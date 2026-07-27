import type { InvitationImageKey } from './invitation-image'
import type { InvitationScreenEditForm } from './screen'

import type { BuilderStepNumber } from '../utils/builder'

export const BUILDER_PREVIEW_SCREENS = [
  'invitation',
  'acceptance',
  'date_selection',
  'activity_selection',
  'final',
] as const

export const BUILDER_PREVIEW_DEVICE_IDS = ['compact', 'regular', 'large'] as const

export type BuilderPreviewScreen = typeof BUILDER_PREVIEW_SCREENS[number]
export type BuilderPreviewDeviceId = typeof BUILDER_PREVIEW_DEVICE_IDS[number]

export type BuilderPreviewScreenDefinition = {
  builderStep: BuilderStepNumber
  icon: string
  label: string
  screen: BuilderPreviewScreen
}

export type BuilderPreviewDevice = {
  id: BuilderPreviewDeviceId
  label: string
  width: 320 | 375 | 430
}

export type BuilderPreviewDemoOption = {
  description: string
  id: string
  imageKey?: InvitationImageKey
  label: string
}

export type BuilderPreviewNoButtonTransform = {
  scale: number
  x: number
  y: number
}

export type BuilderPreviewScreenConfig = InvitationScreenEditForm & {
  template_text: string
}
