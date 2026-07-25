import type { InvitationScreenRecord } from './screen'

export const INVITATION_NAME_MAX_LENGTH = 100
export const INVITATION_MESSAGE_MAX_LENGTH = 1000
export const PLAN_OPTION_PLACE_MAX_LENGTH = 200
export const PLAN_OPTION_COMMENT_MAX_LENGTH = 500
export const MIN_PLAN_OPTIONS = 2
export const MAX_PLAN_OPTIONS = 5
export const INVITATION_CREATION_MODES = ['quick', 'extended'] as const
export const INVITATION_PUBLICATION_STATUSES = ['draft', 'published'] as const
export const INVITATION_PLANNING_MODES = ['before_acceptance', 'after_acceptance'] as const

export type InvitationCreationMode = typeof INVITATION_CREATION_MODES[number]
export type InvitationPublicationStatus = typeof INVITATION_PUBLICATION_STATUSES[number]
export type InvitationPlanningMode = typeof INVITATION_PLANNING_MODES[number]
export type InvitationResponseStatus = 'pending' | 'accepted' | 'declined'
export type FinalInvitationResponseStatus = Exclude<InvitationResponseStatus, 'pending'>

export type InvitationCreatePayload = {
  author_name: string
  recipient_name: string
  message: string
  creation_mode: InvitationCreationMode
}

export type InvitationEditForm = InvitationCreatePayload & {
  planning_mode: InvitationPlanningMode
}

export type InvitationUpdatePayload = Partial<InvitationEditForm>

export type InvitationEditSaveState = 'error' | 'idle' | 'saving' | 'success'

export type InvitationPlanOption = {
  id: string
  starts_at: string
  place: string
  comment: string
  position: number
}

export type PlanOptionPayload = {
  starts_at: string
  place: string
  comment: string
}

export type PlanOptionsPayload = {
  options: PlanOptionPayload[]
}

export type PlanSelectionPayload = {
  option_id: string
}

export type PlanConfirmationPayload = {
  confirmed: true
  option_id: string
}

export type InvitationRecord = InvitationCreatePayload & {
  planning_mode: InvitationPlanningMode
  id: string
  server_now: string
  publication_status: InvitationPublicationStatus
  published_at: string | null
  response_status: InvitationResponseStatus
  responded_at: string | null
  screens: InvitationScreenRecord[]
  plan_options: InvitationPlanOption[]
  selected_option_id: string | null
  selected_at: string | null
  confirmed_at: string | null
  created_at: string
  updated_at: string
}

export type InvitationCreateResponse = InvitationRecord & {
  management_token: string
}

export type InvitationField = keyof InvitationEditForm

export type InvitationValidationErrors = Partial<Record<InvitationField, string>>

export type InvitationResponsePayload = {
  response_status: FinalInvitationResponseStatus
}
