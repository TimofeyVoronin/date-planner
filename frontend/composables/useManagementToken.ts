import { ref, toValue, type MaybeRefOrGetter } from 'vue'
import {
  isManagementToken,
  managementTokenSessionKey,
  readManagementToken,
} from '../utils/invitations'

export function useManagementToken(invitationId: MaybeRefOrGetter<string>) {
  const managementToken = ref<string | null>(null)

  function clearManagementToken(): void {
    managementToken.value = null

    try {
      window.sessionStorage.removeItem(managementTokenSessionKey(toValue(invitationId)))
    }
    catch {
      // Storage can be unavailable in private browsing modes.
    }
  }

  function takeManagementToken(): string | null {
    const key = managementTokenSessionKey(toValue(invitationId))
    const hasHash = window.location.hash.length > 0
    const tokenFromHash = readManagementToken(window.location.hash)

    if (hasHash) {
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${window.location.search}`,
      )

      if (!tokenFromHash) {
        clearManagementToken()
        return null
      }

      managementToken.value = tokenFromHash

      try {
        window.sessionStorage.setItem(key, tokenFromHash)
      }
      catch {
        // The in-memory token still works when session storage is disabled.
      }

      return tokenFromHash
    }

    if (managementToken.value) {
      return managementToken.value
    }

    try {
      const storedToken = window.sessionStorage.getItem(key)

      if (storedToken && isManagementToken(storedToken)) {
        managementToken.value = storedToken
        return storedToken
      }

      if (storedToken) {
        window.sessionStorage.removeItem(key)
      }

      return null
    }
    catch {
      return null
    }
  }

  return {
    clearManagementToken,
    takeManagementToken,
  }
}
