import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type CSSProperties,
} from 'vue'

export const RUNAWAY_ATTEMPT_LIMIT = 5
export const MIN_NO_BUTTON_SCALE = 0.6
export const MAX_YES_BUTTON_SCALE = 1.6

const NO_BUTTON_SCALE_STEP = 0.08
const YES_BUTTON_SCALE_STEP = 0.12
const EDGE_PADDING = 10
const BUTTON_CLEARANCE = 12
const BUTTON_GAP = 12
const INITIAL_BUTTON_TOP = 32
const DEFAULT_BUTTON_WIDTH = 118

export type ButtonScales = {
  no: number
  yes: number
}

type Point = {
  x: number
  y: number
}

type Rectangle = {
  bottom: number
  left: number
  right: number
  top: number
}

function roundScale(value: number): number {
  return Math.round(value * 100) / 100
}

export function normalizeAttemptCount(attempts: number): number {
  if (!Number.isFinite(attempts)) {
    return 0
  }

  return Math.min(RUNAWAY_ATTEMPT_LIMIT, Math.max(0, Math.floor(attempts)))
}

export function getNextAttemptCount(attempts: number): number {
  return Math.min(RUNAWAY_ATTEMPT_LIMIT, normalizeAttemptCount(attempts) + 1)
}

export function hasReachedRunawayLimit(attempts: number): boolean {
  return normalizeAttemptCount(attempts) >= RUNAWAY_ATTEMPT_LIMIT
}

export function calculateButtonScales(attempts: number): ButtonScales {
  const safeAttempts = normalizeAttemptCount(attempts)

  return {
    no: roundScale(Math.max(MIN_NO_BUTTON_SCALE, 1 - safeAttempts * NO_BUTTON_SCALE_STEP)),
    yes: roundScale(Math.min(MAX_YES_BUTTON_SCALE, 1 + safeAttempts * YES_BUTTON_SCALE_STEP)),
  }
}

function rectanglesOverlap(first: Rectangle, second: Rectangle, clearance: number): boolean {
  return !(
    first.right + clearance <= second.left
    || first.left >= second.right + clearance
    || first.bottom + clearance <= second.top
    || first.top >= second.bottom + clearance
  )
}

function visualRectangle(point: Point, width: number, height: number, scale: number): Rectangle {
  const horizontalInset = width * (1 - scale) / 2
  const verticalInset = height * (1 - scale) / 2

  return {
    left: point.x + horizontalInset,
    right: point.x + horizontalInset + width * scale,
    top: point.y + verticalInset,
    bottom: point.y + verticalInset + height * scale,
  }
}

