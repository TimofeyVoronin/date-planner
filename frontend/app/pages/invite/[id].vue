<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import InvitationPreviewCard from '../../../components/invitation/InvitationPreviewCard.vue'
import FinalPlanCard from '../../../components/planning/FinalPlanCard.vue'
import PlanOptionSelector from '../../../components/planning/PlanOptionSelector.vue'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import { useExpiryClock } from '../../../composables/useExpiryClock'
import type {
  FinalInvitationResponseStatus,
  InvitationRecord,
} from '../../../types/invitation'
import {
  isFinalInvitationResponseStatus,
  isInvitationId,
  parseInvitationApiError,
  parseInvitationResponseApiError,
  refreshInvitationResponseAfterConflict,
} from '../../../utils/invitations'
import {
  findSelectedPlanOption,
  findUsableSelectedPlanOption,
  getPersistedPlanSelectionState,
  parsePlanningApiError,
  refreshPlanSelectionAfterRejection,
  shouldAnnounceNewFinalPlan,
} from '../../../utils/planning'

type PageState = 'error' | 'loading' | 'ready'
type ResponseSaveState = 'error' | 'idle' | 'saved' | 'saving'
type SelectionSaveState = 'error' | 'idle' | 'saved' | 'saving'

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
const announceFinalPlan = ref(false)
const announceFinalPlanOnNextSnapshot = ref(false)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const { currentTime, refreshCurrentTime, synchronizeServerTime } = useExpiryClock()
const selectedPlanOption = computed(() => findSelectedPlanOption(
  invitation.value?.plan_options ?? [],
  invitation.value?.selected_option_id ?? null,
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

function applyPublicInvitationRecord(
  nextInvitation: InvitationRecord,
  announceNewFinalPlan = false,
): void {
  const previousConfirmedAt = invitation.value?.confirmed_at ?? null

  synchronizeServerTime(nextInvitation.server_now)
  invitation.value = nextInvitation
  applyPersistedPlanSelection(nextInvitation)
  announceFinalPlan.value = announceNewFinalPlan
    && shouldAnnounceNewFinalPlan(previousConfirmedAt, nextInvitation.confirmed_at)
}

function applyPublicInvitationSnapshot(
  nextInvitation: InvitationRecord,
  announceNewFinalPlan = false,
): void {
  const shouldAnnounceNewFinalPlan = announceNewFinalPlan
    || announceFinalPlanOnNextSnapshot.value

  applyPublicInvitationRecord(nextInvitation, shouldAnnounceNewFinalPlan)
  responseSaveState.value = isFinalInvitationResponseStatus(nextInvitation.response_status)
    ? 'saved'
    : 'idle'
  pendingResponse.value = null
  savedDuringThisVisit.value = false
  announceFinalPlanOnNextSnapshot.value = false
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

  pendingResponse.value = status
  responseSaveError.value = ''
  responseSaveState.value = 'saving'

  try {
    const nextInvitation = await api.saveInvitationResponse(invitationId.value, {
      response_status: status,
    })

    applyPublicInvitationRecord(nextInvitation, true)
    savedDuringThisVisit.value = true
    responseSaveState.value = 'saved'
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
  const now = refreshCurrentTime()
  const selectedOption = findUsableSelectedPlanOption(
    invitation.value?.plan_options ?? [],
    optionId,
    now,
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

  selectionSaveState.value = 'saving'
  selectionSaveError.value = ''

  try {
    const nextInvitation = await api.savePlanSelection(invitationId.value, {
      option_id: selectedOptionId.value,
    })

    applyPublicInvitationRecord(nextInvitation, true)
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

function retryResponseSave(): void {
  if (pendingResponse.value) {
    void saveResponse(pendingResponse.value)
  }
}

onMounted(loadInvitation)
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
        <InvitationPreviewCard
          :allow-reset="false"
          :author-name="invitation.author_name"
          :initial-status="invitation.response_status"
          :message="invitation.message"
          :planning-context="true"
          :recipient-name="invitation.recipient_name"
          @answered="saveResponse"
        />
        <div
          v-if="responseSaveState !== 'idle'"
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

        <template v-if="invitation.confirmed_at">
          <FinalPlanCard
            v-if="selectedPlanOption"
            :announce="announceFinalPlan"
            :confirmed-at="invitation.confirmed_at"
            :option="selectedPlanOption"
          />
          <section v-else class="plan-data-error" role="alert">
            Итоговый план не удалось загрузить. Обнови страницу и попробуй снова.
          </section>
        </template>

        <section
          v-else-if="invitation.response_status === 'accepted'
            && invitation.plan_options.length === 0"
          class="plan-waiting"
          aria-labelledby="plan-waiting-title"
        >
          <span aria-hidden="true">🗓️</span>
          <div>
            <h2 id="plan-waiting-title">Ждём варианты от автора</h2>
            <p>Ответ уже сохранён. Здесь появятся даты и места, когда автор их предложит.</p>
          </div>
        </section>

        <PlanOptionSelector
          v-else-if="invitation.response_status === 'accepted'"
          :current-time="currentTime"
          :model-value="selectedOptionId"
          :options="invitation.plan_options"
          :persisted-option-id="invitation.selected_option_id"
          :save-error="selectionSaveError"
          :save-state="selectionSaveState"
          @save="savePlanSelection"
          @update:model-value="choosePlanOption"
        />
        <p class="detail-shell__privacy">
          <span aria-hidden="true">🔒</span>
          Страница доступна только тем, у кого есть ссылка.
        </p>
      </template>
    </section>
  </main>
</template>
