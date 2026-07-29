import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  BUILDER_PREVIEW_ACTIVITIES,
  buildBuilderPreviewDemoDateOptions,
  BUILDER_PREVIEW_DEVICES,
  BUILDER_PREVIEW_SCREEN_DEFINITIONS,
  buildBuilderPreviewActivityOptions,
  buildBuilderPreviewDateOptions,
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

  it('reserves enough desktop space for the largest phone preview', () => {
    const css = readFileSync(
      new URL('../app/assets/css/main.css', import.meta.url),
      'utf8',
    )
    const phoneWidth = Number(
      css.match(/--builder-preview-max-phone-width:\s*(\d+)px/)?.[1],
    )
    const scrollbarWidth = Number(
      css.match(/--builder-preview-scrollbar-width:\s*(\d+)px/)?.[1],
    )
    const inlineReserve = Number(
      css.match(/--builder-preview-inline-reserve:\s*(\d+)px/)?.[1],
    )
    const largestDeviceWidth = Math.max(
      ...BUILDER_PREVIEW_DEVICES.map(device => device.width),
    )

    expect(phoneWidth).toBe(largestDeviceWidth)
    expect(scrollbarWidth).toBeGreaterThan(0)
    expect(inlineReserve).toBeGreaterThanOrEqual(70 + scrollbarWidth * 2)
    expect(css).toContain(
      'calc(var(--builder-preview-max-phone-width) + var(--builder-preview-inline-reserve))',
    )
    expect(css).toContain('scrollbar-gutter: stable')
    expect(css).toContain(
      'padding-inline: calc(20px + var(--builder-preview-scrollbar-width)) 20px',
    )
  })

  it('recognizes preview screens and clamps the runaway-button transform', () => {
    expect(isBuilderPreviewScreen('final')).toBe(true)
    expect(isBuilderPreviewScreen('manage')).toBe(false)
    expect(getBuilderPreviewNoButtonTransform(-5)).toEqual({ x: 0, y: 0, scale: 1 })
    expect(getBuilderPreviewNoButtonTransform(2)).toEqual({ x: -46, y: 18, scale: .84 })
    expect(getBuilderPreviewNoButtonTransform(99)).toEqual({ x: 34, y: 30, scale: .76 })
  })

  it('turns local date drafts into live preview choices', () => {
    expect(buildBuilderPreviewDateOptions([
      { startsAt: '2030-01-02T18:30', place: ' Кофейня ', comment: ' У окна ' },
      { startsAt: '', place: '', comment: '' },
    ])).toEqual([
      {
        id: 'draft-date-1',
        label: '02.01.2030 · 18:30',
        description: 'Кофейня — У окна',
      },
      {
        id: 'draft-date-2',
        label: 'Дата и время пока не указаны',
        description: 'Место пока не указано',
      },
    ])
  })

  it('turns local activity drafts into live preview choices', () => {
    expect(buildBuilderPreviewActivityOptions([
      {
        title: ' Кино ',
        description: ' Премьера ',
        imageKey: 'activity-movie',
        place: ' Центр ',
      },
      {
        title: '',
        description: '',
        imageKey: 'activity-coffee',
        place: '',
      },
    ])).toEqual([
      {
        id: 'draft-activity-1',
        label: 'Кино',
        description: 'Центр — Премьера',
        imageKey: 'activity-movie',
      },
      {
        id: 'draft-activity-2',
        label: 'Название активности пока не указано',
        description: 'Описание пока не указано',
        imageKey: 'activity-coffee',
      },
    ])
  })

  it('builds future demonstration dates from synchronized server time', () => {
    const options = buildBuilderPreviewDemoDateOptions(
      new Date(2026, 6, 29, 23, 30),
    )

    expect(options).toEqual([
      {
        id: 'date-friday',
        label: 'Пятница, 31 июля · 19:00',
        description: 'Кофейня у парка',
      },
      {
        id: 'date-saturday',
        label: 'Суббота, 1 августа · 17:30',
        description: 'Встречаемся у набережной',
      },
      {
        id: 'date-tuesday',
        label: 'Вторник, 4 августа · 20:00',
        description: 'Вечерняя прогулка по центру',
      },
    ])
    expect(new Set(options.map(option => option.id)).size).toBe(options.length)
    expect(options.every(option => option.description.length > 0)).toBe(true)
  })

  it('moves a same-day demonstration slot to the following week after it passes', () => {
    const options = buildBuilderPreviewDemoDateOptions(
      new Date(2026, 7, 4, 20, 1),
    )
    const tuesday = options.find(option => option.id === 'date-tuesday')

    expect(tuesday?.label).toBe('Вторник, 11 августа · 20:00')
  })

  it('feeds synchronized server time into demonstration date generation', () => {
    const preview = readFileSync(
      new URL('../components/builder/BuilderMobilePreview.vue', import.meta.url),
      'utf8',
    )
    const builderPage = readFileSync(
      new URL('../app/pages/manage/[id]/builder.vue', import.meta.url),
      'utf8',
    )

    expect(preview).toContain('currentTime: Date')
    expect(preview).toContain('buildBuilderPreviewDemoDateOptions(props.currentTime)')
    expect(builderPage).toContain(':current-time="currentTime"')
  })

  it('keeps demonstration activity choices stable and unique', () => {
    const activityIds = BUILDER_PREVIEW_ACTIVITIES.map(option => option.id)

    expect(new Set(activityIds).size).toBe(activityIds.length)
    expect(BUILDER_PREVIEW_ACTIVITIES.every(option => option.description.length > 0)).toBe(true)
  })
})
