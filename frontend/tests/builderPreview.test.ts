import { describe, expect, it } from 'vitest'
import {
  BUILDER_PREVIEW_ACTIVITIES,
  BUILDER_PREVIEW_DATES,
  BUILDER_PREVIEW_DEVICES,
  BUILDER_PREVIEW_SCREEN_DEFINITIONS,
  getBuilderPreviewDevice,
  getBuilderPreviewNoButtonTransform,
  getBuilderPreviewScreenDefinition,
  getBuilderPreviewScreenForStep,
  getNextBuilderPreviewScreen,
  getPreviousBuilderPreviewScreen,
  isBuilderPreviewDeviceId,
  isBuilderPreviewScreen,
} from '../utils/builderPreview'

describe('builder interactive preview definitions', () => {
  it('defines five ordered and uniquely identified screens', () => {
    const screens = BUILDER_PREVIEW_SCREEN_DEFINITIONS.map(item => item.screen)

    expect(screens).toEqual([
      'invitation',
      'acceptance',
      'date_selection',
      'activity_selection',
      'final',
    ])
    expect(new Set(screens).size).toBe(screens.length)
    expect(BUILDER_PREVIEW_SCREEN_DEFINITIONS.every(item => item.label.length > 0)).toBe(true)
  })

  it('maps each builder step to its relevant preview screen', () => {
    expect(getBuilderPreviewScreenForStep(1)).toBe('invitation')
    expect(getBuilderPreviewScreenForStep(2)).toBe('date_selection')
    expect(getBuilderPreviewScreenForStep(3)).toBe('activity_selection')
    expect(getBuilderPreviewScreenForStep(4)).toBe('final')
    expect(getBuilderPreviewScreenDefinition('acceptance')).toMatchObject({
      builderStep: 1,
      label: 'Ответ «Да»',
    })
  })

  it('moves through preview screens without crossing the boundaries', () => {
    expect(getPreviousBuilderPreviewScreen('invitation')).toBeNull()
    expect(getPreviousBuilderPreviewScreen('date_selection')).toBe('acceptance')
    expect(getNextBuilderPreviewScreen('acceptance')).toBe('date_selection')
    expect(getNextBuilderPreviewScreen('final')).toBeNull()
  })

  it('defines three supported mobile widths', () => {
    expect(BUILDER_PREVIEW_DEVICES.map(device => device.width)).toEqual([320, 375, 430])
    expect(getBuilderPreviewDevice('regular')).toMatchObject({ width: 375 })
    expect(isBuilderPreviewDeviceId('compact')).toBe(true)
    expect(isBuilderPreviewDeviceId('tablet')).toBe(false)
  })

  it('recognizes preview screens and clamps the runaway-button transform', () => {
    expect(isBuilderPreviewScreen('final')).toBe(true)
    expect(isBuilderPreviewScreen('manage')).toBe(false)
    expect(getBuilderPreviewNoButtonTransform(-5)).toEqual({ x: 0, y: 0, scale: 1 })
    expect(getBuilderPreviewNoButtonTransform(2)).toEqual({ x: -46, y: 18, scale: .84 })
    expect(getBuilderPreviewNoButtonTransform(99)).toEqual({ x: 34, y: 30, scale: .76 })
  })

  it('keeps demonstration choices stable and unique', () => {
    const dateIds = BUILDER_PREVIEW_DATES.map(option => option.id)
    const activityIds = BUILDER_PREVIEW_ACTIVITIES.map(option => option.id)

    expect(new Set(dateIds).size).toBe(dateIds.length)
    expect(new Set(activityIds).size).toBe(activityIds.length)
    expect(BUILDER_PREVIEW_DATES.every(option => option.description.length > 0)).toBe(true)
    expect(BUILDER_PREVIEW_ACTIVITIES.every(option => option.description.length > 0)).toBe(true)
  })
})
