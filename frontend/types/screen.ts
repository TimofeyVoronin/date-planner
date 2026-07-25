import type { InvitationImageKey } from './invitation-image'

export const INVITATION_SCREEN_TYPES = [
  'invitation',
  'acceptance',
  'date_selection',
  'activity_selection',
  'final',
] as const

export type InvitationScreenType = typeof INVITATION_SCREEN_TYPES[number]

export type InvitationScreenRecord = {
  screen_type: InvitationScreenType
  title: string
  subtitle: string
  button_text: string
  image_key: InvitationImageKey
}
