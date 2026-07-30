import { describe, expect, it } from 'vitest'
import { BUILDER_PREVIEW_NO_BUTTON_ATTEMPT_LIMIT, useBuilderPreview } from '../composables/useBuilderPreview'

describe('builder interactive preview state', () => {
  it('starts on the screen associated with the current builder step', () => {
    expect(useBuilderPreview(1).activeScreen.value).toBe('invitation')
    expect(useBuilderPreview(3).activeScreen.value).toBe('activity_selection')
  })

  it('synchronizes with another builder step and resets the no-button demo', () => {
    const preview = useBuilderPreview(1)

    preview.runAwayNoButton()
    preview.syncToBuilderStep(2)

    expect(preview.activeScreen.value).toBe('date_selection')
    expect(preview.noButtonAttempts.value).toBe(0)
  })

  it('supports manual forward and backward scenario navigation', () => {
    const preview = useBuilderPreview(1)

    preview.goForward()
    expect(preview.activeScreen.value).toBe('acceptance')
    preview.goForward()
    expect(preview.activeScreen.value).toBe('date_selection')
    preview.goBack()
    expect(preview.activeScreen.value).toBe('acceptance')
  })

  it('preserves a manually selected screen while unrelated preview data changes', () => {
    const preview = useBuilderPreview(1)

    preview.selectScreen('acceptance')
    preview.deviceId.value = 'large'
    preview.selectedDateId.value = 'date-saturday'

    expect(preview.activeScreen.value).toBe('acceptance')
    expect(preview.deviceId.value).toBe('large')
    expect(preview.selectedDateId.value).toBe('date-saturday')
  })

  it('resolves selected demonstration choices and falls back safely', () => {
    const preview = useBuilderPreview(1)

    preview.selectedActivityId.value = 'activity-movie'
    expect(preview.selectedActivity.value.label).toBe('Кино и обсуждение')

    preview.selectedActivityId.value = 'missing'
    expect(preview.selectedActivity.value.id).toBe('activity-walk')
  })

  it('limits the runaway-button demonstration and exposes its final state', () => {
    const preview = useBuilderPreview(1)

    for (let attempt = 0; attempt < 10; attempt += 1) {
      preview.runAwayNoButton()
    }

    expect(preview.noButtonAttempts.value).toBe(BUILDER_PREVIEW_NO_BUTTON_ATTEMPT_LIMIT)
    expect(preview.noButtonLimitReached.value).toBe(true)
    expect(preview.noButtonTransform.value).toEqual({ x: -36, y: -26, scale: .68 })
  })

  it('resets the whole demonstration without changing the selected device', () => {
    const preview = useBuilderPreview(4)

    preview.deviceId.value = 'compact'
    preview.selectedDateId.value = 'date-tuesday'
    preview.selectedActivityId.value = 'activity-surprise'
    preview.runAwayNoButton()
    preview.reset()

    expect(preview.activeScreen.value).toBe('invitation')
    expect(preview.selectedDateId.value).toBe('date-friday')
    expect(preview.selectedActivity.value.id).toBe('activity-walk')
    expect(preview.noButtonAttempts.value).toBe(0)
    expect(preview.deviceId.value).toBe('compact')
  })
})
