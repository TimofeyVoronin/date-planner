import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH,
  ACTIVITY_OPTION_PLACE_MAX_LENGTH,
  ACTIVITY_OPTION_TITLE_MAX_LENGTH,
  MAX_ACTIVITY_OPTIONS,
  MIN_ACTIVITY_OPTIONS,
  type ActivityOptionRecord,
} from '../types/activity'
import {
  activityDraftsToPayload,
  activityOptionDraftsHaveChanges,
  activityOptionToDraft,
  activityStepRequiresOptionSave,
  getDefaultActivityOptionImageKey,
  isActivityOptionImageKey,
  normalizeActivityOption,
  normalizeActivityOptionsResponse,
  parseActivityOptionsApiError,
  sortActivityOptions,
  validateActivityOptionDrafts,
  type ActivityOptionDraft,
} from '../utils/activities'

const savedOptions: ActivityOptionRecord[] = [
  {
    id: 'activity-b',
    title: 'Кино',
    description: 'Премьера и обсуждение после фильма',
    image_key: 'activity-movie',
    place: 'Кинотеатр в центре',
    position: 1,
  },
  {
    id: 'activity-a',
    title: 'Кофе',
    description: 'Спокойный разговор',
    image_key: 'activity-coffee',
    place: 'Кофейня',
    position: 0,
  },
  {
    id: 'activity-c',
    title: 'Сюрприз',
    description: '',
    image_key: 'activity-selection-default',
    place: '',
    position: 2,
  },
]

const validDrafts: ActivityOptionDraft[] = [
  {
    title: ' Кофе ',
    description: ' Спокойный разговор ',
    imageKey: 'activity-coffee',
    place: ' Кофейня ',
  },
  {
    title: 'Кино',
    description: 'Премьера',
    imageKey: 'activity-movie',
    place: '',
  },
  {
    title: 'Прогулка',
    description: '',
    imageKey: 'activity-selection-default',
    place: 'Парк',
  },
]

describe('activity option normalization', () => {
  it('normalizes and sorts a collection by server position', () => {
    expect(normalizeActivityOptionsResponse({ options: savedOptions })).toEqual([
      savedOptions[1],
      savedOptions[0],
      savedOptions[2],
    ])
    expect(sortActivityOptions(savedOptions).map(option => option.id)).toEqual([
      'activity-a',
      'activity-b',
      'activity-c',
    ])
  })

  it('rejects malformed collection and option payloads', () => {
    expect(() => normalizeActivityOptionsResponse([])).toThrow(
      'Сервер вернул некорректную коллекцию активностей.',
    )
    expect(() => normalizeActivityOption(null)).toThrow(
      'Сервер вернул некорректный вариант активности.',
    )
    expect(() => normalizeActivityOption({ ...savedOptions[0], position: -1 })).toThrow(
      'Сервер вернул неполные данные варианта активности.',
    )
    expect(() => normalizeActivityOption({ ...savedOptions[0], title: 42 })).toThrow(
      'Сервер вернул неполные данные варианта активности.',
    )
  })

  it('uses only supported local image keys and a stable fallback cycle', () => {
    expect(isActivityOptionImageKey('activity-coffee')).toBe(true)
    expect(isActivityOptionImageKey('https://example.com/image.svg')).toBe(false)
    expect(isActivityOptionImageKey(null)).toBe(false)
    expect(getDefaultActivityOptionImageKey(-5)).toBe('activity-selection-default')
    expect(getDefaultActivityOptionImageKey(1)).toBe('activity-coffee')
    expect(getDefaultActivityOptionImageKey(5)).toBe('activity-movie')
  })

  it('converts saved options to editable drafts and replaces unknown image keys safely', () => {
    expect(activityOptionToDraft(savedOptions[1]!)).toEqual({
      title: 'Кофе',
      description: 'Спокойный разговор',
      imageKey: 'activity-coffee',
      place: 'Кофейня',
    })
    expect(activityOptionToDraft({
      ...savedOptions[0]!,
      image_key: 'future-image-key',
      position: 2,
    }).imageKey).toBe('activity-movie')
  })
})

