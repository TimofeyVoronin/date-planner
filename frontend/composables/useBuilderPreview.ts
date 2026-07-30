import { computed, ref } from 'vue'
import type {
  BuilderPreviewDeviceId,
  BuilderPreviewScreen,
} from '../types/builder-preview'
import type { BuilderStepNumber } from '../utils/builder'
import {
  BUILDER_PREVIEW_ACTIVITIES,
  getBuilderPreviewNoButtonTransform,
  getBuilderPreviewScreenForStep,
  getNextBuilderPreviewScreen,
  getPreviousBuilderPreviewScreen,
} from '../utils/builderPreview'

export const BUILDER_PREVIEW_NO_BUTTON_ATTEMPT_LIMIT = 4

const BUILDER_PREVIEW_DEFAULT_DATE_ID = 'date-friday'

export function useBuilderPreview(initialStep: BuilderStepNumber = 1) {
  const activeScreen = ref<BuilderPreviewScreen>(getBuilderPreviewScreenForStep(initialStep))
  const deviceId = ref<BuilderPreviewDeviceId>('regular')
  const selectedDateId = ref(BUILDER_PREVIEW_DEFAULT_DATE_ID)
  const selectedActivityId = ref(BUILDER_PREVIEW_ACTIVITIES[0]!.id)
  const noButtonAttempts = ref(0)

  const selectedActivity = computed(() => (
    BUILDER_PREVIEW_ACTIVITIES.find(option => option.id === selectedActivityId.value)
    ?? BUILDER_PREVIEW_ACTIVITIES[0]!
  ))
  const previousScreen = computed(() => getPreviousBuilderPreviewScreen(activeScreen.value))
  const nextScreen = computed(() => getNextBuilderPreviewScreen(activeScreen.value))
  const noButtonTransform = computed(() => (
    getBuilderPreviewNoButtonTransform(noButtonAttempts.value)
  ))
  const noButtonLimitReached = computed(() => (
    noButtonAttempts.value >= BUILDER_PREVIEW_NO_BUTTON_ATTEMPT_LIMIT
  ))

  function selectScreen(screen: BuilderPreviewScreen): void {
    activeScreen.value = screen
    noButtonAttempts.value = 0
  }

  function syncToBuilderStep(step: BuilderStepNumber): void {
    selectScreen(getBuilderPreviewScreenForStep(step))
  }

  function goForward(): void {
    if (nextScreen.value) {
      selectScreen(nextScreen.value)
    }
  }

  function goBack(): void {
    if (previousScreen.value) {
      selectScreen(previousScreen.value)
    }
  }

  function reset(): void {
    activeScreen.value = 'invitation'
    selectedDateId.value = BUILDER_PREVIEW_DEFAULT_DATE_ID
    selectedActivityId.value = BUILDER_PREVIEW_ACTIVITIES[0]!.id
    noButtonAttempts.value = 0
  }

  function runAwayNoButton(): void {
    noButtonAttempts.value = Math.min(
      noButtonAttempts.value + 1,
      BUILDER_PREVIEW_NO_BUTTON_ATTEMPT_LIMIT,
    )
  }

  return {
    activeScreen,
    deviceId,
    nextScreen,
    noButtonAttempts,
    noButtonLimitReached,
    noButtonTransform,
    previousScreen,
    selectedActivity,
    selectedActivityId,
    selectedDateId,
    goBack,
    goForward,
    reset,
    runAwayNoButton,
    selectScreen,
    syncToBuilderStep,
  }
}
