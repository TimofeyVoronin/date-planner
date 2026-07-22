export const INVITATION_NAME_MAX_LENGTH = 100
export const INVITATION_MESSAGE_MAX_LENGTH = 1000

export type InvitationCreatePayload = {
  author_name: string
  recipient_name: string
  message: string
}

export type InvitationRecord = InvitationCreatePayload & {
  id: string
  created_at: string
  updated_at: string
}

export type InvitationCreateResponse = InvitationRecord & {
  management_token: string
}

export type InvitationField = keyof InvitationCreatePayload

export type InvitationValidationErrors = Partial<Record<InvitationField, string>>
