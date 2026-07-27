<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import ActivityOptionsEditor from '../../../../components/activities/ActivityOptionsEditor.vue'
import BuilderAcceptanceScreenEditor from '../../../../components/builder/BuilderAcceptanceScreenEditor.vue'
import BuilderFinalTemplateSummary from '../../../../components/builder/BuilderFinalTemplateSummary.vue'
import BuilderImageLibrary from '../../../../components/builder/BuilderImageLibrary.vue'
import BuilderInvitationScreenEditor from '../../../../components/builder/BuilderInvitationScreenEditor.vue'
import BuilderInvitationStep from '../../../../components/builder/BuilderInvitationStep.vue'
import BuilderMobilePreview from '../../../../components/builder/BuilderMobilePreview.vue'
import BuilderPlanningModeStep from '../../../../components/builder/BuilderPlanningModeStep.vue'
import BuilderScreenConfigSummary from '../../../../components/builder/BuilderScreenConfigSummary.vue'
import PlanOptionsEditor from '../../../../components/planning/PlanOptionsEditor.vue'
import { useBuilderAutosave } from '../../../../composables/useBuilderAutosave'
import { useExpiryClock } from '../../../../composables/useExpiryClock'
import { useInvitationScreenAutosave } from '../../../../composables/useInvitationScreenAutosave'
import { useInvitationsApi } from '../../../../composables/useInvitationsApi'
import { useManagementToken } from '../../../../composables/useManagementToken'
import type {
  ActivityOptionRecord,
  ActivityOptionsPayload,
} from '../../../../types/activity'
import type {
  BuilderPreviewScreen,
  BuilderPreviewScreenConfig,
} from '../../../../types/builder-preview'
import type {
  InvitationPlanOption,
  InvitationPlanningMode,
  InvitationRecord,
  PlanOptionsPayload,
} from '../../../../types/invitation'
import type { InvitationImageKey } from '../../../../types/invitation-image'
import type {
  InvitationScreenRecord,
  InvitationScreenType,
} from '../../../../types/screen'
import {
  buildBuilderPreviewActivityOptions,
  buildBuilderPreviewDateOptions,
} from '../../../../utils/builderPreview'
import {
  BUILDER_STEPS,
  builderStepSessionKey,
  getBuilderAccessBlock,
  getBuilderStepDefinition,
  getNextBuilderStep,
  getPreviousBuilderStep,
  parseBuilderStep,
  resolveBuilderStep,
  type BuilderAccessBlock,
  type BuilderStepNumber,
} from '../../../../utils/builder'
import {
  activityStepRequiresOptionSave,
  parseActivityOptionsApiError,
  type ActivityOptionDraft,
} from '../../../../utils/activities'
import {
  isInvitationId,
  parseInvitationApiError,
  type InvitationApiError,
} from '../../../../utils/invitations'
import {
  parsePlanOptionsApiError,
  planningModeChangeRemovesOptions,
  planningStepRequiresOptionSave,
  planOptionsPayloadHasExpiredDate,
  type PlanOptionDraft,
} from '../../../../utils/planning'
import {
  createInvitationScreenEditForm,
  getInvitationScreenByType,
  getInvitationScreensForBuilderStep,
} from '../../../../utils/screens'

type BuilderPageState = 'blocked' | 'error' | 'loading' | 'missing-token' | 'ready'