describe('activity option editing contract', () => {
  it('accepts three to six valid activities', () => {
    expect(validateActivityOptionDrafts(validDrafts)).toEqual({
      formError: null,
      optionErrors: [{}, {}, {}],
      valid: true,
    })
    expect(validateActivityOptionDrafts([
      ...validDrafts,
      ...validDrafts,
    ]).valid).toBe(true)
  })

  it('reports collection bounds and exact invalid fields', () => {
    expect(validateActivityOptionDrafts(validDrafts.slice(0, 2))).toMatchObject({
      formError: `Добавь минимум ${MIN_ACTIVITY_OPTIONS} активности.`,
      valid: false,
    })
    expect(validateActivityOptionDrafts([
      ...validDrafts,
      ...validDrafts,
      validDrafts[0]!,
    ])).toMatchObject({
      formError: `Можно предложить не больше ${MAX_ACTIVITY_OPTIONS} активностей.`,
      valid: false,
    })

    const invalid = validateActivityOptionDrafts([
      {
        title: ' ',
        description: 'A'.repeat(ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH + 1),
        imageKey: 'invalid-key' as ActivityOptionDraft['imageKey'],
        place: 'A'.repeat(ACTIVITY_OPTION_PLACE_MAX_LENGTH + 1),
      },
      {
        ...validDrafts[1]!,
        title: 'A'.repeat(ACTIVITY_OPTION_TITLE_MAX_LENGTH + 1),
      },
      validDrafts[2]!,
    ])

    expect(invalid.valid).toBe(false)
    expect(invalid.optionErrors[0]).toEqual({
      title: 'Укажи название активности.',
      description: `Не больше ${ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH} символов.`,
      imageKey: 'Выбери изображение из встроенной библиотеки.',
      place: `Не больше ${ACTIVITY_OPTION_PLACE_MAX_LENGTH} символов.`,
    })
    expect(invalid.optionErrors[1]?.title).toBe(
      `Не больше ${ACTIVITY_OPTION_TITLE_MAX_LENGTH} символов.`,
    )
  })

  it('trims payload values without changing submitted order', () => {
    expect(activityDraftsToPayload(validDrafts)).toEqual({
      options: [
        {
          title: 'Кофе',
          description: 'Спокойный разговор',
          image_key: 'activity-coffee',
          place: 'Кофейня',
        },
        {
          title: 'Кино',
          description: 'Премьера',
          image_key: 'activity-movie',
          place: '',
        },
        {
          title: 'Прогулка',
          description: '',
          image_key: 'activity-selection-default',
          place: 'Парк',
        },
      ],
    })
  })

  it('detects draft changes and requires a complete third step before moving forward', () => {
    expect(activityOptionDraftsHaveChanges(
      validDrafts,
      validDrafts.map(item => ({ ...item })),
    )).toBe(false)
    expect(activityOptionDraftsHaveChanges(validDrafts, validDrafts.slice(0, 2))).toBe(true)
    expect(activityOptionDraftsHaveChanges(validDrafts, [
      { ...validDrafts[0]!, place: 'Другое место' },
      ...validDrafts.slice(1),
    ])).toBe(true)

    expect(activityStepRequiresOptionSave(false, 3, true)).toBe(false)
    expect(activityStepRequiresOptionSave(false, 0, true)).toBe(true)
    expect(activityStepRequiresOptionSave(true, 3, false)).toBe(true)
    expect(activityStepRequiresOptionSave(false, 0, false)).toBe(false)
  })
})

describe('activity API errors and builder integration', () => {
  it('maps positional server errors to the matching editor fields', () => {
    const parsed = parseActivityOptionsApiError({
      statusCode: 400,
      data: {
        options: [
          {},
          {
            title: ['This field may not be blank.'],
            description: ['Too long.'],
            image_key: ['Invalid.'],
            place: ['Too long.'],
          },
        ],
      },
    })

    expect(parsed.message).toBe(
      'Проверь названия, изображения и дополнительные поля активностей.',
    )
    expect(parsed.optionErrors[1]).toEqual({
      title: `Укажи название длиной до ${ACTIVITY_OPTION_TITLE_MAX_LENGTH} символов.`,
      description: `Описание должно быть не длиннее ${ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH} символов.`,
      imageKey: 'Выбери корректное локальное изображение.',
      place: `Место должно быть не длиннее ${ACTIVITY_OPTION_PLACE_MAX_LENGTH} символов.`,
    })
  })

  it('maps collection, conflict, nested-response and generic errors', () => {
    expect(parseActivityOptionsApiError({
      statusCode: 400,
      data: { options: ['Too short.'] },
    }).formError).toBe(
      `Добавь от ${MIN_ACTIVITY_OPTIONS} до ${MAX_ACTIVITY_OPTIONS} активностей.`,
    )

    expect(parseActivityOptionsApiError({
      statusCode: 400,
      response: { _data: { options: 'Invalid collection.' } },
    }).formError).toBe(
      `Добавь от ${MIN_ACTIVITY_OPTIONS} до ${MAX_ACTIVITY_OPTIONS} активностей.`,
    )

    expect(parseActivityOptionsApiError({
      statusCode: 409,
      data: { detail: 'Published.' },
    }).message).toBe(
      'Активности уже нельзя изменить. Обнови страницу и проверь состояние приглашения.',
    )

    expect(parseActivityOptionsApiError({ statusCode: 500 }).formError).toBeNull()
  })

  it('connects the editor, save boundary and live preview to builder step three', () => {
    const builder = readFileSync(
      new URL('../app/pages/manage/[id]/builder.vue', import.meta.url),
      'utf8',
    )
    const preview = readFileSync(
      new URL('../components/builder/BuilderMobilePreview.vue', import.meta.url),
      'utf8',
    )

    expect(builder).toContain('<ActivityOptionsEditor')
    expect(builder).toContain('return flushActivityOptions(requireCompleteStep)')
    expect(builder).toContain(':activity-options="previewActivityOptions"')
    expect(builder).toContain('api.getActivityOptions(invitationId.value, token)')
    expect(builder).toContain('api.saveActivityOptions(invitationId.value, token, payload)')
    expect(preview).toContain('v-for="option in visibleActivityOptions"')
    expect(preview).toContain("usesDraftActivityOptions ? 'Твои варианты'")
  })
})
