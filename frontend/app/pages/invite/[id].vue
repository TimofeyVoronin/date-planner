<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import ActivityOptionSelector from '../../../components/activities/ActivityOptionSelector.vue'
import InvitationPreviewCard from '../../../components/invitation/InvitationPreviewCard.vue'
import PublicDeclinedCard from '../../../components/invitation/PublicDeclinedCard.vue'
import PublicFlowProgress from '../../../components/invitation/PublicFlowProgress.vue'
import PublicResumeNotice from '../../../components/invitation/PublicResumeNotice.vue'
import PublicWaitingCard from '../../../components/invitation/PublicWaitingCard.vue'
import FinalPlanCard from '../../../components/planning/FinalPlanCard.vue'
import PlanOptionSelector from '../../../components/planning/PlanOptionSelector.vue'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import { useExpiryClock } from '../../../composables/useExpiryClock'
import type {
  FinalInvitationResponseStatus,
  InvitationRecord,
} from '../../../types/invitation'
import {
  findSelectedActivityOption,
  getPersistedActivitySelectionState,
  parseActivitySelectionApiError,
  refreshActivitySelectionAfterRejection,
} from '../../../utils/activities'
import {
  isFinalInvitationResponseStatus,
  isInvitationId,
  parseInvitationApiError,
  parseInvitationResponseApiError,
  refreshInvitationResponseAfterConflict,
} from '../../../utils/invitations'
import {
  canChangeDeclinedInvitationResponse,
  getPublicFlowTransitionKey,
  getPublicInvitationStage,
  getPublicResumeNotice,
  isPublicResponseStage,
  shouldRefreshPublicSnapshotOnResume,
  type PublicInvitationStage,
  type PublicResumeNotice as PublicResumeNoticeData,
} from '../../../utils/publicFlow'
import { getInvitationScreenByType } from '../../../utils/screens'
import {
  findUsableSelectedPlanOption,
  getPersistedPlanSelectionState,
  parsePlanningApiError,
  refreshPlanSelectionAfterRejection,
  shouldAnnounceNewFinalPlan,
} from '../../../utils/planning'

type PageState = 'error' | 'loading' | 'ready'
type ResponseSaveState = 'error' | 'idle' | 'saved' | 'saving'
type SelectionSaveState = 'error' | 'idle' | 'saved' | 'saving'
type ActivitySelectionSaveState = 'error' | 'idle' | 'saved' | 'saving'
type WaitingRefreshState = 'error' | 'idle' | 'loading'

