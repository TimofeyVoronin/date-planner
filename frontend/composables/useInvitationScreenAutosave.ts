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
import type { BuilderAutosaveStatus } from './useBuilderAutosave'
import type {
  InvitationScreenEditForm,
  InvitationScreenRecord,
  InvitationScreenUpdatePayload,
  InvitationScreenValidationErrors,
} from '../types/screen'
import {
  buildInvitationScreenUpdatePayload,
  createInvitationScreenEditForm,
  hasInvitationScreenValidationErrors,
  invitationScreenEditFormHasChanges,
  parseInvitationScreenApiError,
  validateInvitationScreenEditForm,
  type InvitationScreenApiError,
} from '../utils/screens'

export const INVITATION_SCREEN_AUTOSAVE_DELAY_MS = 800

export type InvitationScreenAutosaveOptions = {
  debounceMs?: number
  onAuthorizationError?: (error: InvitationScreenApiError) => void
  onSaved?: (screen: InvitationScreenRecord) => void
  save: (payload: InvitationScreenUpdatePayload) => Promise<InvitationScreenRecord>
}

export type InvitationScreenAutosave = {
  dispose: () => void
  errorMessage: Ref<string>
  fieldErrors: Ref<InvitationScreenValidationErrors>
  flush: () => Promise<boolean>
  form: InvitationScreenEditForm
  hasUnsavedChanges: ComputedRef<boolean>
  isDirty: ComputedRef<boolean>
  resetFromScreen: (screen: InvitationScreenRecord) => void
  retry: () => Promise<boolean>
  status: Ref<BuilderAutosaveStatus>
}

export function useInvitationScreenAutosave(
  options: InvitationScreenAutosaveOptions,
): InvitationScreenAutosave {
  const debounceMs = options.debounceMs ?? INVITATION_SCREEN_AUTOSAVE_DELAY_MS
  const baseline = ref<InvitationScreenRecord | null>(null)
  const form = reactive<InvitationScreenEditForm>({
    title: '',
    subtitle: '',
    button_text: '',
    secondary_button_text: '',
    image_key: 'invitation-default',
    template_text: '',
  })
  const status = ref<BuilderAutosaveStatus>('idle')
  const errorMessage = ref('')
  const fieldErrors = ref<InvitationScreenValidationErrors>({})
  const isInitialized = ref(false)
  const isDisposed = ref(false)
  const isDirty = computed(() => {
    if (!baseline.value || !isInitialized.value) {
      return false
    }

    return invitationScreenEditFormHasChanges(form, baseline.value)
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

  function resetFromScreen(screen: InvitationScreenRecord): void {
    clearTimer()
    revision += 1
    suppressFormWatcher = true
    baseline.value = screen
    Object.assign(form, createInvitationScreenEditForm(screen))
    suppressFormWatcher = false
    isInitialized.value = true
    status.value = 'idle'
    clearFeedback()
  }

  async function startSave(): Promise<boolean> {
    const screen = baseline.value

    if (!screen || isDisposed.value) {
      return false
    }

    const validationErrors = validateInvitationScreenEditForm(
      form,
      screen.screen_type,
    )
    if (hasInvitationScreenValidationErrors(validationErrors, screen.screen_type)) {
      fieldErrors.value = validationErrors
      errorMessage.value = 'Проверь заполненные поля экрана.'
      status.value = 'error'
      return false
    }

    const payload = buildInvitationScreenUpdatePayload(form, screen)
    if (Object.keys(payload).length === 0) {
      status.value = status.value === 'saved' ? 'saved' : 'idle'
      clearFeedback()
      return true
    }

    const requestRevision = revision
    status.value = 'saving'
    clearFeedback()

    const request = options.save(payload)
      .then((savedScreen) => {
        if (isDisposed.value) {
          return false
        }

        baseline.value = savedScreen
        options.onSaved?.(savedScreen)

        if (revision === requestRevision) {
          suppressFormWatcher = true
          Object.assign(form, createInvitationScreenEditForm(savedScreen))
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

        const parsedError = parseInvitationScreenApiError(error)
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
    resetFromScreen,
    retry,
    status,
  }
}
