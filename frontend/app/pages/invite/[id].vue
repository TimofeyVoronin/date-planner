<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import InvitationPreviewCard from '../../../components/invitation/InvitationPreviewCard.vue'
import PlanOptionSelector from '../../../components/planning/PlanOptionSelector.vue'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import type {
  FinalInvitationResponseStatus,
  InvitationRecord,
} from '../../../types/invitation'
import {
  isFinalInvitationResponseStatus,
  isInvitationId,
  parseInvitationApiError,
  parseInvitationResponseApiError,
} from '../../../utils/invitations'
import { findSelectedPlanOption, parsePlanningApiError } from '../../../utils/planning'

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
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')

useHead({
  title: 'Личное приглашение — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

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
    invitation.value = await api.getPublicInvitation(invitationId.value)
    responseSaveState.value = isFinalInvitationResponseStatus(invitation.value.response_status)
      ? 'saved'
      : 'idle'
    savedDuringThisVisit.value = false
    selectedOptionId.value = findSelectedPlanOption(
      invitation.value.plan_options,
      invitation.value.selected_option_id,
    )?.id ?? null
    selectionSaveState.value = selectedOptionId.value ? 'saved' : 'idle'
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
    invitation.value = await api.saveInvitationResponse(invitationId.value, {
      response_status: status,
    })
    selectedOptionId.value = invitation.value.selected_option_id
    savedDuringThisVisit.value = true
    responseSaveState.value = 'saved'
  }
  catch (error: unknown) {
    responseSaveError.value = parseInvitationResponseApiError(error).message
    responseSaveState.value = 'error'
  }
}

function choosePlanOption(optionId: string): void {
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

  selectionSaveState.value = 'saving'
  selectionSaveError.value = ''

  try {
    invitation.value = await api.savePlanSelection(invitationId.value, {
      option_id: selectedOptionId.value,
    })
    selectedOptionId.value = invitation.value.selected_option_id
    selectionSaveState.value = 'saved'
  }
  catch (error: unknown) {
    selectionSaveError.value = parsePlanningApiError(error, 'selection').message
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

        <section
          v-if="invitation.response_status === 'accepted' && invitation.plan_options.length === 0"
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