const route = useRoute()
const api = useInvitationsApi()
const invitation = ref<InvitationRecord | null>(null)
const pageState = ref<PageState>('loading')
const errorMessage = ref('')
const isNotFound = ref(false)
const responseSaveState = ref<ResponseSaveState>('idle')
const responseSaveError = ref('')
const pendingResponse = ref<FinalInvitationResponseStatus | null>(null)
const savedDuringThisVisit = ref(false)
const selectedOptionId = ref<string | null>(null)
const selectionSaveState = ref<SelectionSaveState>('idle')
const selectionSaveError = ref('')
const selectedActivityOptionId = ref<string | null>(null)
const activitySelectionSaveState = ref<ActivitySelectionSaveState>('idle')
const activitySelectionSaveError = ref('')
const waitingRefreshState = ref<WaitingRefreshState>('idle')
const waitingRefreshError = ref('')
const showAcceptanceTransition = ref(false)
const announceFinalPlan = ref(false)
const announceFinalPlanOnNextSnapshot = ref(false)
const resumeNotice = ref<PublicResumeNoticeData | null>(null)
const resumeRefreshError = ref('')
const stagePanelRef = ref<HTMLElement | null>(null)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const { currentTime, refreshCurrentTime, synchronizeServerTime } = useExpiryClock()
let lastSnapshotReceivedAt: number | null = null
let resumeRefreshInFlight = false
const invitationScreen = computed(() => (
  getInvitationScreenByType(invitation.value?.screens ?? [], 'invitation')
))
const acceptanceScreen = computed(() => (
  getInvitationScreenByType(invitation.value?.screens ?? [], 'acceptance')
))
const dateSelectionScreen = computed(() => (
  getInvitationScreenByType(invitation.value?.screens ?? [], 'date_selection')
))
const activitySelectionScreen = computed(() => (
  getInvitationScreenByType(invitation.value?.screens ?? [], 'activity_selection')
))
const hasActivityOptions = computed(() => (invitation.value?.activity_options.length ?? 0) > 0)
const serverStage = computed<PublicInvitationStage>(() => (
  invitation.value
    ? getPublicInvitationStage(invitation.value, currentTime.value)
    : 'invitation'
))
const activeStage = computed<PublicInvitationStage>(() => {
  if (
    showAcceptanceTransition.value
    && serverStage.value !== 'declined'
    && serverStage.value !== 'final'
  ) {
    return 'acceptance'
  }

  return serverStage.value
})
const stageTransitionKey = computed(() => getPublicFlowTransitionKey(activeStage.value))
const responseStage = computed(() => isPublicResponseStage(activeStage.value))
const canChangeDeclinedResponse = computed(() => (
  invitation.value ? canChangeDeclinedInvitationResponse(invitation.value) : false
))
const showResponseSaveStatus = computed(() => (
  responseStage.value
  || (
    activeStage.value === 'declined'
    && (savedDuringThisVisit.value || responseSaveState.value !== 'saved')
  )
))
const selectedPlanOption = computed(() => (
  findUsableSelectedPlanOption(
    invitation.value?.plan_options ?? [],
    invitation.value?.selected_option_id ?? null,
    currentTime.value,
  )
))
const selectedActivityOption = computed(() => (
  findSelectedActivityOption(
    invitation.value?.activity_options ?? [],
    invitation.value?.selected_activity_option_id ?? null,
  )
))
const continueDisabled = computed(() => (
  responseSaveState.value !== 'saved'
  || invitation.value?.response_status !== 'accepted'
))
const hasUnsavedPublicChoice = computed(() => (
  responseSaveState.value === 'saving'
  || selectionSaveState.value === 'saving'
  || activitySelectionSaveState.value === 'saving'
  || (
    activeStage.value === 'date_selection'
    && selectedOptionId.value !== (invitation.value?.selected_option_id ?? null)
  )
  || (
    activeStage.value === 'activity_selection'
    && selectedActivityOptionId.value
      !== (invitation.value?.selected_activity_option_id ?? null)
  )
))

