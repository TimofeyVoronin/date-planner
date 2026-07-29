import type { InvitationRecord } from '../types/invitation'
import { findSelectedActivityOption } from './activities'
import { findUsableSelectedPlanOption } from './planning'

export const PUBLIC_INVITATION_STAGES = [
  'invitation',
  'acceptance',
  'date_selection',
  'activity_selection',
  'awaiting_confirmation',
  'final',
  'declined',
] as const

export type PublicInvitationStage = typeof PUBLIC_INVITATION_STAGES[number]
export type PublicFlowStepId = 'invitation' | 'date_selection' | 'activity_selection' | 'confirmation'

export type PublicFlowStep = {
  icon: string
  id: PublicFlowStepId
  label: string
}

const PUBLIC_FLOW_STEPS: readonly PublicFlowStep[] = [
  { id: 'invitation', icon: '💌', label: 'Ответ' },
  { id: 'date_selection', icon: '🗓️', label: 'Дата' },
  { id: 'activity_selection', icon: '✨', label: 'Активность' },
  { id: 'confirmation', icon: '💞', label: 'Подтверждение' },
]

const RESPONSE_STAGES: readonly PublicInvitationStage[] = [
  'invitation',
  'acceptance',
]

export function canChangeDeclinedInvitationResponse(
  invitation: InvitationRecord,
): boolean {
  return invitation.response_status === 'declined'
    && invitation.confirmed_at === null
    && invitation.confirmed_plan === null
}

export function getPublicInvitationStage(
  invitation: InvitationRecord,
  now: Date,
): PublicInvitationStage {
  if (invitation.confirmed_plan || invitation.confirmed_at) {
    return 'final'
  }

  if (invitation.response_status === 'declined') {
    return 'declined'
  }

  if (invitation.response_status !== 'accepted') {
    return 'invitation'
  }

  const selectedPlanOption = findUsableSelectedPlanOption(
    invitation.plan_options,
    invitation.selected_option_id,
    now,
  )

  if (!selectedPlanOption) {
    return 'date_selection'
  }

  if (
    invitation.activity_options.length > 0
    && !findSelectedActivityOption(
      invitation.activity_options,
      invitation.selected_activity_option_id,
    )
  ) {
    return 'activity_selection'
  }

  return 'awaiting_confirmation'
}

export function getPublicFlowSteps(hasActivityOptions: boolean): PublicFlowStep[] {
  return PUBLIC_FLOW_STEPS
    .filter(step => hasActivityOptions || step.id !== 'activity_selection')
    .map(step => ({ ...step }))
}

export function getPublicFlowCurrentStepId(
  stage: PublicInvitationStage,
  hasActivityOptions: boolean,
): PublicFlowStepId {
  if (stage === 'date_selection') {
    return 'date_selection'
  }

  if (stage === 'activity_selection') {
    return hasActivityOptions ? 'activity_selection' : 'confirmation'
  }

  if (stage === 'awaiting_confirmation' || stage === 'final') {
    return 'confirmation'
  }

  return 'invitation'
}

export function getPublicFlowCurrentStepIndex(
  stage: PublicInvitationStage,
  hasActivityOptions: boolean,
): number {
  const steps = getPublicFlowSteps(hasActivityOptions)
  const currentStepId = getPublicFlowCurrentStepId(stage, hasActivityOptions)

  return Math.max(0, steps.findIndex(step => step.id === currentStepId))
}

export function getPublicFlowTransitionKey(stage: PublicInvitationStage): string {
  return RESPONSE_STAGES.includes(stage) ? 'response' : stage
}

export function isPublicResponseStage(stage: PublicInvitationStage): boolean {
  return RESPONSE_STAGES.includes(stage)
}
