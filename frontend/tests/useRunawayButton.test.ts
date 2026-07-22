import { describe, expect, it } from 'vitest'
import {
  MAX_YES_BUTTON_SCALE,
  MIN_NO_BUTTON_SCALE,
  RUNAWAY_ATTEMPT_LIMIT,
  calculateButtonScales,
  getNextAttemptCount,
  hasReachedRunawayLimit,
  normalizeAttemptCount,
} from '../composables/useRunawayButton'

describe('calculateButtonScales', () => {
  it('returns the initial scale before any attempts', () => {
    expect(calculateButtonScales(0)).toEqual({ no: 1, yes: 1 })
  })

  it('changes both scales after every successful attempt', () => {
    expect(calculateButtonScales(1)).toEqual({ no: 0.92, yes: 1.12 })
    expect(calculateButtonScales(3)).toEqual({ no: 0.76, yes: 1.36 })
  })

  it('honours the lower and upper scale limits', () => {
    expect(calculateButtonScales(RUNAWAY_ATTEMPT_LIMIT)).toEqual({
      no: MIN_NO_BUTTON_SCALE,
      yes: MAX_YES_BUTTON_SCALE,
    })
    expect(calculateButtonScales(100)).toEqual({
      no: MIN_NO_BUTTON_SCALE,
      yes: MAX_YES_BUTTON_SCALE,
    })
  })
})

describe('attempt counter', () => {
  it('increments successful attempts up to five', () => {
    let attempts = 0

    for (let index = 0; index < 10; index += 1) {
      attempts = getNextAttemptCount(attempts)
    }

    expect(attempts).toBe(RUNAWAY_ATTEMPT_LIMIT)
  })

  it('normalizes invalid, fractional, and negative values', () => {
    expect(normalizeAttemptCount(Number.NaN)).toBe(0)
    expect(normalizeAttemptCount(-2)).toBe(0)
    expect(normalizeAttemptCount(2.9)).toBe(2)
    expect(normalizeAttemptCount(8)).toBe(RUNAWAY_ATTEMPT_LIMIT)
  })

  it('reports the fifth successful attempt as the runaway limit', () => {
    expect(hasReachedRunawayLimit(4)).toBe(false)
    expect(hasReachedRunawayLimit(5)).toBe(true)
    expect(hasReachedRunawayLimit(100)).toBe(true)
  })
})