export function useRunawayButton(random: () => number = Math.random) {
  const containerRef = ref<HTMLElement | null>(null)
  const noButtonRef = ref<HTMLButtonElement | null>(null)
  const yesButtonRef = ref<HTMLButtonElement | null>(null)
  const attempts = ref(0)
  const position = ref<Point>({ x: 0, y: 0 })
  const positionReady = ref(false)
  const prefersReducedMotion = ref(false)

  let motionQuery: MediaQueryList | null = null
  let resizeObserver: ResizeObserver | null = null

  const scales = computed(() => calculateButtonScales(attempts.value))
  const pairOffset = computed(
    () => ((noButtonRef.value?.offsetWidth ?? DEFAULT_BUTTON_WIDTH) + BUTTON_GAP) / 2,
  )
  const canRunAway = computed(
    () => attempts.value < RUNAWAY_ATTEMPT_LIMIT && !prefersReducedMotion.value,
  )
  const runawayLimitReached = computed(() => hasReachedRunawayLimit(attempts.value))

  const noButtonStyle = computed<CSSProperties>(() => ({
    transform: `translate3d(${position.value.x}px, ${position.value.y}px, 0) scale(${scales.value.no})`,
    visibility: positionReady.value ? 'visible' : 'hidden',
  }))

  const yesButtonStyle = computed<CSSProperties>(() => ({
    '--yes-button-pair-offset': `${pairOffset.value}px`,
    '--yes-button-scale': String(scales.value.yes),
    '--yes-button-shift': `${pairOffset.value * attempts.value / RUNAWAY_ATTEMPT_LIMIT}px`,
  }))

  function setInitialPosition(): void {
    const container = containerRef.value
    const noButton = noButtonRef.value

    if (!container || !noButton) {
      return
    }

    const scale = scales.value.no
    const horizontalInset = noButton.offsetWidth * (1 - scale) / 2
    const verticalInset = noButton.offsetHeight * (1 - scale) / 2
    const minX = EDGE_PADDING - horizontalInset
    const maxX = container.clientWidth - EDGE_PADDING - noButton.offsetWidth + horizontalInset
    const minY = EDGE_PADDING - verticalInset
    const maxY = container.clientHeight - EDGE_PADDING - noButton.offsetHeight + verticalInset

    const desiredPosition = attempts.value === 0
      ? {
          x: container.clientWidth / 2 + BUTTON_GAP / 2,
          y: INITIAL_BUTTON_TOP,
        }
      : position.value

    position.value = {
      x: Math.max(minX, Math.min(maxX, desiredPosition.x)),
      y: Math.max(minY, Math.min(maxY, desiredPosition.y)),
    }
    positionReady.value = true

    if (attempts.value === 0) {
      return
    }

    const yesRectangle = getYesRectangle(scales.value.yes, attempts.value)
    const noRectangle = visualRectangle(
      position.value,
      noButton.offsetWidth,
      noButton.offsetHeight,
      scale,
    )

    if (yesRectangle && rectanglesOverlap(noRectangle, yesRectangle, BUTTON_CLEARANCE)) {
      const safePosition = findNextPosition(scales.value.no, scales.value.yes, attempts.value)

      if (safePosition) {
        position.value = safePosition
      }
    }
  }

  function getYesRectangle(
    nextScale: number,
    nextAttempt: number,
  ): Rectangle | null {
    const container = containerRef.value
    const yesButton = yesButtonRef.value

    if (!container || !yesButton) {
      return null
    }

    const nextProgress = normalizeAttemptCount(nextAttempt) / RUNAWAY_ATTEMPT_LIMIT
    const centerX = container.clientWidth / 2 - pairOffset.value + pairOffset.value * nextProgress
    const centerY = INITIAL_BUTTON_TOP + yesButton.offsetHeight / 2
    const width = yesButton.offsetWidth * nextScale
    const height = yesButton.offsetHeight * nextScale

    return {
      left: centerX - width / 2,
      right: centerX + width / 2,
      top: centerY - height / 2,
      bottom: centerY + height / 2,
    }
  }

  function findNextPosition(
    nextScale: number,
    nextYesScale: number,
    nextAttempt: number,
  ): Point | null {
    const container = containerRef.value
    const noButton = noButtonRef.value

    if (!container || !noButton) {
      return null
    }

    const width = noButton.offsetWidth
    const height = noButton.offsetHeight
    const horizontalInset = width * (1 - nextScale) / 2
    const verticalInset = height * (1 - nextScale) / 2
    const minX = EDGE_PADDING - horizontalInset
    const maxX = container.clientWidth - EDGE_PADDING - width + horizontalInset
    const minY = EDGE_PADDING - verticalInset
    const maxY = container.clientHeight - EDGE_PADDING - height + verticalInset

    if (maxX < minX || maxY < minY) {
      return null
    }

    const yesRectangle = getYesRectangle(nextYesScale, nextAttempt)
    const minimumDistance = Math.min(
      56,
      Math.max(28, Math.min(container.clientWidth, container.clientHeight) * 0.14),
    )
    const currentCenter = {
      x: position.value.x + width / 2,
      y: position.value.y + height / 2,
    }
    const currentRectangle = visualRectangle(position.value, width, height, scales.value.no)

    const candidates: Point[] = Array.from({ length: 72 }, () => ({
      x: minX + random() * (maxX - minX),
      y: minY + random() * (maxY - minY),
    }))

    candidates.push(
      { x: minX, y: minY },
      { x: maxX, y: minY },
      { x: minX, y: maxY },
      { x: maxX, y: maxY },
      { x: (minX + maxX) / 2, y: maxY },
    )

    for (let row = 0; row <= 4; row += 1) {
      for (let column = 0; column <= 4; column += 1) {
        candidates.push({
          x: minX + column / 4 * (maxX - minX),
          y: minY + row / 4 * (maxY - minY),
        })
      }
    }

    for (const candidate of candidates) {
      const candidateCenter = { x: candidate.x + width / 2, y: candidate.y + height / 2 }
      const distance = Math.hypot(
        candidateCenter.x - currentCenter.x,
        candidateCenter.y - currentCenter.y,
      )

      if (distance < minimumDistance) {
        continue
      }

      const noRectangle = visualRectangle(candidate, width, height, nextScale)

      if (rectanglesOverlap(noRectangle, currentRectangle, BUTTON_CLEARANCE)) {
        continue
      }

      if (!yesRectangle || !rectanglesOverlap(noRectangle, yesRectangle, BUTTON_CLEARANCE)) {
        return candidate
      }
    }

    return null
  }

  function runAway(): boolean {
    if (!canRunAway.value) {
      return false
    }

    if (!positionReady.value) {
      setInitialPosition()
    }

    const nextAttempt = getNextAttemptCount(attempts.value)
    const nextScales = calculateButtonScales(nextAttempt)
    const nextPosition = findNextPosition(nextScales.no, nextScales.yes, nextAttempt)

    if (!nextPosition) {
      return false
    }

    position.value = nextPosition
    attempts.value = nextAttempt

    return true
  }

  function resetRunawayButton(): void {
    attempts.value = 0
    positionReady.value = false
    void nextTick(setInitialPosition)
  }

  function handleMotionPreference(event: MediaQueryListEvent): void {
    prefersReducedMotion.value = event.matches
  }

  function observeCurrentContainer(): void {
    resizeObserver?.disconnect()

    if (resizeObserver && containerRef.value) {
      resizeObserver.observe(containerRef.value)
    }
  }

  watch(containerRef, (container) => {
    observeCurrentContainer()

    if (container) {
      setInitialPosition()
    }
  })

  onMounted(() => {
    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    prefersReducedMotion.value = motionQuery.matches
    motionQuery.addEventListener('change', handleMotionPreference)

    resizeObserver = new ResizeObserver(setInitialPosition)

    void nextTick(() => {
      setInitialPosition()
      observeCurrentContainer()
    })
  })

  onBeforeUnmount(() => {
    motionQuery?.removeEventListener('change', handleMotionPreference)
    resizeObserver?.disconnect()
    motionQuery = null
    resizeObserver = null
  })

  return {
    attempts,
    canRunAway,
    containerRef,
    noButtonRef,
    noButtonStyle,
    positionReady,
    prefersReducedMotion,
    resetRunawayButton,
    runawayLimitReached,
    runAway,
    yesButtonRef,
    yesButtonStyle,
  }
}
