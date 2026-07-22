import { describe, expect, it } from 'vitest'
import {
  calculateServerTimeOffset,
  estimateServerTime,
} from '../composables/useExpiryClock'
import type { InvitationPlanOption } from '../types/invitation'
import { isPlanOptionExpired } from '../utils/planning'

function option(startsAt: string): InvitationPlanOption {
  return {
    id: 'option',
    starts_at: startsAt,
    place: 'Кафе',
    comment: '',
    position: 1,
  }
}

describe('backend-synchronized expiry clock', () => {
  it('corrects a browser clock that is two hours ahead', () => {
    const browserNow = new Date('2030-01-01T14:00:00Z')
    const offset = calculateServerTimeOffset('2030-01-01T12:00:00Z', browserNow)

    expect(offset).toBe(-2 * 60 * 60 * 1_000)
    const estimatedServerNow = estimateServerTime(
      new Date('2030-01-01T14:30:00Z'),
      offset ?? 0,
    )

    expect(estimatedServerNow.toISOString()).toBe('2030-01-01T12:30:00.000Z')
    expect(isPlanOptionExpired(option('2030-01-01T12:45:00Z'), estimatedServerNow)).toBe(false)
  })

  it('corrects a browser clock that is two hours behind', () => {
    const browserNow = new Date('2030-01-01T10:00:00Z')
    const offset = calculateServerTimeOffset('2030-01-01T12:00:00Z', browserNow)

    expect(offset).toBe(2 * 60 * 60 * 1_000)
    const estimatedServerNow = estimateServerTime(
      new Date('2030-01-01T10:30:00Z'),
      offset ?? 0,
    )

    expect(estimatedServerNow.toISOString()).toBe('2030-01-01T12:30:00.000Z')
    expect(isPlanOptionExpired(option('2030-01-01T12:15:00Z'), estimatedServerNow)).toBe(true)
  })

  it('ignores an invalid server timestamp', () => {
    expect(calculateServerTimeOffset('not-a-date', new Date())).toBeNull()
  })
})
