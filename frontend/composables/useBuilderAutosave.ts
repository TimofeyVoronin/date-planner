import {
  computed,
  getCurrentScope,
  onScopeDispose,
  reactive,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'
import type {
  InvitationCreatePayload,
  InvitationRecord,
  InvitationUpdatePayload,
  InvitationValidationErrors,
} from '../types/invitation'
import {
  buildInvitationUpdatePayload,
  createInvitationEditForm,
  hasInvitationValidationErrors,
  invitationEditFormHasChanges,
  parseInvitationApiError,
  validateInvitationPayload,
  type InvitationApiError,
} from '../utils/invitations'

export const BUILDER_AUTOSAVE_DELAY_MS = 800

export type BuilderAutosaveStatus = 'dirty' | 'error' | 'idle' | 'saved' | 'saving'

export type BuilderAutosaveOptions = {
  debounceMs?: number
  onAuthorizationError?: (error: InvitationApiError) => void
  onSaved?: (invitation: InvitationRecord) => void
  save: (payload: InvitationUpdatePayload) => Promise<InvitationRecord>
}

export type BuilderAutosave = {
  dispose: () => void
  errorMessage: Ref<string>
  fieldErrors: Ref<InvitationValidationErrors>
  flush: () => Promise<boolean>
  form: InvitationCreatePayload
  hasUnsavedChanges: ComputedRef<boolean>
  isDirty: ComputedRef<boolean>
  resetFromInvitation: (invitation: InvitationRecord) => void
  retry: () => Promise<boolean>
  status: Ref<BuilderAutosaveStatus>
}

export function useBuilderAutosave(options: BuilderAutosaveOptions): BuilderAutosave {
  const debounceMs = options.debounceMs ?? BUILDER_AUTOSAVE_DELAY_MS
  const baseline = ref<InvitationRecord | null>(null)
  const form = reactive<InvitationCreatePayload>({
    author_name: '',
    recipient_name: '',
    message: '',
    creation_mode: 'extended',
  })
  const status = ref<BuilderAutosaveStatus>('idle')
  const errorMessage = ref('')
  const fieldErrors = ref<InvitationValidationErrors>({})
  const isInitialized = ref(false)
  const isDisposed = ref(false)
  const isDirty = computed(() => {
    if (!baseline.value || !isInitialized.value) {
      return false
    }

    return invitationEditFormHasChanges(form, baseline.value)
  })
  const hasUnsavedChanges = computed(() => isDirty.value || status.value === 'saving')

  let timer: ReturnType<typeof setTimeout> | null = null
  let activeRequest: Promise<boolean> | null = null
  let revision = 0
  let suppressFormWatcher = false

  function clearTimer(): void {
    if (timer === null) {
      return
    }

    clearTimeout(timer)
    timer = null
  }

  function clearFeedback(): void {
    errorMessage.value = ''
    fieldErrors.value = {}
  }

  function schedule(): void {
    clearTimer()

    if (!isDirty.value || isDisposed.value) {
      return
    }

    timer = setTimeout(() => {
      timer = null
      void flush()
    }, debounceMs)
  }

  function resetFromInvitation(invitation: InvitationRecord): void {
    clearTimer()
    revision += 1
    suppressFormWatcher = true
    baseline.value = invitation
    Object.assign(form, createInvitationEditForm(invitation))
    suppressFormWatcher = false
    isInitialized.value = true
    status.value = 'idle'
    clearFeedback()
  }

  async function startSave(): Promise<boolean> {
    const invitation = baseline.value

    if (!invitation || isDisposed.value) {
      return false
    }

    const validationErrors = validateInvitationPayload(form)

    if (hasInvitationValidationErrors(validationErrors)) {
      fieldErrors.value = validationErrors
      errorMessage.value = 'Проверь заполненные поля.'
      status.value = 'error'
      return false
    }

    const payload = buildInvitationUpdatePayload(form, invitation)

    if (Object.keys(payload).length === 0) {
      status.value = status.value === 'saved' ? 'saved' : 'idle'
      clearFeedback()
      return true
    }

    const requestRevision = revision
    status.value = 'saving'
    clearFeedback()

    const request = options.save(payload)
      .then((savedInvitation) => {
        if (isDisposed.value) {
          return false
        }

        baseline.value = savedInvitation
        options.onSaved?.(savedInvitation)

        if (revision === requestRevision) {
          suppressFormWatcher = true
          Object.assign(form, createInvitationEditForm(savedInvitation))
          suppressFormWatcher = false
          status.value = 'saved'
        }
        else {
          status.value = 'dirty'
        }

        clearFeedback()
        return true
      })
      .catch((error: unknown) => {
        if (isDisposed.value) {
          return false
        }

        const parsedError = parseInvitationApiError(error)

        errorMessage.value = parsedError.message
        fieldErrors.value = parsedError.fieldErrors
        status.value = 'error'

        if (parsedError.status === 401 || parsedError.status === 403) {
          options.onAuthorizationError?.(parsedError)
        }

        return false
      })

    activeRequest = request
    const saved = await request
    activeRequest = null

    if (saved && !isDisposed.value && isDirty.value) {
      return flush()
    }

    return saved && !isDirty.value
  }

  async function flush(): Promise<boolean> {
    clearTimer()

    if (isDisposed.value) {
      return false
    }

    if (activeRequest) {
      const saved = await activeRequest

      if (!saved || isDisposed.value) {
        return false
      }

      return isDirty.value ? flush() : true
    }

    return startSave()
  }

  function retry(): Promise<boolean> {
    clearFeedback()
    status.value = isDirty.value ? 'dirty' : 'idle'

    return flush()
  }

  function dispose(): void {
    clearTimer()
    revision += 1
    isDisposed.value = true
  }

  watch(
    form,
    () => {
      if (!isInitialized.value || isDisposed.value || suppressFormWatcher) {
        return
      }

      revision += 1
      clearFeedback()

      if (!isDirty.value) {
        clearTimer()
        status.value = 'idle'
        return
      }

      status.value = 'dirty'
      schedule()
    },
    { deep: true, flush: 'sync' },
  )

  if (getCurrentScope()) {
    onScopeDispose(dispose)
  }

  return {
    dispose,
    errorMessage,
    fieldErrors,
    flush,
    form,
    hasUnsavedChanges,
    isDirty,
    resetFromInvitation,
    retry,
    status,
  }
}
