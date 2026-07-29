import type { InvitationRecord } from '../types/invitation'
import { findSelectedActivityOption } from './activities'
import {
  findSelectedPlanOption,
  findUsableSelectedPlanOption,
  getSelectablePlanOptions,
  isPlanOptionExpired,
} from './planning'

export const PUBLIC_INVITATION_STAGES = [
  'invitation',
  'acceptance',
  'date_selection',
  'activity_selection',
  'awaiting_confirmation',
  'final',
  'declined',
] as const

export const PUBLIC_RESUME_REFRESH_COOLDOWN_MS = 15_000

export type PublicInvitationStage = typeof PUBLIC_INVITATION_STAGES[number]
export type PublicFlowStepId = 'invitation' | 'date_selection' | 'activity_selection' | 'confirmation'
export type PublicResumeNoticeTone = 'info' | 'success' | 'warning'

export type PublicFlowStep = {
  icon: string
  id: PublicFlowStepId
  label: string
}

export type PublicResumeNotice = {
  description: string
  icon: string
  title: string
  tone: PublicResumeNoticeTone
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

export function getPublicResumeNotice(
  invitation: InvitationRecord,
  now: Date,
): PublicResumeNotice | null {
  if (invitation.confirmed_plan || invitation.confirmed_at) {
    return {
      description: 'Итоговый план уже подтверждён. Мы сразу открыли сохранённую финальную карточку.',
      icon: '💞',
      title: 'План восстановлен',
      tone: 'success',
    }
  }

  if (invitation.response_status === 'declined') {
    return {
      description: 'Твой ответ уже сохранён. Дополнительных действий не требуется.',
      icon: '🌷',
      title: 'Ответ восстановлен',
      tone: 'info',
    }
  }

  if (invitation.response_status !== 'accepted') {
    return null
  }

  const persistedPlanOption = findSelectedPlanOption(
    invitation.plan_options,
    invitation.selected_option_id,
  )
  const selectedPlanOption = findUsableSelectedPlanOption(
    invitation.plan_options,
    invitation.selected_option_id,
    now,
  )
  const persistedSelectionIsUnavailable = Boolean(
    invitation.selected_option_id
    && (
      persistedPlanOption === null
      || isPlanOptionExpired(persistedPlanOption, now)
    )
  )

  if (persistedSelectionIsUnavailable) {
    const hasFutureOptions = getSelectablePlanOptions(invitation.plan_options, now).length > 0

    return {
      description: hasFutureOptions
        ? 'Ранее выбранный вариант уже прошёл или больше недоступен. Выбери новую актуальную дату.'
        : 'Ранее выбранный вариант уже прошёл. Автору нужно предложить новые даты, прежде чем выбор можно будет продолжить.',
      icon: '⌛',
      title: 'Выбранная дата больше не актуальна',
      tone: 'warning',
    }
  }

  if (!selectedPlanOption) {
    const hasFutureOptions = getSelectablePlanOptions(invitation.plan_options, now).length > 0

    return {
      description: hasFutureOptions
        ? 'Согласие уже сохранено. Продолжи с выбора подходящих даты и места.'
        : 'Согласие уже сохранено. Автор ещё готовит актуальные варианты даты.',
      icon: '🗓️',
      title: 'Ответ восстановлен',
      tone: 'info',
    }
  }

  const selectedActivity = findSelectedActivityOption(
    invitation.activity_options,
    invitation.selected_activity_option_id,
  )

  if (invitation.activity_options.length > 0 && !selectedActivity) {
    return {
      description: 'Выбранная дата уже сохранена. Осталось выбрать активность.',
      icon: '✨',
      title: 'Дата восстановлена',
      tone: 'info',
    }
  }

  return {
    description: invitation.activity_options.length > 0
      ? 'Дата и активность уже сохранены. Осталось дождаться окончательного подтверждения автора.'
      : 'Дата уже сохранена. Осталось дождаться окончательного подтверждения автора.',
    icon: '💌',
    title: 'Выбор восстановлен',
    tone: 'info',
  }
}

export function shouldRefreshPublicSnapshotOnResume(
  lastRefreshAt: number | null,
  currentTimestamp: number = Date.now(),
): boolean {
  if (lastRefreshAt === null) {
    return true
  }

  return currentTimestamp - lastRefreshAt >= PUBLIC_RESUME_REFRESH_COOLDOWN_MS
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