useHead({
  title: 'Личное приглашение — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

function applyPersistedPlanSelection(nextInvitation: InvitationRecord): void {
  const selectionState = getPersistedPlanSelectionState(
    nextInvitation.plan_options,
    nextInvitation.selected_option_id,
    currentTime.value,
  )

  selectedOptionId.value = selectionState.selectedOptionId
  selectionSaveState.value = selectionState.isSaved ? 'saved' : 'idle'
  selectionSaveError.value = ''
}

function applyPersistedActivitySelection(nextInvitation: InvitationRecord): void {
  const selectionState = getPersistedActivitySelectionState(
    nextInvitation.activity_options,
    nextInvitation.selected_activity_option_id,
  )

  selectedActivityOptionId.value = selectionState.selectedOptionId
  activitySelectionSaveState.value = selectionState.isSaved ? 'saved' : 'idle'
  activitySelectionSaveError.value = ''
}

function applyPublicInvitationRecord(
  nextInvitation: InvitationRecord,
  announceNewFinalPlan = false,
): void {
  const previousConfirmedAt = invitation.value?.confirmed_at ?? null

  synchronizeServerTime(nextInvitation.server_now)
  invitation.value = nextInvitation
  applyPersistedPlanSelection(nextInvitation)
  applyPersistedActivitySelection(nextInvitation)
  announceFinalPlan.value = announceNewFinalPlan
    && shouldAnnounceNewFinalPlan(previousConfirmedAt, nextInvitation.confirmed_at)
}

function applyPublicInvitationSnapshot(
  nextInvitation: InvitationRecord,
  announceNewFinalPlan = false,
): void {
  const shouldAnnounceFinalPlan = announceNewFinalPlan
    || announceFinalPlanOnNextSnapshot.value

  applyPublicInvitationRecord(nextInvitation, shouldAnnounceFinalPlan)
  responseSaveState.value = isFinalInvitationResponseStatus(nextInvitation.response_status)
    ? 'saved'
    : 'idle'
  pendingResponse.value = null
  savedDuringThisVisit.value = false
  showAcceptanceTransition.value = false
  announceFinalPlanOnNextSnapshot.value = false
}

function markSnapshotReceived(): void {
  lastSnapshotReceivedAt = Date.now()
  resumeRefreshError.value = ''
}

function clearResumeNotice(): void {
  resumeNotice.value = null
}

function focusActiveStage(): void {
  void nextTick(() => stagePanelRef.value?.focus({ preventScroll: true }))
}

function showPublicSnapshotRefreshFailure(error: unknown): void {
  const parsedError = parseInvitationApiError(error)

  errorMessage.value = parsedError.status === 404
    ? parsedError.message
    : `Данные приглашения уже изменились, но не удалось загрузить актуальное состояние. ${parsedError.message}`
  isNotFound.value = parsedError.status === 404
  pageState.value = 'error'
}

async function loadInvitation(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  isNotFound.value = false

  if (!isInvitationId(invitationId.value)) {
    errorMessage.value = 'Приглашение не найдено или ссылка больше не действует.'
    isNotFound.value = true
    pageState.value = 'error'
    return
  }

  try {
    const nextInvitation = await api.getPublicInvitation(invitationId.value)

    applyPublicInvitationSnapshot(nextInvitation)
    resumeNotice.value = getPublicResumeNotice(nextInvitation, currentTime.value)
    markSnapshotReceived()
    pageState.value = 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    errorMessage.value = parsedError.message
    isNotFound.value = parsedError.status === 404
    pageState.value = 'error'
  }
}

async function saveResponse(status: FinalInvitationResponseStatus): Promise<void> {
  if (responseSaveState.value === 'saving') {
    return
  }

  clearResumeNotice()
  pendingResponse.value = status
  responseSaveError.value = ''
  responseSaveState.value = 'saving'
  showAcceptanceTransition.value = status === 'accepted' && Boolean(acceptanceScreen.value)

  try {
    const nextInvitation = await api.saveInvitationResponse(invitationId.value, {
      response_status: status,
    })

    applyPublicInvitationRecord(nextInvitation, true)
    markSnapshotReceived()
    savedDuringThisVisit.value = true
    responseSaveState.value = 'saved'

    if (status === 'declined') {
      showAcceptanceTransition.value = false
    }
  }
  catch (error: unknown) {
    const parsedError = parseInvitationResponseApiError(error)

    try {
      const nextInvitation = await refreshInvitationResponseAfterConflict(
        parsedError,
        () => api.getPublicInvitation(invitationId.value),
      )

      if (nextInvitation) {
        applyPublicInvitationSnapshot(nextInvitation, true)
        return
      }
    }
    catch (refreshError: unknown) {
      responseSaveState.value = 'error'
      announceFinalPlanOnNextSnapshot.value = true
      showPublicSnapshotRefreshFailure(refreshError)
      return
    }

    responseSaveError.value = parsedError.message
    responseSaveState.value = 'error'
  }
}

function choosePlanOption(optionId: string): void {
  const selectedOption = findUsableSelectedPlanOption(
    invitation.value?.plan_options ?? [],
    optionId,
    refreshCurrentTime(),
  )

  if (!selectedOption) {
    selectedOptionId.value = null
    selectionSaveError.value = 'Время этого варианта уже прошло. Выбери другую актуальную дату.'
    selectionSaveState.value = 'error'
    return
  }

  selectedOptionId.value = optionId
  selectionSaveError.value = ''
  selectionSaveState.value = optionId === invitation.value?.selected_option_id
    ? 'saved'
    : 'idle'
}

async function savePlanSelection(): Promise<void> {
  if (!selectedOptionId.value || selectionSaveState.value === 'saving') {
    return
  }

  const selectedOption = findUsableSelectedPlanOption(
    invitation.value?.plan_options ?? [],
    selectedOptionId.value,
    refreshCurrentTime(),
  )

  if (!selectedOption) {
    selectedOptionId.value = null
    selectionSaveError.value = 'Время этого варианта уже прошло. Выбери другую актуальную дату.'
    selectionSaveState.value = 'error'
    return
  }

  clearResumeNotice()
  selectionSaveState.value = 'saving'
  selectionSaveError.value = ''

  try {
    const nextInvitation = await api.savePlanSelection(invitationId.value, {
      option_id: selectedOptionId.value,
    })

    applyPublicInvitationRecord(nextInvitation, true)
    markSnapshotReceived()
    focusActiveStage()
  }
  catch (error: unknown) {
    const parsedError = parsePlanningApiError(error, 'selection')

    try {
      const nextInvitation = await refreshPlanSelectionAfterRejection(
        parsedError,
        () => api.getPublicInvitation(invitationId.value),
      )

      if (nextInvitation) {
        applyPublicInvitationSnapshot(nextInvitation, true)
        focusActiveStage()
        return
      }
    }
    catch (refreshError: unknown) {
      selectionSaveState.value = 'error'
      announceFinalPlanOnNextSnapshot.value = true
      showPublicSnapshotRefreshFailure(refreshError)
      return
    }

    selectionSaveError.value = parsedError.message
    selectionSaveState.value = 'error'
  }
}

function chooseActivityOption(optionId: string): void {
  const selectedOption = findSelectedActivityOption(
    invitation.value?.activity_options ?? [],
    optionId,
  )

  if (!selectedOption) {
    selectedActivityOptionId.value = null
    activitySelectionSaveError.value = 'Эта активность больше недоступна. Выбери другой вариант.'
    activitySelectionSaveState.value = 'error'
    return
  }

  selectedActivityOptionId.value = selectedOption.id
  activitySelectionSaveError.value = ''
  activitySelectionSaveState.value = optionId === invitation.value?.selected_activity_option_id
    ? 'saved'
    : 'idle'
}

async function saveActivitySelection(): Promise<void> {
  if (!selectedActivityOptionId.value || activitySelectionSaveState.value === 'saving') {
    return
  }

  const selectedOption = findSelectedActivityOption(
    invitation.value?.activity_options ?? [],
    selectedActivityOptionId.value,
  )
  if (!selectedOption) {
    selectedActivityOptionId.value = null
    activitySelectionSaveError.value = 'Эта активность больше недоступна. Выбери другой вариант.'
    activitySelectionSaveState.value = 'error'
    return
  }

  clearResumeNotice()
  activitySelectionSaveState.value = 'saving'
  activitySelectionSaveError.value = ''

  try {
    const nextInvitation = await api.saveActivitySelection(invitationId.value, {
      option_id: selectedOption.id,
    })

    applyPublicInvitationRecord(nextInvitation, true)
    markSnapshotReceived()
    focusActiveStage()
  }
  catch (error: unknown) {
    const parsedError = parseActivitySelectionApiError(error)

    try {
      const nextInvitation = await refreshActivitySelectionAfterRejection(
        parsedError,
        () => api.getPublicInvitation(invitationId.value),
      )

      if (nextInvitation) {
        applyPublicInvitationSnapshot(nextInvitation, true)
        focusActiveStage()
        return
      }
    }
    catch (refreshError: unknown) {
      activitySelectionSaveState.value = 'error'
      announceFinalPlanOnNextSnapshot.value = true
      showPublicSnapshotRefreshFailure(refreshError)
      return
    }

    activitySelectionSaveError.value = parsedError.message
    activitySelectionSaveState.value = 'error'
  }
}

async function refreshWaitingStatus(): Promise<void> {
  if (waitingRefreshState.value === 'loading') {
    return
  }

  waitingRefreshState.value = 'loading'
  waitingRefreshError.value = ''

  try {
    const nextInvitation = await api.getPublicInvitation(invitationId.value)

    applyPublicInvitationSnapshot(nextInvitation, true)
    markSnapshotReceived()
    waitingRefreshState.value = 'idle'
    focusActiveStage()
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    waitingRefreshError.value = parsedError.message
    waitingRefreshState.value = 'error'
  }
}

async function refreshPublicSnapshotOnResume(force = false): Promise<void> {
  if (
    pageState.value !== 'ready'
    || resumeRefreshInFlight
    || (!force && hasUnsavedPublicChoice.value)
    || (!force && !shouldRefreshPublicSnapshotOnResume(lastSnapshotReceivedAt))
  ) {
    return
  }

  resumeRefreshInFlight = true

  try {
    const previousStage = serverStage.value
    const nextInvitation = await api.getPublicInvitation(invitationId.value)

    applyPublicInvitationSnapshot(nextInvitation, true)
    markSnapshotReceived()

    if (previousStage !== serverStage.value) {
      resumeNotice.value = getPublicResumeNotice(nextInvitation, currentTime.value)
      focusActiveStage()
    }
  }
  catch (error: unknown) {
    resumeRefreshError.value = parseInvitationApiError(error).message
  }
  finally {
    resumeRefreshInFlight = false
  }
}

function refreshWhenPageBecomesVisible(): void {
  refreshCurrentTime()

  if (document.visibilityState === 'visible') {
    void refreshPublicSnapshotOnResume()
  }
}

function refreshWhenWindowFocuses(): void {
  refreshCurrentTime()
  void refreshPublicSnapshotOnResume()
}

function retryResponseSave(): void {
  if (pendingResponse.value) {
    void saveResponse(pendingResponse.value)
  }
}

function continueToPlanning(): void {
  if (continueDisabled.value) {
    return
  }

  showAcceptanceTransition.value = false
  focusActiveStage()
}

watch(serverStage, (nextStage, previousStage) => {
  if (
    pageState.value === 'ready'
    && nextStage === 'date_selection'
    && (previousStage === 'activity_selection' || previousStage === 'awaiting_confirmation')
    && invitation.value
  ) {
    applyPersistedPlanSelection(invitation.value)
    resumeNotice.value = getPublicResumeNotice(invitation.value, currentTime.value)
    focusActiveStage()
  }
})

onMounted(() => {
  void loadInvitation()
  document.addEventListener('visibilitychange', refreshWhenPageBecomesVisible)
  window.addEventListener('focus', refreshWhenWindowFocuses)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', refreshWhenPageBecomesVisible)
  window.removeEventListener('focus', refreshWhenWindowFocuses)
})
</script>

<template>
  <main class="detail-page">
    <div class="background-heart background-heart--one" aria-hidden="true" />
    <div class="background-heart background-heart--two" aria-hidden="true" />

    <section class="detail-shell" aria-labelledby="invite-page-title">
      <NuxtLink class="brand-link" to="/" aria-label="Date Planner, перейти на главную">
        <img src="/images/envelope-heart.svg" alt="" width="46" height="40">
        <span>Date Planner</span>
      </NuxtLink>

      <div v-if="pageState === 'loading'" class="state-card" role="status" aria-live="polite">
        <span class="state-card__icon state-card__icon--loading" aria-hidden="true">♥</span>
        <h1 id="invite-page-title">Открываем приглашение…</h1>
        <p>Ещё мгновение.</p>
      </div>

      <div v-else-if="pageState === 'error'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">{{ isNotFound ? '💌' : '🌧️' }}</span>
        <h1 id="invite-page-title">
          {{ isNotFound ? 'Такого приглашения нет' : 'Не удалось открыть приглашение' }}
        </h1>
        <p>{{ errorMessage }}</p>
        <div class="state-card__actions">
          <button v-if="!isNotFound" type="button" @click="loadInvitation">
            Попробовать снова
          </button>
          <NuxtLink to="/">Создать новое</NuxtLink>
        </div>
      </div>

      <template v-else-if="invitation">
        <header class="detail-shell__heading">
          <p>Тебе пришло личное приглашение</p>
          <h1 id="invite-page-title">{{ invitation.recipient_name }}, это для тебя</h1>
        </header>

        <PublicResumeNotice
          v-if="resumeNotice"
          :notice="resumeNotice"
          @dismiss="clearResumeNotice"
        />

        <div v-if="resumeRefreshError" class="public-resume-refresh-error" role="alert">
          <span>{{ resumeRefreshError }}</span>
          <button type="button" @click="refreshPublicSnapshotOnResume(true)">
            Обновить состояние
          </button>
        </div>

        <PublicFlowProgress
          :has-activity-options="hasActivityOptions"
          :stage="activeStage"
        />

        <Transition name="public-flow-stage" mode="out-in">
          <div
            :key="stageTransitionKey"
            ref="stagePanelRef"
            class="public-flow-stage"
            tabindex="-1"
          >
            <InvitationPreviewCard
              v-if="responseStage"
              :acceptance-screen="acceptanceScreen"
              :allow-reset="false"
              :author-name="invitation.author_name"
              :continue-disabled="continueDisabled"
              :direct-decline="true"
              :initial-status="invitation.response_status"
              :message="invitation.message"
              :planning-context="true"
              :recipient-name="invitation.recipient_name"
              :screen="invitationScreen"
              @answered="saveResponse"
              @continue="continueToPlanning"
            />

            <PublicDeclinedCard
              v-else-if="activeStage === 'declined'"
              :can-change-decision="canChangeDeclinedResponse"
              :is-saving="responseSaveState === 'saving'"
              :recipient-name="invitation.recipient_name"
              @accept="saveResponse('accepted')"
            />

            <PlanOptionSelector
              v-else-if="activeStage === 'date_selection'"
              :current-time="currentTime"
              :model-value="selectedOptionId"
              :options="invitation.plan_options"
              :persisted-option-id="invitation.selected_option_id"
              :save-error="selectionSaveError"
              :save-state="selectionSaveState"
              :screen="dateSelectionScreen"
              @save="savePlanSelection"
              @update:model-value="choosePlanOption"
            />

            <ActivityOptionSelector
              v-else-if="activeStage === 'activity_selection'"
              :model-value="selectedActivityOptionId"
              :options="invitation.activity_options"
              :persisted-option-id="invitation.selected_activity_option_id"
              :save-error="activitySelectionSaveError"
              :save-state="activitySelectionSaveState"
              :screen="activitySelectionScreen"
              @save="saveActivitySelection"
              @update:model-value="chooseActivityOption"
            />

            <PublicWaitingCard
              v-else-if="activeStage === 'awaiting_confirmation' && selectedPlanOption"
              :activity="selectedActivityOption"
              :option="selectedPlanOption"
              :refresh-error="waitingRefreshError"
              :refresh-state="waitingRefreshState"
              @refresh="refreshWaitingStatus"
            />

            <template v-else-if="activeStage === 'final'">
              <FinalPlanCard
                v-if="invitation.confirmed_plan"
                :announce="announceFinalPlan"
                :plan="invitation.confirmed_plan"
              />
              <section v-else class="plan-data-error" role="alert">
                Итоговый план не удалось загрузить. Обнови страницу и попробуй снова.
              </section>
            </template>

            <section v-else class="plan-data-error" role="alert">
              Текущее состояние приглашения не удалось показать. Обнови страницу и попробуй снова.
            </section>

            <div
              v-if="showResponseSaveStatus && responseSaveState !== 'idle'"
              class="response-save-status"
              :class="`response-save-status--${responseSaveState}`"
              :role="responseSaveState === 'error' ? 'alert' : 'status'"
              aria-live="polite"
            >
              <span class="response-save-status__icon" aria-hidden="true">
                {{ responseSaveState === 'saving' ? '⏳' : responseSaveState === 'saved' ? '✓' : '!' }}
              </span>
              <div>
                <strong v-if="responseSaveState === 'saving'">Сохраняем твой ответ…</strong>
                <strong v-else-if="responseSaveState === 'saved'">
                  {{ savedDuringThisVisit ? 'Ответ сохранён' : 'Ответ уже сохранён' }}
                </strong>
                <strong v-else>Не удалось сохранить ответ</strong>
                <p v-if="responseSaveState === 'saving'">Не закрывай страницу ещё мгновение.</p>
                <p v-else-if="responseSaveState === 'saved'">
                  Автор приглашения увидит его на своей секретной странице.
                </p>
                <p v-else>{{ responseSaveError }}</p>
              </div>
              <button
                v-if="responseSaveState === 'error'"
                type="button"
                @click="retryResponseSave"
              >
                Повторить
              </button>
            </div>
          </div>
        </Transition>

        <p class="detail-shell__privacy">
          <span aria-hidden="true">🔒</span>
          Страница доступна только тем, у кого есть ссылка.
        </p>
      </template>
    </section>
  </main>
</template>
