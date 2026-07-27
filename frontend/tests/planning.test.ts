import { describe, expect, it, vi } from 'vitest'
import type { InvitationPlanOption } from '../types/invitation'
import type { InvitationScreenRecord } from '../types/screen'
import {
  buildPlanConfirmationPayload,
  findSelectedPlanOption,
  findUsableSelectedPlanOption,
  getMinimumPlanDateTime,
  getPersistedPlanSelectionState,
  getPlanSelectionOptionState,
  getPlanSelectionScreenPresentation,
  getSelectablePlanOptions,
  getPlanConfirmationStage,
  isoToLocalDateTime,
  isPlanOptionExpired,
  localDateTimeToIso,
  parsePlanningApiError,
  parsePlanOptionsApiError,
  parsePlanConfirmationApiError,
  planningModeChangeRemovesOptions,
  planningStepRequiresOptionSave,
  planDraftsToPayload,
  planOptionDraftsHaveChanges,
  planOptionsPayloadHasExpiredDate,
  reconcileServerExpiredSelectionId,
  refreshPlanSelectionAfterRejection,
  shouldRefreshPlanSelection,
  shouldAnnounceNewFinalPlan,
  sortPlanOptions,
  validatePlanOptionDrafts,
  type PlanOptionDraft,
} from '../utils/planning'

const futureDrafts: PlanOptionDraft[] = [
  { startsAt: '2030-01-01T13:00', place: 'Кафе', comment: '' },
  { startsAt: '2030-01-02T18:30', place: 'Парк', comment: 'Встретимся у входа' },
]

function option(id: string, position: number, startsAt: string): InvitationPlanOption {
  return {
    id,
    position,
    starts_at: startsAt,
    place: `Место ${id}`,
    comment: '',
  }
}

const dateSelectionScreen: InvitationScreenRecord = {
  screen_type: 'date_selection',
  title: 'Выбери нашу дату',
  subtitle: 'Здесь только актуальные варианты.',
  button_text: 'Подтвердить дату',
  secondary_button_text: '',
  image_key: 'date-sunset',
}

describe('planning date conversion', () => {
  it('converts browser-local datetime to an ISO instant', () => {
    expect(localDateTimeToIso('2030-05-20T19:45')).toBe(
      new Date(2030, 4, 20, 19, 45).toISOString(),
    )
  })

  it('rejects malformed and impossible local dates', () => {
    expect(localDateTimeToIso('')).toBeNull()
    expect(localDateTimeToIso('2030-02-30T10:00')).toBeNull()
    expect(localDateTimeToIso('not-a-date')).toBeNull()
  })

  it('round-trips a valid local minute without changing it', () => {
    const localValue = '2030-06-15T09:05'
    const isoValue = localDateTimeToIso(localValue)

    expect(isoValue).not.toBeNull()
    expect(isoToLocalDateTime(isoValue ?? '')).toBe(localValue)
  })

  it('uses the next whole minute as the minimum input value', () => {
    expect(getMinimumPlanDateTime(new Date(2030, 0, 1, 12, 30, 45))).toBe('2030-01-01T12:31')
  })
})