const route = useRoute()
const router = useRouter()
const api = useInvitationsApi()
const pageState = ref<BuilderPageState>('loading')
const invitation = ref<InvitationRecord | null>(null)
const screens = ref<InvitationScreenRecord[]>([])
const currentStep = ref<BuilderStepNumber>(1)
const accessBlock = ref<BuilderAccessBlock | null>(null)
const errorMessage = ref('')
const canRetry = ref(true)
const isStepNavigationReady = ref(false)
const builderPlanOptions = ref<InvitationPlanOption[]>([])
const previewPlanDrafts = ref<PlanOptionDraft[]>([])
const planSaveState = ref<'error' | 'idle' | 'saving' | 'success'>('idle')
const planSaveError = ref('')
const planEditorDirty = ref(false)
const planOptionsEditor = ref<InstanceType<typeof PlanOptionsEditor> | null>(null)
const builderActivityOptions = ref<ActivityOptionRecord[]>([])
const previewActivityDrafts = ref<ActivityOptionDraft[]>([])
const activitySaveState = ref<'error' | 'idle' | 'saving' | 'success'>('idle')
const activitySaveError = ref('')
const activityEditorDirty = ref(false)
const activityOptionsEditor = ref<InstanceType<typeof ActivityOptionsEditor> | null>(null)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const managementPath = computed(() => `/manage/${encodeURIComponent(invitationId.value)}`)
const { clearManagementToken, takeManagementToken } = useManagementToken(invitationId)
const { currentTime, refreshCurrentTime, synchronizeServerTime } = useExpiryClock()
const activeStep = computed(() => getBuilderStepDefinition(currentStep.value))
const previousStep = computed(() => getPreviousBuilderStep(currentStep.value))
const nextStep = computed(() => getNextBuilderStep(currentStep.value))
const activeScreens = computed(() => (
  getInvitationScreensForBuilderStep(screens.value, currentStep.value)
))
const activeScreenTypes = computed(() => (
  activeScreens.value.map(screen => screen.screen_type)
))
const primaryInvitationScreen = computed(() => (
  getInvitationScreenByType(screens.value, 'invitation')
))
const acceptanceInvitationScreen = computed(() => (
  getInvitationScreenByType(screens.value, 'acceptance')
))
const finalInvitationScreen = computed(() => (
  getInvitationScreenByType(screens.value, 'final')
))
const summaryScreens = computed(() => (
  currentStep.value === 1 ? [] : activeScreens.value
))
const blockedPresentation = computed(() => {
  if (accessBlock.value === 'quick-mode') {
    return {
      icon: '⚡',
      title: 'Для быстрого приглашения конструктор не нужен',
      description: 'Переключи приглашение в расширенный режим на странице управления, затем вернись сюда.',
      action: 'Открыть настройки приглашения',
    }
  }

  return {
    icon: '💌',
    title: 'Опубликованное приглашение уже закрыто для конструктора',
    description: 'Сейчас конструктор доступен только расширенному черновику до публикации.',
    action: 'Вернуться к управлению',
  }
})

const autosave = useBuilderAutosave({
  async save(payload) {
    const token = takeManagementToken()

    if (!token) {
      throw { statusCode: 401 }
    }

    return api.updateManagedInvitation(invitationId.value, token, payload)
  },
  onSaved(nextInvitation) {
    invitation.value = nextInvitation
    synchronizeServerTime(nextInvitation.server_now)
    accessBlock.value = getBuilderAccessBlock(nextInvitation)

    if (nextInvitation.planning_mode === 'after_acceptance') {
      builderPlanOptions.value = []
      previewPlanDrafts.value = []
      planEditorDirty.value = false
      planSaveState.value = 'idle'
      planSaveError.value = ''
    }

    if (accessBlock.value) {
      pageState.value = 'blocked'
    }
  },
  onAuthorizationError(error) {
    handleAuthorizationError(error)
  },
})

const planningModeModel = computed<InvitationPlanningMode>({
  get: () => autosave.form.planning_mode,
  set: (mode) => {
    if (planSaveState.value === 'saving') {
      return
    }

    const removesPreparedOptions = planningModeChangeRemovesOptions(
      autosave.form.planning_mode,
      mode,
      planEditorDirty.value,
      builderPlanOptions.value.length,
    )

    if (
      removesPreparedOptions
      && !window.confirm(
        'Подготовленные варианты будут удалены. Продолжить и добавлять даты после согласия?',
      )
    ) {
      return
    }

    autosave.form.planning_mode = mode
  },
})

function replaceSavedScreen(savedScreen: InvitationScreenRecord): void {
  screens.value = screens.value.map(screen => (
    screen.screen_type === savedScreen.screen_type ? savedScreen : screen
  ))
}

const invitationScreenAutosave = useInvitationScreenAutosave({
  async save(payload) {
    const token = takeManagementToken()

    if (!token) {
      throw { statusCode: 401 }
    }

    return api.updateInvitationScreen(
      invitationId.value,
      token,
      'invitation',
      payload,
    )
  },
  onSaved: replaceSavedScreen,
  onAuthorizationError(error) {
    handleAuthorizationError(error)
  },
})

const acceptanceScreenAutosave = useInvitationScreenAutosave({
  async save(payload) {
    const token = takeManagementToken()

    if (!token) {
      throw { statusCode: 401 }
    }

    return api.updateInvitationScreen(
      invitationId.value,
      token,
      'acceptance',
      payload,
    )
  },
  onSaved: replaceSavedScreen,
  onAuthorizationError(error) {
    handleAuthorizationError(error)
  },
})

const finalScreenAutosave = useInvitationScreenAutosave({
  async save(payload) {
    const token = takeManagementToken()

    if (!token) {
      throw { statusCode: 401 }
    }

    return api.updateFinalScreen(invitationId.value, token, payload)
  },
  onSaved: replaceSavedScreen,
  onAuthorizationError(error) {
    handleAuthorizationError(error)
  },
})

