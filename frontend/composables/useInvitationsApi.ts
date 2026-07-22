import type {
  InvitationCreatePayload,
  InvitationCreateResponse,
  InvitationRecord,
} from '../types/invitation'

export function useInvitationsApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBaseUrl

  function createInvitation(payload: InvitationCreatePayload): Promise<InvitationCreateResponse> {
    return $fetch<InvitationCreateResponse>('/api/v1/invitations/', {
      baseURL,
      method: 'POST',
      body: payload,
    })
  }

  function getPublicInvitation(id: string): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(`/api/v1/invitations/${encodeURIComponent(id)}/`, {
      baseURL,
    })
  }

  function getManagedInvitation(id: string, token: string): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/manage/`,
      {
        baseURL,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )
  }

  return {
    createInvitation,
    getManagedInvitation,
    getPublicInvitation,
  }
}
