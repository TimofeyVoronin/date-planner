import { describe, expect, it } from 'vitest'
import type { InvitationScreenRecord } from '../types/screen'
import {
  buildInvitationScreenUpdatePayload,
  createInvitationScreenEditForm,
  getInvitationScreenByType,
  getInvitationScreenPresentation,
  getInvitationScreensForBuilderStep,
  isInvitationScreenType,
  normalizeInvitationScreen,
  normalizeInvitationScreens,
  parseInvitationScreenApiError,
  sortInvitationScreens,
  validateInvitationScreenEditForm,
} from '../utils/screens'

const screens: InvitationScreenRecord[] = [
  {
    screen_type: 'invitation',
    title: 'Ты пойдёшь со мной на свидание?',
    subtitle: 'Особенное приглашение',
    button_text: 'Да!',
    secondary_button_text: 'Нет',
    image_key: 'invitation-default',
    template_text: '',
  },
  {
    screen_type: 'acceptance',
    title: 'Ура!',
    subtitle: 'Выберем дату',
    button_text: 'Выбрать дату',
    secondary_button_text: '',
    image_key: 'acceptance-default',
    template_text: '',
  },
  {
    screen_type: 'date_selection',
    title: 'Когда тебе удобно?',
    subtitle: 'Выбери дату',
    button_text: 'Продолжить',
    secondary_button_text: '',
    image_key: 'date-selection-default',
    template_text: '',
  },
  {
    screen_type: 'activity_selection',
    title: 'Чем займёмся?',
    subtitle: 'Выбери активность',
    button_text: 'Продолжить',
    secondary_button_text: '',
    image_key: 'activity-selection-default',
    template_text: '',
  },
  {
    screen_type: 'final',
    title: 'Договорились',
    subtitle: 'Итоговый план',
    button_text: 'Посмотреть план',
    secondary_button_text: '',
    image_key: 'final-default',
    template_text: '{recipient}, жду тебя {date} в {time}. Встречаемся в {place}, а дальше нас ждёт {activity} 💘',
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

  it('rejects unsafe or misplaced final templates', () => {
    expect(() => normalizeInvitationScreens([
      ...screens.slice(0, 4),
      { ...screens[4], template_text: '{author.name}' },
    ])).toThrow(/небезопасный шаблон/i)

    expect(() => normalizeInvitationScreens([
      { ...screens[0], template_text: '{recipient}' },
      ...screens.slice(1),
    ])).toThrow(/другому экрану/i)
  })

  it('rejects an unknown or incompatible image key', () => {
    expect(() => normalizeInvitationScreens([
      { ...screens[0], image_key: 'unknown-image' },
      ...screens.slice(1),
    ])).toThrow(/неизвестное изображение/i)

    expect(() => normalizeInvitationScreens([
      { ...screens[0], image_key: 'final-default' },
      ...screens.slice(1),
    ])).toThrow(/не подходит/i)
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

  it('builds a minimal normalized PATCH for the primary screen', () => {
    const screen = screens[0]!
    const form = createInvitationScreenEditForm(screen)

    form.title = '  Новый вопрос  '
    form.image_key = 'invitation-moon'

    expect(buildInvitationScreenUpdatePayload(form, screen)).toEqual({
      title: 'Новый вопрос',
      image_key: 'invitation-moon',
    })
    expect(getInvitationScreenByType(screens, 'invitation')).toEqual(screen)
    expect(getInvitationScreenByType(screens, 'final')?.screen_type).toBe('final')
  })

  it('builds and validates the acceptance screen without a decline action', () => {
    const screen = screens[1]!
    const form = createInvitationScreenEditForm(screen)

    form.title = '  Ты правда согласился?  '
    form.button_text = '  Продолжить  '
    form.secondary_button_text = 'Это поле не относится ко второму экрану'
    form.image_key = 'acceptance-fireworks'

    expect(buildInvitationScreenUpdatePayload(form, screen)).toEqual({
      title: 'Ты правда согласился?',
      button_text: 'Продолжить',
      image_key: 'acceptance-fireworks',
    })
    expect(validateInvitationScreenEditForm({
      ...form,
      button_text: '',
      image_key: 'invitation-default',
    }, 'acceptance')).toMatchObject({
      button_text: expect.any(String),
      image_key: expect.any(String),
    })
    expect(validateInvitationScreenEditForm({
      ...form,
      secondary_button_text: '',
    }, 'acceptance').secondary_button_text).toBeUndefined()
  })

  it('builds and validates the editable final screen without an action button', () => {
    const screen = screens[4]!
    const form = createInvitationScreenEditForm(screen)

    form.title = '  До встречи!  '
    form.subtitle = '  Наш план подтверждён.  '
    form.button_text = ''
    form.image_key = 'final-night'
    form.template_text = '  {recipient}, {author} ждёт тебя {date} в {time}: {activity} — {place}.  '

    expect(buildInvitationScreenUpdatePayload(form, screen)).toEqual({
      title: 'До встречи!',
      subtitle: 'Наш план подтверждён.',
      image_key: 'final-night',
      template_text: '{recipient}, {author} ждёт тебя {date} в {time}: {activity} — {place}.',
    })
    expect(validateInvitationScreenEditForm(form, 'final')).toEqual({})
    expect(validateInvitationScreenEditForm({
      ...form,
      title: ' ',
      image_key: 'invitation-default',
      template_text: '{author.name}',
    }, 'final')).toMatchObject({
      title: expect.any(String),
      image_key: expect.any(String),
      template_text: expect.any(String),
    })
  })

  it('validates required actions, limits, and compatible image choice', () => {
    const screen = screens[0]!

    expect(validateInvitationScreenEditForm({
      ...createInvitationScreenEditForm(screen),
      title: '   ',
      button_text: '',
      secondary_button_text: '',
      image_key: 'final-default',
    })).toMatchObject({
      title: expect.any(String),
      button_text: expect.any(String),
      secondary_button_text: expect.any(String),
      image_key: expect.any(String),
    })
  })

  it('normalizes one PATCH response and parses field errors', () => {
    expect(normalizeInvitationScreen(screens[0])).toEqual(screens[0])
    expect(parseInvitationScreenApiError({
      statusCode: 400,
      data: {
        template_text: ['Неизвестная переменная.'],
        title: ['Обязательное поле.'],
      },
    })).toMatchObject({
      status: 400,
      message: 'Проверь заполненные поля экрана.',
      fieldErrors: {
        template_text: 'Неизвестная переменная.',
        title: 'Обязательное поле.',
      },
    })
  })
})