const selectedImageKeys = computed(() => ({
  invitation: invitationScreenAutosave.form.image_key,
  acceptance: acceptanceScreenAutosave.form.image_key,
  final: finalScreenAutosave.form.image_key,
}))

const previewScreens = computed<Record<BuilderPreviewScreen, BuilderPreviewScreenConfig> | null>(() => {
  const dateScreen = getInvitationScreenByType(screens.value, 'date_selection')
  const activityScreen = getInvitationScreenByType(screens.value, 'activity_selection')
  const finalScreen = getInvitationScreenByType(screens.value, 'final')

  if (!dateScreen || !activityScreen || !finalScreen) {
    return null
  }

  return {
    invitation: {
      title: invitationScreenAutosave.form.title,
      subtitle: invitationScreenAutosave.form.subtitle,
      button_text: invitationScreenAutosave.form.button_text,
      secondary_button_text: invitationScreenAutosave.form.secondary_button_text,
      image_key: invitationScreenAutosave.form.image_key,
      template_text: '',
    },
    acceptance: {
      title: acceptanceScreenAutosave.form.title,
      subtitle: acceptanceScreenAutosave.form.subtitle,
      button_text: acceptanceScreenAutosave.form.button_text,
      secondary_button_text: '',
      image_key: acceptanceScreenAutosave.form.image_key,
      template_text: '',
    },
    date_selection: {
      ...createInvitationScreenEditForm(dateScreen),
      template_text: dateScreen.template_text,
    },
    activity_selection: {
      ...createInvitationScreenEditForm(activityScreen),
      template_text: activityScreen.template_text,
    },
    final: {
      ...finalScreenAutosave.form,
    },
  }
})
const previewDateOptions = computed(() => (
  autosave.form.planning_mode === 'before_acceptance'
    ? buildBuilderPreviewDateOptions(previewPlanDrafts.value)
    : []
))
const previewActivityOptions = computed(() => (
  buildBuilderPreviewActivityOptions(previewActivityDrafts.value)
))
const combinedAutosaveStatus = computed(() => {
  const statuses = [
    autosave.status.value,
    invitationScreenAutosave.status.value,
    acceptanceScreenAutosave.status.value,
  ]

  if (currentStep.value === 2 && autosave.form.planning_mode === 'before_acceptance') {
    if (planSaveState.value === 'error') {
      statuses.push('error')
    }
    else if (planSaveState.value === 'saving') {
      statuses.push('saving')
    }
    else if (planEditorDirty.value) {
      statuses.push('dirty')
    }
    else if (planSaveState.value === 'success') {
      statuses.push('saved')
    }
  }

  if (currentStep.value === 3) {
    if (activitySaveState.value === 'error') {
      statuses.push('error')
    }
    else if (activitySaveState.value === 'saving') {
      statuses.push('saving')
    }
    else if (activityEditorDirty.value) {
      statuses.push('dirty')
    }
    else if (activitySaveState.value === 'success') {
      statuses.push('saved')
    }
  }

  if (currentStep.value === 4) {
    statuses.push(finalScreenAutosave.status.value)
  }

  if (statuses.includes('error')) {
    return 'error' as const
  }
  if (statuses.includes('saving')) {
    return 'saving' as const
  }
  if (statuses.includes('dirty')) {
    return 'dirty' as const
  }
  if (statuses.includes('saved')) {
    return 'saved' as const
  }

  return 'idle' as const
})

const hasUnsavedStepChanges = computed(() => (
  autosave.hasUnsavedChanges.value
  || invitationScreenAutosave.hasUnsavedChanges.value
  || acceptanceScreenAutosave.hasUnsavedChanges.value
  || (
    currentStep.value === 2
    && autosave.form.planning_mode === 'before_acceptance'
    && (planEditorDirty.value || planSaveState.value === 'saving')
  )
  || (
    currentStep.value === 3
    && (activityEditorDirty.value || activitySaveState.value === 'saving')
  )
  || (
    currentStep.value === 4
    && finalScreenAutosave.hasUnsavedChanges.value
  )
))

const autosavePresentation = computed(() => {
  switch (combinedAutosaveStatus.value) {
    case 'dirty':
      return { icon: '●', label: 'Изменения не сохранены', tone: 'dirty' }
    case 'saving':
      return { icon: '⏳', label: 'Сохранение…', tone: 'saving' }
    case 'saved':
      return { icon: '✓', label: 'Сохранено', tone: 'saved' }
    case 'error':
      return { icon: '!', label: 'Не удалось сохранить', tone: 'error' }
    default:
      return { icon: '✓', label: 'Все изменения сохранены', tone: 'idle' }
  }
})