describe('planning validation and payload', () => {
  const now = new Date(2030, 0, 1, 12, 0)

  it('accepts two complete future options and an empty optional comment', () => {
    expect(validatePlanOptionDrafts(futureDrafts, now)).toEqual({
      formError: null,
      optionErrors: [{}, {}],
      valid: true,
    })
  })

  it('enforces the two-to-five option boundary', () => {
    expect(validatePlanOptionDrafts(futureDrafts.slice(0, 1), now).formError).toContain('минимум 2')
    expect(validatePlanOptionDrafts(Array.from({ length: 6 }, () => futureDrafts[0]), now)
      .formError).toContain('не больше 5')
  })

  it('requires a future datetime and a place for every option', () => {
    const validation = validatePlanOptionDrafts([
      { startsAt: '2029-12-31T23:59', place: ' ', comment: '' },
      futureDrafts[1],
    ], now)

    expect(validation.valid).toBe(false)
    expect(validation.optionErrors[0]?.startsAt).toContain('будущем')
    expect(validation.optionErrors[0]?.place).toContain('место')
  })

  it('enforces backend text limits', () => {
    const validation = validatePlanOptionDrafts([
      { startsAt: futureDrafts[0].startsAt, place: 'P'.repeat(201), comment: 'C'.repeat(501) },
      futureDrafts[1],
    ], now)

    expect(validation.optionErrors[0]?.place).toContain('200')
    expect(validation.optionErrors[0]?.comment).toContain('500')
  })

  it('detects value and ordering changes against the saved draft baseline', () => {
    expect(planOptionDraftsHaveChanges(futureDrafts, futureDrafts.map(item => ({ ...item }))))
      .toBe(false)
    expect(planOptionDraftsHaveChanges([...futureDrafts].reverse(), futureDrafts)).toBe(true)
    expect(planOptionDraftsHaveChanges([
      { ...futureDrafts[0], place: 'Другое место' },
      futureDrafts[1],
    ], futureDrafts)).toBe(true)
    expect(planOptionDraftsHaveChanges(futureDrafts.slice(0, 1), futureDrafts)).toBe(true)
  })

  it('requires valid options before moving forward but not before moving back', () => {
    expect(planningStepRequiresOptionSave(false, 0, true)).toBe(true)
    expect(planningStepRequiresOptionSave(false, 0, false)).toBe(false)
    expect(planningStepRequiresOptionSave(false, 2, true)).toBe(false)
    expect(planningStepRequiresOptionSave(true, 2, false)).toBe(true)
  })

  it('warns when changing the mode would delete saved or unsaved draft options', () => {
    expect(planningModeChangeRemovesOptions(
      'before_acceptance',
      'after_acceptance',
      false,
      2,
    )).toBe(true)
    expect(planningModeChangeRemovesOptions(
      'before_acceptance',
      'after_acceptance',
      true,
      0,
    )).toBe(true)
    expect(planningModeChangeRemovesOptions(
      'after_acceptance',
      'before_acceptance',
      true,
      2,
    )).toBe(false)
    expect(planningModeChangeRemovesOptions(
      'before_acceptance',
      'after_acceptance',
      false,
      0,
    )).toBe(false)
  })

  it('maps nested backend option errors to specific editor fields', () => {
    const parsed = parsePlanOptionsApiError({
      status: 400,
      data: {
        options: [
          { starts_at: ['The proposed time must be in the future.'] },
          { place: ['This field may not be blank.'], comment: ['Too long.'] },
        ],
      },
    })

    expect(parsed.formError).toBeNull()
    expect(parsed.optionErrors).toEqual([
      { startsAt: 'Выбери корректные будущие дату и время.' },
      {
        place: 'Укажи место длиной до 200 символов.',
        comment: 'Комментарий должен быть не длиннее 500 символов.',
      },
    ])
  })

  it('maps option-count errors to the whole editor', () => {
    const parsed = parsePlanOptionsApiError({
      statusCode: 400,
      response: {
        status: 400,
        _data: { options: ['Ensure this field has at least 2 elements.'] },
      },
    })

    expect(parsed.formError).toContain('от 2 до 5')
    expect(parsed.optionErrors).toEqual([])
  })

  it('falls back to a form-level message for an unknown validation response', () => {
    const parsed = parsePlanOptionsApiError({
      status: 400,
      data: { detail: 'Invalid option set.' },
    })

    expect(parsed.formError).toContain('Проверь')
    expect(parsed.optionErrors).toEqual([])
  })

  it('recognizes non-field option-list errors and transport failures', () => {
    expect(parsePlanOptionsApiError({
      status: 400,
      data: { options: { non_field_errors: ['Invalid list.'] } },
    }).formError).toContain('от 2 до 5')

    const transportError = parsePlanOptionsApiError(new Error('offline'))
    expect(transportError.status).toBeNull()
    expect(transportError.formError).toBeNull()
    expect(transportError.optionErrors).toEqual([])
  })

  it('trims text and serializes local datetimes for the API', () => {
    expect(planDraftsToPayload([
      { startsAt: '2030-01-01T13:00', place: '  Кафе  ', comment: '  У окна ' },
      futureDrafts[1],
    ])).toEqual({
      options: [
        {
          starts_at: new Date(2030, 0, 1, 13, 0).toISOString(),
          place: 'Кафе',
          comment: 'У окна',
        },
        {
          starts_at: new Date(2030, 0, 2, 18, 30).toISOString(),
          place: 'Парк',
          comment: 'Встретимся у входа',
        },
      ],
    })
  })

  it('rechecks serialized option dates at the exact save instant', () => {
    const now = new Date('2030-01-01T12:00:00Z')

    expect(planOptionsPayloadHasExpiredDate({
      options: [
        { starts_at: now.toISOString(), place: 'Кафе', comment: '' },
        { starts_at: '2030-01-01T13:00:00Z', place: 'Парк', comment: '' },
      ],
    }, now)).toBe(true)
    expect(planOptionsPayloadHasExpiredDate({
      options: [
        { starts_at: '2030-01-01T12:00:01Z', place: 'Кафе', comment: '' },
        { starts_at: '2030-01-01T13:00:00Z', place: 'Парк', comment: '' },
      ],
    }, now)).toBe(false)
  })
})

