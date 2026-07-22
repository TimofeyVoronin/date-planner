import { onMounted, onUnmounted, readonly, ref } from 'vue'

const CLOCK_REFRESH_INTERVAL_MS = 1_000

export function calculateServerTimeOffset(serverNow: string, clientNow: Date): number | null {
  const serverTimestamp = new Date(serverNow).getTime()

  if (Number.isNaN(serverTimestamp)) {
    return null
  }

  return serverTimestamp - clientNow.getTime()
}

export function estimateServerTime(clientNow: Date, serverOffsetMs: number): Date {
  return new Date(clientNow.getTime() + serverOffsetMs)
}

export function useExpiryClock() {
  const serverOffsetMs = ref(0)
  const currentTime = ref(estimateServerTime(new Date(), serverOffsetMs.value))
  let intervalId: ReturnType<typeof setInterval> | null = null

  function refreshCurrentTime(): Date {
    const nextTime = estimateServerTime(new Date(), serverOffsetMs.value)
    currentTime.value = nextTime

    return nextTime
  }

  function synchronizeServerTime(serverNow: string): Date {
    const clientNow = new Date()
    const nextOffset = calculateServerTimeOffset(serverNow, clientNow)

    if (nextOffset !== null) {
      serverOffsetMs.value = nextOffset
      currentTime.value = estimateServerTime(clientNow, nextOffset)

      return currentTime.value
    }

    return refreshCurrentTime()
  }

  function refreshWhenVisible(): void {
    if (document.visibilityState === 'visible') {
      refreshCurrentTime()
    }
  }

  onMounted(() => {
    refreshCurrentTime()
    intervalId = setInterval(refreshCurrentTime, CLOCK_REFRESH_INTERVAL_MS)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    window.addEventListener('focus', refreshCurrentTime)
  })

  onUnmounted(() => {
    if (intervalId !== null) {
      clearInterval(intervalId)
    }

    document.removeEventListener('visibilitychange', refreshWhenVisible)
    window.removeEventListener('focus', refreshCurrentTime)
  })

  return {
    currentTime: readonly(currentTime),
    refreshCurrentTime,
    synchronizeServerTime,
  }
}
