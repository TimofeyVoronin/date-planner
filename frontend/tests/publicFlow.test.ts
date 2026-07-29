import { describe, expect, it } from 'vitest'
import type { ActivityOptionRecord } from '../types/activity'
import type {
  ConfirmedPlanRecord,
  InvitationPlanOption,
  InvitationRecord,
} from '../types/invitation'
import {
  canChangeDeclinedInvitationResponse,
  getPublicFlowCurrentStepId,
  getPublicFlowCurrentStepIndex,
  getPublicFlowSteps,
  getPublicFlowTransitionKey,
  getPublicInvitationStage,
  getPublicResumeNotice,
  isPublicResponseStage,
  PUBLIC_RESUME_REFRESH_COOLDOWN_MS,
  shouldRefreshPublicSnapshotOnResume,
} from '../utils/publicFlow'

const now = new Date('2030-01-01T10:00:00Z')

const futureOption: InvitationPlanOption = {
  id: '11111111-1111-4111-8111-111111111111',
  starts_at: '2030-01-02T18:00:00Z',
  time_zone: 'UTC',
  place: 'Кофейня',
  comment: 'Столик у окна',
  position: 0,
}

const expiredOption: InvitationPlanOption = {
  ...futureOption,
  id: '22222222-2222-4222-8222-222222222222',
  starts_at: '2029-12-31T18:00:00Z',
}

const activityOption: ActivityOptionRecord = {
  id: '33333333-3333-4333-8333-333333333333',
  title: 'Кино',
  description: 'Выбрать фильм вместе',
  image_key: 'activity-movie',
  place: 'Кинотеатр',
  position: 0,
}

const confirmedPlan: ConfirmedPlanRecord = {
  option_id: futureOption.id,
  activity_option_id: activityOption.id,
  starts_at: futureOption.starts_at,
  time_zone: futureOption.time_zone,
  place: futureOption.place,
  comment: futureOption.comment,
  activity_title: activityOption.title,
  activity_description: activityOption.description,
  activity_place: activityOption.place,
  activity_image_key: activityOption.image_key,
  final_title: 'До встречи',
  final_subtitle: 'План подтверждён',
  final_image_key: 'final-default',
  final_text: 'Жду тебя завтра.',
  confirmed_at: '2030-01-01T11:00:00Z',
}

function invitationRecord(
  overrides: Partial<InvitationRecord> = {},
): InvitationRecord {
  return {
    id: 'd9428888-122b-11e1-b85c-61cd3cbb3210',
    author_name: 'Алиса',
    recipient_name: 'Борис',
    message: 'Пойдём на свидание?',
    creation_mode: 'extended',
    planning_mode: 'after_acceptance',
    server_now: now.toISOString(),
    publication_status: 'published',
    published_at: '2030-01-01T09:00:00Z',
    response_status: 'pending',
    responded_at: null,
    screens: [],
    plan_options: [],
    activity_options: [],
    selected_option_id: null,
    selected_at: null,
    selected_activity_option_id: null,
    activity_selected_at: null,
    confirmed_at: null,
    confirmed_plan: null,
    created_at: '2030-01-01T09:00:00Z',
    updated_at: '2030-01-01T09:00:00Z',
    ...overrides,
  }
}

describe('public invitation state machine', () => {
  it('starts on the invitation and keeps a declined response on its own terminal screen', () => {
    expect(getPublicInvitationStage(invitationRecord(), now)).toBe('invitation')
    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'declined',
      responded_at: '2030-01-01T10:05:00Z',
    }), now)).toBe('declined')
  })

  it('allows a declined response to change only before final confirmation', () => {
    const declined = invitationRecord({
      response_status: 'declined',
      responded_at: '2030-01-01T10:05:00Z',
    })

    expect(canChangeDeclinedInvitationResponse(declined)).toBe(true)
    expect(canChangeDeclinedInvitationResponse({
      ...declined,
      confirmed_at: confirmedPlan.confirmed_at,
      confirmed_plan: confirmedPlan,
    })).toBe(false)
    expect(canChangeDeclinedInvitationResponse(invitationRecord())).toBe(false)
  })

  it('requires an accepted recipient to choose a usable date', () => {
    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
    }), now)).toBe('date_selection')

    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [expiredOption],
      selected_option_id: expiredOption.id,
      selected_at: '2029-12-30T10:00:00Z',
    }), now)).toBe('date_selection')
  })

  it('moves from a saved date to activity selection only when activities exist', () => {
    const selectedDate = {
      response_status: 'accepted' as const,
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [futureOption],
      selected_option_id: futureOption.id,
      selected_at: '2030-01-01T10:10:00Z',
    }

    expect(getPublicInvitationStage(invitationRecord(selectedDate), now)).toBe(
      'awaiting_confirmation',
    )
    expect(getPublicInvitationStage(invitationRecord({
      ...selectedDate,
      activity_options: [activityOption],
    }), now)).toBe('activity_selection')
  })

  it('waits for the author after the complete date and activity choice', () => {
    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [futureOption],
      selected_option_id: futureOption.id,
      selected_at: '2030-01-01T10:10:00Z',
      activity_options: [activityOption],
      selected_activity_option_id: activityOption.id,
      activity_selected_at: '2030-01-01T10:15:00Z',
    }), now)).toBe('awaiting_confirmation')
  })

  it('treats confirmation as the highest-priority final state', () => {
    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'declined',
      confirmed_at: confirmedPlan.confirmed_at,
      confirmed_plan: confirmedPlan,
    }), now)).toBe('final')

    expect(getPublicInvitationStage(invitationRecord({
      response_status: 'accepted',
      confirmed_at: confirmedPlan.confirmed_at,
      confirmed_plan: null,
    }), now)).toBe('final')
  })
})

