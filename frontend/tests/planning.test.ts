import { describe, expect, it } from 'vitest'
import type { InvitationPlanOption } from '../types/invitation'
import {
  findSelectedPlanOption,
  getMinimumPlanDateTime,
  isoToLocalDateTime,
  localDateTimeToIso,
  parsePlanningApiError,
  planDraftsToPayload,
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

  it('presents actionable validation and conflict errors', () => {
    expect(parsePlanningApiError({ status: 400 }, 'selection').message).toContain('недоступен')
    expect(parsePlanningApiError({ status: 409 }, 'options').message).toContain('нельзя изменить')
    expect(parsePlanningApiError({ status: 429 }, 'options').message).toContain('минуту')
  })
})