describe('recipient date-selection screen', () => {
  const now = new Date('2030-01-02T12:00:00Z')

  it('shows only future options in the author-defined order', () => {
    const options = [
      option('later', 2, '2030-01-04T12:00:00Z'),
      option('expired', 0, '2030-01-02T12:00:00Z'),
      option('first', 1, '2030-01-03T12:00:00Z'),
      option('invalid', 3, 'not-a-date'),
    ]

    expect(getSelectablePlanOptions(options, now).map(item => item.id)).toEqual([
      'first',
      'later',
    ])
    expect(options.map(item => item.id)).toEqual(['later', 'expired', 'first', 'invalid'])
  })

  it('distinguishes empty, expired, and available option sets', () => {
    expect(getPlanSelectionOptionState([], now)).toEqual({
      availability: 'empty',
      options: [],
    })

    expect(getPlanSelectionOptionState([
      option('expired', 0, '2030-01-02T12:00:00Z'),
      option('invalid', 1, 'not-a-date'),
    ], now)).toEqual({
      availability: 'expired',
      options: [],
    })

    const available = getPlanSelectionOptionState([
      option('later', 2, '2030-01-04T12:00:00Z'),
      option('expired', 0, '2030-01-02T12:00:00Z'),
      option('first', 1, '2030-01-03T12:00:00Z'),
    ], now)

    expect(available.availability).toBe('available')
    expect(available.options.map(item => item.id)).toEqual(['first', 'later'])
  })

  it('uses the configured date-selection copy, action, and image', () => {
    expect(getPlanSelectionScreenPresentation(dateSelectionScreen)).toEqual({
      title: 'Выбери нашу дату',
      subtitle: 'Здесь только актуальные варианты.',
      buttonText: 'Подтвердить дату',
      imageKey: 'date-sunset',
    })
  })

  it('preserves an empty subtitle and defends required public copy', () => {
    expect(getPlanSelectionScreenPresentation({
      ...dateSelectionScreen,
      title: '   ',
      subtitle: '   ',
      button_text: '   ',
    })).toEqual({
      title: 'Выбери вариант свидания',
      subtitle: '',
      buttonText: 'Сохранить выбор',
      imageKey: 'date-sunset',
    })
  })

  it('falls back to the built-in public screen for quick invitations', () => {
    expect(getPlanSelectionScreenPresentation(null)).toEqual({
      title: 'Выбери вариант свидания',
      subtitle: 'Выбор можно изменить до этапа итогового подтверждения.',
      buttonText: 'Сохранить выбор',
      imageKey: 'date-selection-default',
    })
    expect(getPlanSelectionScreenPresentation({
      ...dateSelectionScreen,
      screen_type: 'acceptance',
      image_key: 'acceptance-default',
    })).toEqual(getPlanSelectionScreenPresentation(null))
  })
})