describe('public flow progress', () => {
  it('includes or skips the activity step based on the server collection', () => {
    expect(getPublicFlowSteps(true).map(step => step.id)).toEqual([
      'invitation',
      'date_selection',
      'activity_selection',
      'confirmation',
    ])
    expect(getPublicFlowSteps(false).map(step => step.id)).toEqual([
      'invitation',
      'date_selection',
      'confirmation',
    ])
  })

  it.each([
    ['invitation', false, 'invitation', 0],
    ['acceptance', true, 'invitation', 0],
    ['declined', true, 'invitation', 0],
    ['date_selection', false, 'date_selection', 1],
    ['activity_selection', true, 'activity_selection', 2],
    ['activity_selection', false, 'confirmation', 2],
    ['awaiting_confirmation', false, 'confirmation', 2],
    ['final', true, 'confirmation', 3],
  ] as const)(
    'maps %s to its visible progress step',
    (stage, hasActivities, stepId, index) => {
      expect(getPublicFlowCurrentStepId(stage, hasActivities)).toBe(stepId)
      expect(getPublicFlowCurrentStepIndex(stage, hasActivities)).toBe(index)
    },
  )

  it('keeps all response presentations in one transition instance', () => {
    expect(getPublicFlowTransitionKey('invitation')).toBe('response')
    expect(getPublicFlowTransitionKey('acceptance')).toBe('response')
    expect(getPublicFlowTransitionKey('declined')).toBe('declined')
    expect(getPublicFlowTransitionKey('date_selection')).toBe('date_selection')
    expect(isPublicResponseStage('acceptance')).toBe(true)
    expect(isPublicResponseStage('declined')).toBe(false)
    expect(isPublicResponseStage('final')).toBe(false)
  })
})


describe('public flow restoration', () => {
  it('does not show a restoration notice for a new pending invitation', () => {
    expect(getPublicResumeNotice(invitationRecord(), now)).toBeNull()
  })

  it('restores accepted invitations at the next incomplete step', () => {
    expect(getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [futureOption],
    }), now)).toMatchObject({
      title: 'Ответ восстановлен',
      tone: 'info',
    })

    expect(getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [futureOption],
      selected_option_id: futureOption.id,
      selected_at: '2030-01-01T10:10:00Z',
      activity_options: [activityOption],
    }), now)).toMatchObject({
      title: 'Дата восстановлена',
      tone: 'info',
    })
  })

  it('explains an expired persisted date and whether replacements exist', () => {
    const withReplacement = getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [expiredOption, futureOption],
      selected_option_id: expiredOption.id,
      selected_at: '2029-12-30T10:00:00Z',
    }), now)

    expect(withReplacement).toMatchObject({
      title: 'Выбранная дата больше не актуальна',
      tone: 'warning',
    })
    expect(withReplacement?.description).toContain('Выбери новую актуальную дату')

    const withoutReplacement = getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [expiredOption],
      selected_option_id: expiredOption.id,
      selected_at: '2029-12-30T10:00:00Z',
    }), now)

    expect(withoutReplacement?.description).toContain('Автору нужно предложить новые даты')
  })

  it('restores waiting, declined, and confirmed terminal states', () => {
    expect(getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      responded_at: '2030-01-01T10:05:00Z',
      plan_options: [futureOption],
      selected_option_id: futureOption.id,
      selected_at: '2030-01-01T10:10:00Z',
      activity_options: [activityOption],
      selected_activity_option_id: activityOption.id,
      activity_selected_at: '2030-01-01T10:15:00Z',
    }), now)).toMatchObject({
      title: 'Выбор восстановлен',
    })

    expect(getPublicResumeNotice(invitationRecord({
      response_status: 'declined',
      responded_at: '2030-01-01T10:05:00Z',
    }), now)).toMatchObject({
      title: 'Ответ восстановлен',
    })

    expect(getPublicResumeNotice(invitationRecord({
      response_status: 'accepted',
      confirmed_at: confirmedPlan.confirmed_at,
      confirmed_plan: confirmedPlan,
    }), now)).toMatchObject({
      title: 'План восстановлен',
      tone: 'success',
    })
  })

  it('throttles focus and visibility refreshes without blocking an explicit retry', () => {
    const timestamp = 1_000_000

    expect(shouldRefreshPublicSnapshotOnResume(null, timestamp)).toBe(true)
    expect(shouldRefreshPublicSnapshotOnResume(timestamp, timestamp + 1_000)).toBe(false)
    expect(shouldRefreshPublicSnapshotOnResume(
      timestamp,
      timestamp + PUBLIC_RESUME_REFRESH_COOLDOWN_MS,
    )).toBe(true)
  })
})
