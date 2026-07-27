import type {
  ActivityOptionsPayload,
  ActivityOptionRecord,
  ActivitySelectionPayload,
} from '../types/activity'
import type {
  InvitationCreatePayload,
  InvitationCreateResponse,
  InvitationRecord,
  InvitationResponsePayload,
  InvitationUpdatePayload,
  PlanConfirmationPayload,
  PlanOptionsPayload,
  PlanSelectionPayload,
} from '../types/invitation'
import type {
  FinalScreenUpdatePayload,
  FinalTemplateUpdatePayload,
  InvitationScreenRecord,
  InvitationScreenUpdatePayload,
} from '../types/screen'
import { normalizeActivityOptionsResponse } from '../utils/activities'
import { normalizeInvitationScreen, normalizeInvitationScreens } from '../utils/screens'

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

  function updateManagedInvitation(
    id: string,
    token: string,
    payload: InvitationUpdatePayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/manage/`,
      {
        baseURL,
        method: 'PATCH',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )
  }

  async function getInvitationScreens(
    id: string,
    token: string,
  ): Promise<InvitationScreenRecord[]> {
    const payload = await $fetch<unknown>(
      `/api/v1/invitations/${encodeURIComponent(id)}/screens/`,
      {
        baseURL,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    return normalizeInvitationScreens(payload)
  }

  async function updateInvitationScreen(
    id: string,
    token: string,
    screenType: 'acceptance' | 'invitation',
    payload: InvitationScreenUpdatePayload,
  ): Promise<InvitationScreenRecord> {
    const response = await $fetch<unknown>(
      `/api/v1/invitations/${encodeURIComponent(id)}/screens/${screenType}/`,
      {
        baseURL,
        method: 'PATCH',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    return normalizeInvitationScreen(response)
  }

  async function updateFinalScreen(
    id: string,
    token: string,
    payload: FinalScreenUpdatePayload,
  ): Promise<InvitationScreenRecord> {
    const response = await $fetch<unknown>(
      `/api/v1/invitations/${encodeURIComponent(id)}/screens/final/`,
      {
        baseURL,
        method: 'PATCH',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    return normalizeInvitationScreen(response)
  }

  function updateFinalTemplate(
    id: string,
    token: string,
    payload: FinalTemplateUpdatePayload,
  ): Promise<InvitationScreenRecord> {
    return updateFinalScreen(id, token, payload)
  }

  async function getActivityOptions(
    id: string,
    token: string,
  ): Promise<ActivityOptionRecord[]> {
    const response = await $fetch<unknown>(
      `/api/v1/invitations/${encodeURIComponent(id)}/activity-options/`,
      {
        baseURL,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    return normalizeActivityOptionsResponse(response)
  }

  async function saveActivityOptions(
    id: string,
    token: string,
    payload: ActivityOptionsPayload,
  ): Promise<ActivityOptionRecord[]> {
    const response = await $fetch<unknown>(
      `/api/v1/invitations/${encodeURIComponent(id)}/activity-options/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    return normalizeActivityOptionsResponse(response)
  }

  function publishInvitation(id: string, token: string): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/publish/`,
      {
        baseURL,
        method: 'PUT',
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

  function saveActivitySelection(
    id: string,
    payload: ActivitySelectionPayload,
  ): Promise<InvitationRecord> {
    return $fetch<InvitationRecord>(
      `/api/v1/invitations/${encodeURIComponent(id)}/activity-selection/`,
      {
        baseURL,
        method: 'PUT',
        body: payload,
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
    getActivityOptions,
    getInvitationScreens,
    getManagedInvitation,
    getPublicInvitation,
    publishInvitation,
    saveActivityOptions,
    saveActivitySelection,
    savePlanOptions,
    savePlanSelection,
    saveInvitationResponse,
    updateFinalScreen,
    updateFinalTemplate,
    updateInvitationScreen,
    updateManagedInvitation,
  }
}
