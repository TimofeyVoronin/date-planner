import type {
  InvitationCreatePayload,
  InvitationCreateResponse,
  InvitationRecord,
  InvitationResponsePayload,
  PlanConfirmationPayload,
  PlanOptionsPayload,
  PlanSelectionPayload,
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

  function saveInvitationResponse(
    id: string,
    payload: InvitationResponsePayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/response/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
      },
    )
  }

  function savePlanOptions(
    id: string,
    token: string,
    payload: PlanOptionsPayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/plan-options/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )
  }

  function savePlanSelection(
    id: string,
    payload: PlanSelectionPayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/selection/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
      },
    )
  }

  function confirmPlan(
    id: string,
    token: string,
    payload: PlanConfirmationPayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/confirmation/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )
  }

  return {
    confirmPlan,
    createInvitation,
    getManagedInvitation,
    getPublicInvitation,
    savePlanOptions,
    savePlanSelection,
    saveInvitationResponse,
  }
}
