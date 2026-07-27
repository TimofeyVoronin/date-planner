import type { InvitationImageKey } from './invitation-image'

export const INVITATION_SCREEN_TYPES = [
  'invitation',
  'acceptance',
  'date_selection',
  'activity_selection',
  'final',
] as const

export const INVITATION_SCREEN_TITLE_MAX_LENGTH = 160
export const INVITATION_SCREEN_SUBTITLE_MAX_LENGTH = 500
export const INVITATION_SCREEN_BUTTON_MAX_LENGTH = 80

export type InvitationScreenType = typeof INVITATION_SCREEN_TYPES[number]

export type InvitationScreenRecord = {
  screen_type: InvitationScreenType
  title: string
  subtitle: string
  button_text: string
  secondary_button_text: string
  image_key: InvitationImageKey
  template_text: string
}

export type InvitationScreenEditForm = Pick<
  InvitationScreenRecord,
  | 'title'
  | 'subtitle'
  | 'button_text'
  | 'secondary_button_text'
  | 'image_key'
  | 'template_text'
>

export type InvitationScreenUpdatePayload = Partial<InvitationScreenEditForm>
export type InvitationScreenEditableField = keyof InvitationScreenEditForm
export type InvitationScreenValidationErrors = Partial<
  Record<InvitationScreenEditableField, string>
>

export type FinalScreenUpdatePayload = Partial<Pick<
  InvitationScreenRecord,
  'title' | 'subtitle' | 'image_key' | 'template_text'
>>

export type FinalTemplateUpdatePayload = Pick<FinalScreenUpdatePayload, 'template_text'>
