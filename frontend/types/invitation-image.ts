import type { InvitationScreenType } from './screen'

export const INVITATION_IMAGE_KEYS = [
  'invitation-default',
  'invitation-starlight',
  'invitation-flowers',
  'invitation-moon',
  'acceptance-default',
  'acceptance-balloons',
  'acceptance-fireworks',
  'acceptance-together',
  'date-selection-default',
  'date-sunset',
  'date-weekend',
  'activity-selection-default',
  'activity-coffee',
  'activity-movie',
  'final-default',
  'final-toast',
  'final-night',
  'final-route',
] as const

export type InvitationImageKey = typeof INVITATION_IMAGE_KEYS[number]

export type InvitationImageRecord = {
  key: InvitationImageKey
  label: string
  description: string
  altText: string
  assetPath: string
  screenType: InvitationScreenType
}