useHead({
  title: 'Конструктор приглашения — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

function handleAuthorizationError(error: Pick<InvitationApiError, 'message' | 'status'>): void {
  clearManagementToken()
  canRetry.value = false
  errorMessage.value = error.message
  pageState.value = 'error'
}

function readStoredStep(): string | null {
  try {
    return window.sessionStorage.getItem(builderStepSessionKey(invitationId.value))
  }
  catch {
    return null
  }
}

function persistStep(step: BuilderStepNumber): void {
  try {
    window.sessionStorage.setItem(builderStepSessionKey(invitationId.value), String(step))
  }
  catch {
    // The URL still preserves the active step when session storage is unavailable.
  }
}

async function replaceStepQuery(step: BuilderStepNumber): Promise<void> {
  await router.replace({
    query: {
      ...route.query,
      step: String(step),
    },
  })
}

async function restoreStepNavigation(): Promise<void> {
  const queryStep = parseBuilderStep(route.query.step)
  const resolvedStep = resolveBuilderStep(route.query.step, readStoredStep())

  currentStep.value = resolvedStep
  persistStep(resolvedStep)

  if (queryStep !== resolvedStep || route.query.step !== String(resolvedStep)) {
    await replaceStepQuery(resolvedStep)
  }

  isStepNavigationReady.value = true
}

async function flushCurrentStep(requireCompleteStep = false): Promise<boolean> {
  if (!hasUnsavedStepChanges.value && !requireCompleteStep) {
    return true
  }

  if (currentStep.value === 1) {
    const primaryScreenSaved = await invitationScreenAutosave.flush()
    if (!primaryScreenSaved) {
      return false
    }

    const acceptanceScreenSaved = await acceptanceScreenAutosave.flush()
    if (!acceptanceScreenSaved) {
      return false
    }

    const invitationSaved = await autosave.flush()
    return invitationSaved && pageState.value === 'ready'
  }

  if (currentStep.value === 2) {
    if (autosave.hasUnsavedChanges.value) {
      const invitationSaved = await autosave.flush()
      if (!invitationSaved || pageState.value !== 'ready') {
        return false
      }
    }

    if (autosave.form.planning_mode === 'before_acceptance') {
      return flushPlanningOptions(requireCompleteStep)
    }
  }

  if (currentStep.value === 3) {
    return flushActivityOptions(requireCompleteStep)
  }

  if (currentStep.value === 4) {
    return finalScreenAutosave.flush()
  }

  return true
}

async function goToStep(step: BuilderStepNumber): Promise<void> {
  const requireCompleteStep = step > currentStep.value

  if (step === currentStep.value || !await flushCurrentStep(requireCompleteStep)) {
    return
  }

  persistStep(step)
  await replaceStepQuery(step)
}

async function goToPreviousStep(): Promise<void> {
  if (previousStep.value) {
    await goToStep(previousStep.value)
  }
}

async function goToNextStep(): Promise<void> {
  if (nextStep.value) {
    await goToStep(nextStep.value)
  }
}

async function finishBuilder(): Promise<void> {
  if (!await flushCurrentStep()) {
    return
  }

  await router.push(managementPath.value)
}

async function loadBuilder(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  canRetry.value = true
  invitation.value = null
  screens.value = []
  accessBlock.value = null
  builderPlanOptions.value = []
  previewPlanDrafts.value = []
  planEditorDirty.value = false
  planSaveState.value = 'idle'
  planSaveError.value = ''
  builderActivityOptions.value = []
  previewActivityDrafts.value = []
  activityEditorDirty.value = false
  activitySaveState.value = 'idle'
  activitySaveError.value = ''

  if (!isInvitationId(invitationId.value)) {
    errorMessage.value = 'Проверь адрес секретной ссылки.'
    pageState.value = 'error'
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  try {
    const nextInvitation = await api.getManagedInvitation(invitationId.value, token)
    const block = getBuilderAccessBlock(nextInvitation)

    invitation.value = nextInvitation
    synchronizeServerTime(nextInvitation.server_now)
    builderPlanOptions.value = nextInvitation.plan_options
    accessBlock.value = block

    if (block) {
      pageState.value = 'blocked'
      return
    }

    const [nextScreens, nextActivityOptions] = await Promise.all([
      api.getInvitationScreens(invitationId.value, token),
      api.getActivityOptions(invitationId.value, token),
    ])

    screens.value = nextScreens
    builderActivityOptions.value = nextActivityOptions
    autosave.resetFromInvitation(nextInvitation)

    const primaryScreen = getInvitationScreenByType(nextScreens, 'invitation')
    const acceptanceScreen = getInvitationScreenByType(nextScreens, 'acceptance')
    const finalScreen = getInvitationScreenByType(nextScreens, 'final')
    if (!primaryScreen || !acceptanceScreen || !finalScreen) {
      throw new Error('Сервер не вернул обязательные экраны приглашения.')
    }
    invitationScreenAutosave.resetFromScreen(primaryScreen)
    acceptanceScreenAutosave.resetFromScreen(acceptanceScreen)
    finalScreenAutosave.resetFromScreen(finalScreen)
    pageState.value = 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      handleAuthorizationError(parsedError)
      return
    }

    errorMessage.value = parsedError.message
    pageState.value = 'error'
  }
}

let activePlanSave: Promise<boolean> | null = null

function handlePlanDirtyChange(isDirty: boolean): void {
  planEditorDirty.value = isDirty
}

function handlePlanEdited(): void {
  planSaveState.value = 'idle'
  planSaveError.value = ''
}

function handlePlanDraftsChange(drafts: PlanOptionDraft[]): void {
  previewPlanDrafts.value = drafts
}

async function persistPlanningOptions(payload: PlanOptionsPayload): Promise<boolean> {
  if (activePlanSave) {
    return activePlanSave
  }

  if (planOptionsPayloadHasExpiredDate(payload, refreshCurrentTime())) {
    planSaveError.value = 'Одна из дат уже наступила. Обнови время и сохрани варианты снова.'
    planSaveState.value = 'error'
    return false
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return false
  }

  planSaveState.value = 'saving'
  planSaveError.value = ''

  const request = api.savePlanOptions(invitationId.value, token, payload)
    .then((nextInvitation) => {
      invitation.value = nextInvitation
      synchronizeServerTime(nextInvitation.server_now)
      builderPlanOptions.value = nextInvitation.plan_options
      planEditorDirty.value = false
      planSaveState.value = 'success'
      return true
    })
    .catch((error: unknown) => {
      const parsedError = parsePlanOptionsApiError(error)

      if (parsedError.status === 401 || parsedError.status === 403) {
        handleAuthorizationError(parsedError)
        return false
      }

      planSaveError.value = parsedError.message
      planSaveState.value = 'error'
      planOptionsEditor.value?.applyServerErrors(
        parsedError.formError,
        parsedError.optionErrors,
      )
      return false
    })

  activePlanSave = request

  try {
    return await request
  }
  finally {
    activePlanSave = null
  }
}

async function savePlanningOptionsAfterMode(payload: PlanOptionsPayload): Promise<void> {
  planSaveState.value = 'saving'
  planSaveError.value = ''

  if (autosave.hasUnsavedChanges.value) {
    const invitationSaved = await autosave.flush()
    if (!invitationSaved || pageState.value !== 'ready') {
      planSaveState.value = 'idle'
      return
    }
  }

  if (autosave.form.planning_mode === 'before_acceptance') {
    await persistPlanningOptions(payload)
    return
  }

  planSaveState.value = 'idle'
}

function savePlanningOptions(payload: PlanOptionsPayload): void {
  void savePlanningOptionsAfterMode(payload)
}

async function flushPlanningOptions(requireCompleteStep: boolean): Promise<boolean> {
  if (activePlanSave) {
    const saved = await activePlanSave
    if (!saved) {
      return false
    }
  }

  if (!planningStepRequiresOptionSave(
    planEditorDirty.value,
    builderPlanOptions.value.length,
    requireCompleteStep,
  )) {
    return true
  }

  const payload = planOptionsEditor.value?.preparePayload()
  return payload ? persistPlanningOptions(payload) : false
}

let activeActivitySave: Promise<boolean> | null = null

function handleActivityDirtyChange(isDirty: boolean): void {
  activityEditorDirty.value = isDirty
}

function handleActivityEdited(): void {
  activitySaveState.value = 'idle'
  activitySaveError.value = ''
}

function handleActivityDraftsChange(drafts: ActivityOptionDraft[]): void {
  previewActivityDrafts.value = drafts
}

async function persistActivityOptions(payload: ActivityOptionsPayload): Promise<boolean> {
  if (activeActivitySave) {
    return activeActivitySave
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return false
  }

  activitySaveState.value = 'saving'
  activitySaveError.value = ''

  const request = api.saveActivityOptions(invitationId.value, token, payload)
    .then((nextOptions) => {
      builderActivityOptions.value = nextOptions
      activityEditorDirty.value = false
      activitySaveState.value = 'success'
      return true
    })
    .catch((error: unknown) => {
      const parsedError = parseActivityOptionsApiError(error)

      if (parsedError.status === 401 || parsedError.status === 403) {
        handleAuthorizationError(parsedError)
        return false
      }

      activitySaveError.value = parsedError.message
      activitySaveState.value = 'error'
      activityOptionsEditor.value?.applyServerErrors(
        parsedError.formError,
        parsedError.optionErrors,
      )
      return false
    })

  activeActivitySave = request

  try {
    return await request
  }
  finally {
    activeActivitySave = null
  }
}

function saveActivityOptions(payload: ActivityOptionsPayload): void {
  void persistActivityOptions(payload)
}

async function flushActivityOptions(requireCompleteStep: boolean): Promise<boolean> {
  if (activeActivitySave) {
    const saved = await activeActivitySave
    if (!saved) {
      return false
    }
  }

  if (!activityStepRequiresOptionSave(
    activityEditorDirty.value,
    builderActivityOptions.value.length,
    requireCompleteStep,
  )) {
    return true
  }

  const payload = activityOptionsEditor.value?.preparePayload()
  return payload ? persistActivityOptions(payload) : false
}

function selectScreenImage(
  screenType: InvitationScreenType,
  imageKey: InvitationImageKey,
): void {
  if (screenType === 'acceptance') {
    acceptanceScreenAutosave.form.image_key = imageKey
    return
  }

  if (screenType === 'invitation') {
    invitationScreenAutosave.form.image_key = imageKey
    return
  }

  if (screenType === 'final') {
    finalScreenAutosave.form.image_key = imageKey
  }
}

function warnBeforeUnload(event: BeforeUnloadEvent): void {
  if (!hasUnsavedStepChanges.value) {
    return
  }

  event.preventDefault()
  event.returnValue = ''
}

watch(
  () => route.query.step,
  (value) => {
    if (!isStepNavigationReady.value) {
      return
    }

    const parsedStep = parseBuilderStep(value)

    if (parsedStep) {
      currentStep.value = parsedStep
      persistStep(parsedStep)
      return
    }

    void replaceStepQuery(currentStep.value)
  },
)

onBeforeRouteUpdate(async (to) => {
  const destinationStep = parseBuilderStep(to.query.step)

  if (
    destinationStep
    && destinationStep !== currentStep.value
    && !await flushCurrentStep(destinationStep > currentStep.value)
  ) {
    return false
  }

  return true
})

onBeforeRouteLeave(async () => {
  if (!hasUnsavedStepChanges.value) {
    return true
  }

  if (await flushCurrentStep()) {
    return true
  }

  return window.confirm(
    'Не удалось сохранить последние изменения. Покинуть конструктор и потерять их?',
  )
})

onMounted(async () => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  await restoreStepNavigation()
  await loadBuilder()
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', warnBeforeUnload)
  autosave.dispose()
  invitationScreenAutosave.dispose()
  acceptanceScreenAutosave.dispose()
  finalScreenAutosave.dispose()
})
</script>

<template>
  <main class="detail-page detail-page--builder">
    <section class="builder-shell" aria-labelledby="builder-page-title">
      <div class="builder-shell__topbar">
        <NuxtLink class="brand-link" to="/" aria-label="Date Planner, перейти на главную">
          <img src="/images/envelope-heart.svg" alt="" width="46" height="40">
          <span>Date Planner</span>
        </NuxtLink>
        <NuxtLink class="builder-shell__manage-link" :to="managementPath">
          ← К управлению
        </NuxtLink>
      </div>

      <div v-if="pageState === 'loading'" class="state-card" role="status" aria-live="polite">
        <span class="state-card__icon state-card__icon--loading" aria-hidden="true">♥</span>
        <h1 id="builder-page-title">Открываем конструктор…</h1>
        <p>Проверяем черновик и секретный доступ автора.</p>
      </div>

      <div v-else-if="pageState === 'missing-token'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔑</span>
        <h1 id="builder-page-title">В этой вкладке нет секретного ключа</h1>
        <p>
          Сначала открой полную секретную ссылку автора. После этого перейти в конструктор можно со
          страницы управления.
        </p>
        <NuxtLink to="/">Вернуться на главную</NuxtLink>
      </div>

      <div v-else-if="pageState === 'error'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔐</span>
        <h1 id="builder-page-title">Конструктор недоступен</h1>
        <p>{{ errorMessage }}</p>
        <div class="state-card__actions">
          <button v-if="canRetry" type="button" @click="loadBuilder">
            Попробовать снова
          </button>
          <NuxtLink to="/">На главную</NuxtLink>
        </div>
      </div>

      <div v-else-if="pageState === 'blocked'" class="state-card" role="status">
        <span class="state-card__icon" aria-hidden="true">{{ blockedPresentation.icon }}</span>
        <h1 id="builder-page-title">{{ blockedPresentation.title }}</h1>
        <p>{{ blockedPresentation.description }}</p>
        <NuxtLink :to="managementPath">{{ blockedPresentation.action }}</NuxtLink>
      </div>

      <template v-else-if="invitation">
        <header class="builder-shell__heading">
          <p>Расширенный черновик</p>
          <h1 id="builder-page-title">Конструктор приглашения</h1>
          <span>
            {{ invitation.author_name }}, настрой сценарий для {{ invitation.recipient_name }}.
            Изменения конструктора сохраняются автоматически.
          </span>
        </header>

        <nav class="builder-progress" aria-label="Шаги конструктора">
          <ol>
            <li
              v-for="step in BUILDER_STEPS"
              :key="step.id"
              :class="{
                'builder-progress__item--active': step.number === currentStep,
                'builder-progress__item--visited': step.number < currentStep,
              }"
            >
              <button
                type="button"
                :aria-current="step.number === currentStep ? 'step' : undefined"
                :aria-label="`Шаг ${step.number}: ${step.label}`"
                @click="goToStep(step.number)"
              >
                <span aria-hidden="true">{{ step.number }}</span>
                <strong>{{ step.label }}</strong>
              </button>
            </li>
          </ol>
        </nav>

        <article class="builder-stage" :aria-labelledby="`builder-step-${activeStep.id}`">
          <div class="builder-stage__illustration" aria-hidden="true">
            {{ activeStep.icon }}
          </div>
          <div class="builder-stage__copy">
            <p>Шаг {{ currentStep }} из {{ BUILDER_STEPS.length }}</p>
            <h2 :id="`builder-step-${activeStep.id}`">{{ activeStep.label }}</h2>
            <span>{{ activeStep.description }}</span>
          </div>

          <div class="builder-stage__workspace">
            <div class="builder-stage__content">
              <template v-if="currentStep === 1">
                <BuilderInvitationStep
                  v-model:author-name="autosave.form.author_name"
                  v-model:recipient-name="autosave.form.recipient_name"
                  v-model:message="autosave.form.message"
                  v-model:creation-mode="autosave.form.creation_mode"
                  :status="autosave.status.value"
                  :error-message="autosave.errorMessage.value"
                  :field-errors="autosave.fieldErrors.value"
                  :is-dirty="autosave.isDirty.value"
                  @retry="autosave.retry()"
                  @save-now="autosave.flush()"
                />
                <BuilderInvitationScreenEditor
                  v-if="primaryInvitationScreen"
                  v-model:title="invitationScreenAutosave.form.title"
                  v-model:subtitle="invitationScreenAutosave.form.subtitle"
                  v-model:button-text="invitationScreenAutosave.form.button_text"
                  v-model:secondary-button-text="invitationScreenAutosave.form.secondary_button_text"
                  :status="invitationScreenAutosave.status.value"
                  :error-message="invitationScreenAutosave.errorMessage.value"
                  :field-errors="invitationScreenAutosave.fieldErrors.value"
                  :is-dirty="invitationScreenAutosave.isDirty.value"
                  @retry="invitationScreenAutosave.retry()"
                  @save-now="invitationScreenAutosave.flush()"
                />
                <BuilderAcceptanceScreenEditor
                  v-if="acceptanceInvitationScreen"
                  v-model:title="acceptanceScreenAutosave.form.title"
                  v-model:subtitle="acceptanceScreenAutosave.form.subtitle"
                  v-model:button-text="acceptanceScreenAutosave.form.button_text"
                  :status="acceptanceScreenAutosave.status.value"
                  :error-message="acceptanceScreenAutosave.errorMessage.value"
                  :field-errors="acceptanceScreenAutosave.fieldErrors.value"
                  :is-dirty="acceptanceScreenAutosave.isDirty.value"
                  @retry="acceptanceScreenAutosave.retry()"
                  @save-now="acceptanceScreenAutosave.flush()"
                />
              </template>

              <template v-else-if="currentStep === 2">
                <BuilderPlanningModeStep
                  v-model:planning-mode="planningModeModel"
                  :status="autosave.status.value"
                  :error-message="autosave.errorMessage.value"
                  :field-errors="autosave.fieldErrors.value"
                  :is-dirty="autosave.isDirty.value"
                  @retry="autosave.retry()"
                  @save-now="autosave.flush()"
                />
                <PlanOptionsEditor
                  v-if="autosave.form.planning_mode === 'before_acceptance'"
                  ref="planOptionsEditor"
                  variant="builder"
                  :current-time="currentTime"
                  :options="builderPlanOptions"
                  :save-error="planSaveError"
                  :save-state="planSaveState"
                  @dirty-change="handlePlanDirtyChange"
                  @drafts-change="handlePlanDraftsChange"
                  @edited="handlePlanEdited"
                  @save="savePlanningOptions"
                />
                <section
                  v-else
                  class="builder-date-later"
                  aria-labelledby="builder-date-later-title"
                >
                  <span class="builder-date-later__icon" aria-hidden="true">💬</span>
                  <div>
                    <p>После ответа получателя</p>
                    <h3 id="builder-date-later-title">Даты пока добавлять не нужно</h3>
                    <p>
                      Опубликуй приглашение без вариантов. Когда получатель ответит «Да»,
                      редактор появится на секретной странице управления.
                    </p>
                    <p>
                      Такой сценарий не создаёт скрытых черновых дат и сохраняет прежний
                      порядок согласования.
                    </p>
                  </div>
                </section>
              </template>

              <template v-else-if="currentStep === 3">
                <ActivityOptionsEditor
                  ref="activityOptionsEditor"
                  :options="builderActivityOptions"
                  :save-error="activitySaveError"
                  :save-state="activitySaveState"
                  @dirty-change="handleActivityDirtyChange"
                  @drafts-change="handleActivityDraftsChange"
                  @edited="handleActivityEdited"
                  @save="saveActivityOptions"
                />
                <BuilderScreenConfigSummary :screens="summaryScreens" />
              </template>

              <template v-else>
                <BuilderFinalTemplateSummary
                  v-if="finalInvitationScreen"
                  v-model:title="finalScreenAutosave.form.title"
                  v-model:subtitle="finalScreenAutosave.form.subtitle"
                  v-model:template-text="finalScreenAutosave.form.template_text"
                  :status="finalScreenAutosave.status.value"
                  :error-message="finalScreenAutosave.errorMessage.value"
                  :field-errors="finalScreenAutosave.fieldErrors.value"
                  :is-dirty="finalScreenAutosave.isDirty.value"
                  @retry="finalScreenAutosave.retry()"
                  @save-now="finalScreenAutosave.flush()"
                />
              </template>

              <BuilderImageLibrary
                v-if="currentStep !== 3"
                :editable-screen-types="currentStep === 1
                  ? ['invitation', 'acceptance']
                  : currentStep === 4
                    ? ['final']
                    : []"
                :screen-types="activeScreenTypes"
                :selected-image-keys="currentStep === 1 || currentStep === 4
                  ? selectedImageKeys
                  : {}"
                @select-image="selectScreenImage"
              />
            </div>

            <BuilderMobilePreview
              v-if="previewScreens"
              :activity-options="previewActivityOptions"
              :author-name="autosave.form.author_name"
              :builder-step="currentStep"
              :date-options="previewDateOptions"
              :message="autosave.form.message"
              :recipient-name="autosave.form.recipient_name"
              :screens="previewScreens"
            />
          </div>
        </article>

        <footer class="builder-actions" aria-label="Навигация по конструктору">
          <button
            type="button"
            class="builder-actions__secondary"
            :disabled="previousStep === null || combinedAutosaveStatus === 'saving'"
            @click="goToPreviousStep"
          >
            ← Назад
          </button>
          <div
            class="builder-actions__status"
            :class="`builder-actions__status--${autosavePresentation.tone}`"
            role="status"
            aria-live="polite"
          >
            <strong>Шаг {{ currentStep }} из {{ BUILDER_STEPS.length }}</strong>
            <span>{{ autosavePresentation.label }}</span>
          </div>
          <button
            v-if="nextStep"
            type="button"
            class="builder-actions__primary"
            :disabled="combinedAutosaveStatus === 'saving'"
            @click="goToNextStep"
          >
            Далее →
          </button>
          <button
            v-else
            type="button"
            class="builder-actions__primary"
            :disabled="combinedAutosaveStatus === 'saving'"
            @click="finishBuilder"
          >
            Завершить обзор
          </button>
        </footer>
      </template>
    </section>
  </main>
</template>
