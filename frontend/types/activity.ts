import type { InvitationImageKey } from './invitation-image'

export const MIN_ACTIVITY_OPTIONS = 3
export const MAX_ACTIVITY_OPTIONS = 6
export const ACTIVITY_OPTION_TITLE_MAX_LENGTH = 120
export const ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH = 500
export const ACTIVITY_OPTION_PLACE_MAX_LENGTH = 200
export const ACTIVITY_OPTION_IMAGE_KEYS = [
  'activity-selection-default',
  'activity-coffee',
  'activity-movie',
] as const satisfies readonly InvitationImageKey[]

export type ActivityOptionImageKey = typeof ACTIVITY_OPTION_IMAGE_KEYS[number]

export type ActivityOptionRecord = {
  id: string
  title: string
  description: string
  image_key: string
  place: string
  position: number
}

export type ActivityOptionPayload = {
  title: string
  description: string
  image_key: ActivityOptionImageKey
  place: string
}

export type ActivityOptionsPayload = {
  options: ActivityOptionPayload[]
}


export type ActivitySelectionPayload = {
  option_id: string
}
