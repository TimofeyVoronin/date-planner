import { describe, expect, it } from 'vitest'
import {
  MAX_YES_BUTTON_SCALE,
  MIN_NO_BUTTON_SCALE,
  RUNAWAY_ATTEMPT_LIMIT,
  calculateButtonScales,
  getNextAttemptCount,
  getNoButtonClickAction,
  hasReachedRunawayLimit,
  normalizeAttemptCount,
  type NoButtonClickAction,
} from '../composables/useRunawayButton'

describe('calculateButtonScales', () => {
  it('returns the initial scale before any attempts', () => {
    expect(calculateButtonScales(0)).toEqual({ no: 1, yes: 1 })
  })

  it('changes both scales after every successful attempt', () => {
    expect(calculateButtonScales(1)).toEqual({ no: 0.9, yes: 1.15 })
    expect(calculateButtonScales(3)).toEqual({ no: 0.7, yes: 1.45 })
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
  it('increments successful evasions up to four', () => {
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

  it('stops moving after four evasions so the fifth attempt can decline', () => {
    expect(RUNAWAY_ATTEMPT_LIMIT).toBe(4)
    expect(hasReachedRunawayLimit(3)).toBe(false)
    expect(hasReachedRunawayLimit(4)).toBe(true)
    expect(hasReachedRunawayLimit(100)).toBe(true)
  })
})

describe('no-button click policy', () => {
  it('moves for pointer input while evasions remain', () => {
    expect(getNoButtonClickAction({
      canRunAway: true,
      keyboardActivation: false,
      prefersReducedMotion: false,
      runawayEnabled: true,
      runawayLimitReached: false,
      secondChance: false,
    })).toBe('run-away')
  })

  it('runs away four times and declines on the fifth pointer attempt', () => {
    let attempts = 0
    const actions: NoButtonClickAction[] = []

    for (let index = 0; index <= RUNAWAY_ATTEMPT_LIMIT; index += 1) {
      const action = getNoButtonClickAction({
        canRunAway: !hasReachedRunawayLimit(attempts),
        keyboardActivation: false,
        prefersReducedMotion: false,
        runawayEnabled: true,
        runawayLimitReached: hasReachedRunawayLimit(attempts),
        secondChance: false,
      })

      actions.push(action)

      if (action === 'run-away') {
        attempts = getNextAttemptCount(attempts)
      }
    }

    expect(actions).toEqual([
      'run-away',
      'run-away',
      'run-away',
      'run-away',
      'decline',
    ])
    expect(attempts).toBe(RUNAWAY_ATTEMPT_LIMIT)
  })

  it('keeps keyboard and reduced-motion decline immediately accessible', () => {
    const baseContext = {
      canRunAway: true,
      runawayEnabled: true,
      runawayLimitReached: false,
      secondChance: false,
    }

    expect(getNoButtonClickAction({
      ...baseContext,
      keyboardActivation: true,
      prefersReducedMotion: false,
    })).toBe('decline')
    expect(getNoButtonClickAction({
      ...baseContext,
      keyboardActivation: false,
      prefersReducedMotion: true,
    })).toBe('decline')
  })

  it('offers a stable second chance if layout cannot move the button', () => {
    expect(getNoButtonClickAction({
      canRunAway: false,
      keyboardActivation: false,
      prefersReducedMotion: false,
      runawayEnabled: true,
      runawayLimitReached: false,
      secondChance: false,
    })).toBe('offer-second-chance')
  })

  it('declines directly when the runaway behavior is disabled', () => {
    expect(getNoButtonClickAction({
      canRunAway: true,
      keyboardActivation: false,
      prefersReducedMotion: false,
      runawayEnabled: false,
      runawayLimitReached: false,
      secondChance: false,
    })).toBe('decline')
  })
})
