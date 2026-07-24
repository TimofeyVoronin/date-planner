import { describe, expect, it } from 'vitest'
import type { InvitationScreenRecord } from '../types/screen'
import {
  getInvitationScreenPresentation,
  getInvitationScreensForBuilderStep,
  isInvitationScreenType,
  normalizeInvitationScreens,
  sortInvitationScreens,
} from '../utils/screens'

const screens: InvitationScreenRecord[] = [
  {
    screen_type: 'invitation',
    title: 'Ты пойдёшь со мной на свидание?',
    subtitle: 'Особенное приглашение',
    button_text: 'Да!',
    image_key: 'invitation-default',
  },
  {
    screen_type: 'acceptance',
    title: 'Ура!',
    subtitle: 'Выберем дату',
    button_text: 'Выбрать дату',
    image_key: 'acceptance-default',
  },
  {
    screen_type: 'date_selection',
    title: 'Когда тебе удобно?',
    subtitle: 'Выбери дату',
    button_text: 'Продолжить',
    image_key: 'date-selection-default',
  },
  {
    screen_type: 'activity_selection',
    title: 'Чем займёмся?',
    subtitle: 'Выбери активность',
    button_text: 'Продолжить',
    image_key: 'activity-selection-default',
  },
  {
    screen_type: 'final',
    title: 'Договорились',
    subtitle: 'Итоговый план',
    button_text: 'Посмотреть план',
    image_key: 'final-default',
  },
]

describe('invitation screen configuration', () => {
  it('recognizes only the five persisted screen types', () => {
    expect(isInvitationScreenType('invitation')).toBe(true)
    expect(isInvitationScreenType('activity_selection')).toBe(true)
    expect(isInvitationScreenType('preview')).toBe(false)
    expect(isInvitationScreenType(null)).toBe(false)
  })

  it('normalizes and sorts a complete API response', () => {
    const reversed = [...screens].reverse()

    expect(normalizeInvitationScreens(reversed)).toEqual(screens)
    expect(sortInvitationScreens(reversed)).toEqual(screens)
    expect(reversed[0]?.screen_type).toBe('final')
  })

  it('rejects an unknown type or malformed field', () => {
    expect(() => normalizeInvitationScreens([
      ...screens.slice(0, 4),
      { ...screens[4], screen_type: 'preview' },
    ])).toThrow(/неизвестный тип/i)

    expect(() => normalizeInvitationScreens([
      ...screens.slice(0, 4),
      { ...screens[4], title: null },
    ])).toThrow(/title/i)
  })

  it('rejects missing and duplicate screen configurations', () => {
    expect(() => normalizeInvitationScreens(screens.slice(0, 4))).toThrow(/отсутствуют/i)
    expect(() => normalizeInvitationScreens([
      ...screens.slice(0, 4),
      { ...screens[0] },
    ])).toThrow(/повторяющиеся/i)
  })

  it('groups invitation and acceptance on the first builder step', () => {
    expect(getInvitationScreensForBuilderStep(screens, 1).map(screen => screen.screen_type)).toEqual([
      'invitation',
      'acceptance',
    ])
    expect(getInvitationScreensForBuilderStep(screens, 2).map(screen => screen.screen_type)).toEqual([
      'date_selection',
    ])
    expect(getInvitationScreensForBuilderStep(screens, 3).map(screen => screen.screen_type)).toEqual([
      'activity_selection',
    ])
    expect(getInvitationScreensForBuilderStep(screens, 4).map(screen => screen.screen_type)).toEqual([
      'final',
    ])
  })

  it('provides stable Russian presentation for every screen', () => {
    expect(getInvitationScreenPresentation('invitation')).toMatchObject({
      label: 'Экран приглашения',
      icon: '💌',
    })
    expect(getInvitationScreenPresentation('final')).toMatchObject({
      label: 'Финальный экран',
      icon: '💞',
    })
  })
})