describe('persisted planning state', () => {
  const options = [
    option('second', 2, '2030-01-02T12:00:00Z'),
    option('first', 1, '2030-01-01T12:00:00Z'),
  ]

  it('sorts by position without mutating the API array', () => {
    expect(sortPlanOptions(options).map(item => item.id)).toEqual(['first', 'second'])
    expect(options.map(item => item.id)).toEqual(['second', 'first'])
  })

  it('finds only a selected option belonging to this invitation', () => {
    expect(findSelectedPlanOption(options, 'first')?.id).toBe('first')
    expect(findSelectedPlanOption(options, 'missing')).toBeNull()
    expect(findSelectedPlanOption(options, null)).toBeNull()
  })

  it('binds final confirmation to the date and activity shown to the author', () => {
    expect(buildPlanConfirmationPayload('shown-option', 'shown-activity')).toEqual({
      confirmed: true,
      option_id: 'shown-option',
      activity_option_id: 'shown-activity',
    })
    expect(buildPlanConfirmationPayload('shown-option', null)).toEqual({
      confirmed: true,
      option_id: 'shown-option',
      activity_option_id: null,
    })
  })

  it('treats an option at or before the current instant as expired', () => {
    const now = new Date('2030-01-01T12:00:00Z')

    expect(isPlanOptionExpired(option('past', 1, '2030-01-01T11:59:59Z'), now)).toBe(true)
    expect(isPlanOptionExpired(option('boundary', 1, now.toISOString()), now)).toBe(true)
    expect(isPlanOptionExpired(option('future', 1, '2030-01-01T12:00:01Z'), now)).toBe(false)
  })

  it('does not expose an expired persisted selection as a usable choice', () => {
    const now = new Date('2030-01-01T12:00:00Z')
    const choices = [
      option('expired', 1, '2030-01-01T12:00:00Z'),
      option('future', 2, '2030-01-01T12:00:01Z'),
    ]

    expect(findUsableSelectedPlanOption(choices, 'expired', now)).toBeNull()
    expect(findUsableSelectedPlanOption(choices, 'future', now)?.id).toBe('future')
  })

  it('replaces an attempted local choice with the authoritative persisted snapshot', () => {
    const now = new Date('2030-01-01T12:00:00Z')
    const choices = [
      option('attempted-locally', 1, '2030-01-01T13:00:00Z'),
      option('selected-on-server', 2, '2030-01-01T14:00:00Z'),
    ]

    expect(getPersistedPlanSelectionState(choices, 'selected-on-server', now)).toEqual({
      isSaved: true,
      selectedOptionId: 'selected-on-server',
    })
    expect(getPersistedPlanSelectionState(choices, null, now)).toEqual({
      isSaved: false,
      selectedOptionId: null,
    })
  })

  it('presents actionable validation and conflict errors', () => {
    const unavailableSelection = parsePlanningApiError({ status: 400 }, 'selection')
    const conflictedSelection = parsePlanningApiError({ status: 409 }, 'selection')

    expect(unavailableSelection.message).toContain('недоступен')
    expect(parsePlanningApiError({ status: 409 }, 'options').message).toContain('нельзя изменить')
    expect(parsePlanningApiError({ status: 429 }, 'options').message).toContain('минуту')
    expect(shouldRefreshPlanSelection(unavailableSelection)).toBe(true)
    expect(shouldRefreshPlanSelection(conflictedSelection)).toBe(true)
    expect(shouldRefreshPlanSelection(parsePlanningApiError({ status: 429 }, 'selection')))
      .toBe(false)
  })

  it.each([400, 409])('refetches the authoritative snapshot after selection status %i', async (
    status,
  ) => {
    const loadLatest = vi.fn(async () => ({ confirmed_at: '2030-01-01T10:00:00Z' }))
    const parsedError = parsePlanningApiError({ status }, 'selection')

    await expect(refreshPlanSelectionAfterRejection(parsedError, loadLatest)).resolves.toEqual({
      confirmed_at: '2030-01-01T10:00:00Z',
    })
    expect(loadLatest).toHaveBeenCalledOnce()
  })

  it('does not refetch the snapshot for a retryable transport error', async () => {
    const loadLatest = vi.fn(async () => ({ confirmed_at: null }))
    const parsedError = parsePlanningApiError({ status: 429 }, 'selection')

    await expect(refreshPlanSelectionAfterRejection(parsedError, loadLatest)).resolves.toBeNull()
    expect(loadLatest).not.toHaveBeenCalled()
  })

  it('separates ready, expired, and already confirmed planning states', () => {
    const now = new Date('2029-12-31T12:00:00Z')
    const futureOption = option('future', 1, '2030-01-01T12:00:00Z')
    const expiredOption = option('expired', 1, '2029-12-31T11:59:59Z')

    expect(getPlanConfirmationStage('pending', null, null, now)).toBe('hidden')
    expect(getPlanConfirmationStage('declined', futureOption, null, now)).toBe('hidden')
    expect(getPlanConfirmationStage('accepted', null, null, now)).toBe('hidden')
    expect(getPlanConfirmationStage(
      'accepted',
      null,
      '2029-12-31T10:00:00Z',
      now,
    )).toBe('confirmed')
    expect(getPlanConfirmationStage('accepted', futureOption, null, now)).toBe('ready')
    expect(getPlanConfirmationStage(
      'accepted',
      futureOption,
      null,
      now,
      futureOption.id,
    )).toBe('expired')
    expect(getPlanConfirmationStage('accepted', expiredOption, null, now)).toBe('expired')
    expect(getPlanConfirmationStage(
      'accepted',
      expiredOption,
      '2029-12-31T10:00:00Z',
      now,
    )).toBe(
      'confirmed',
    )
  })

  it('retains a server-expired marker only for the same unconfirmed selection', () => {
    expect(reconcileServerExpiredSelectionId('selected', 'selected', null)).toBe('selected')
    expect(reconcileServerExpiredSelectionId('selected', 'replacement', null)).toBeNull()
    expect(reconcileServerExpiredSelectionId('selected', null, null)).toBeNull()
    expect(reconcileServerExpiredSelectionId(
      'selected',
      'selected',
      '2030-01-01T10:00:00Z',
    )).toBeNull()
  })

  it('announces only a final plan first discovered by an API update', () => {
    expect(shouldAnnounceNewFinalPlan(null, '2030-01-01T10:00:00Z')).toBe(true)
    expect(shouldAnnounceNewFinalPlan(null, null)).toBe(false)
    expect(shouldAnnounceNewFinalPlan(
      '2030-01-01T10:00:00Z',
      '2030-01-01T10:00:00Z',
    )).toBe(false)
  })

  it('recognizes the stable expired-selection code and tells the author to refresh', () => {
    const expiredError = parsePlanConfirmationApiError({
      response: {
        status: 409,
        _data: { code: 'selected_option_expired' },
      },
    })

    expect(expiredError.code).toBe('selected_option_expired')
    expect(expiredError.message).toContain('Время выбранного варианта уже прошло')
    expect(expiredError.message).toContain('Обнови данные')

    const changedActivityError = parsePlanConfirmationApiError({
      response: {
        status: 409,
        _data: { code: 'selected_activity_changed' },
      },
    })

    expect(changedActivityError.code).toBe('selected_activity_changed')
    expect(changedActivityError.message).toContain('изменил активность')
    expect(parsePlanConfirmationApiError({ status: 400 }).message).toContain('явным')
    expect(parsePlanConfirmationApiError({ status: 409 }).message).toContain('Обнови данные')
    expect(parsePlanConfirmationApiError({ status: 429 }).message).toContain('минуту')
  })
})
