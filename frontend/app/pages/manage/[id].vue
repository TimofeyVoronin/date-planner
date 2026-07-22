<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import FinalPlanCard from '../../../components/planning/FinalPlanCard.vue'
import PlanOptionsEditor from '../../../components/planning/PlanOptionsEditor.vue'
import { copyTextWithFallback } from '../../../composables/useClipboard'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import { useManagementToken } from '../../../composables/useManagementToken'
import { useExpiryClock } from '../../../composables/useExpiryClock'
import type { InvitationRecord, PlanOptionsPayload } from '../../../types/invitation'
import {
  buildPublicInvitationUrl,
  getInvitationCreationModePresentation,
  getInvitationPublicationPresentation,
  getInvitationResponsePresentation,
  isInvitationId,
  parseInvitationApiError,
} from '../../../utils/invitations'
import {
  buildPlanConfirmationPayload,
  findSelectedPlanOption,
  formatPlanOptionDate,
  getPlanConfirmationStage,
  parsePlanConfirmationApiError,
  parsePlanningApiError,
  planOptionsPayloadHasExpiredDate,
  reconcileServerExpiredSelectionId,
  shouldAnnounceNewFinalPlan,
} from '../../../utils/planning'

type PageState = 'error' | 'loading' | 'missing-token' | 'ready'
type StatusRefreshState = 'error' | 'idle' | 'loading' | 'success'
type PlanSaveState = 'error' | 'idle' | 'saving' | 'success'
type ConfirmationActionState = 'error' | 'idle' | 'saving'
type PublicationActionState = 'error' | 'idle' | 'publishing'

const route = useRoute()
const api = useInvitationsApi()
const invitation = ref<InvitationRecord | null>(null)
const publicUrl = ref('')
const pageState = ref<PageState>('loading')
const errorMessage = ref('')
const copyStatus = ref<'idle' | 'copied' | 'failed'>('idle')
const canRetry = ref(true)
const statusRefreshState = ref<StatusRefreshState>('idle')
const statusRefreshError = ref('')
const planSaveState = ref<PlanSaveState>('idle')
const planSaveError = ref('')
const confirmationActionState = ref<ConfirmationActionState>('idle')
const confirmationError = ref('')
const confirmationConflict = ref(false)
const confirmationJustCompleted = ref(false)
const publicationActionState = ref<PublicationActionState>('idle')
const publicationError = ref('')
const publicationJustCompleted = ref(false)
const serverExpiredSelectionId = ref<string | null>(null)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const { clearManagementToken, takeManagementToken } = useManagementToken(invitationId)
const { currentTime, refreshCurrentTime, synchronizeServerTime } = useExpiryClock()
const responsePresentation = computed(() => getInvitationResponsePresentation(
  invitation.value?.response_status ?? 'pending',
))
const creationModePresentation = computed(() => getInvitationCreationModePresentation(
  invitation.value?.creation_mode ?? 'quick',
))
const publicationPresentation = computed(() => getInvitationPublicationPresentation(
  invitation.value?.publication_status ?? 'draft',
))
const selectedPlanOption = computed(() => findSelectedPlanOption(
  invitation.value?.plan_options ?? [],
  invitation.value?.selected_option_id ?? null,
))
const confirmationStage = computed(() => getPlanConfirmationStage(
  invitation.value?.response_status ?? 'pending',
  selectedPlanOption.value,
  invitation.value?.confirmed_at ?? null,
  currentTime.value,
  serverExpiredSelectionId.value,
))

useHead({
  title: 'Управление приглашением — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

function applyManagedInvitation(nextInvitation: InvitationRecord): void {
  synchronizeServerTime(nextInvitation.server_now)
  serverExpiredSelectionId.value = reconcileServerExpiredSelectionId(
    serverExpiredSelectionId.value,
    nextInvitation.selected_option_id,
    nextInvitation.confirmed_at,
  )
  invitation.value = nextInvitation
}

async function loadManagedInvitation(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  canRetry.value = true

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

    applyManagedInvitation(nextInvitation)
    publicUrl.value = buildPublicInvitationUrl(window.location.origin, invitationId.value)
    planSaveState.value = 'idle'
    confirmationActionState.value = 'idle'
    confirmationError.value = ''
    confirmationConflict.value = false
    confirmationJustCompleted.value = false
    publicationActionState.value = 'idle'
    publicationError.value = ''
    publicationJustCompleted.value = false
    pageState.value = 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
    }

    errorMessage.value = parsedError.message
    pageState.value = 'error'
  }
}

async function publishDraft(): Promise<void> {
  if (
    publicationActionState.value === 'publishing'
    || invitation.value?.publication_status !== 'draft'
  ) {
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  publicationActionState.value = 'publishing'
  publicationError.value = ''
  publicationJustCompleted.value = false

  try {
    const nextInvitation = await api.publishInvitation(invitationId.value, token)

    applyManagedInvitation(nextInvitation)
    publicationActionState.value = 'idle'
    publicationJustCompleted.value = true
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
      errorMessage.value = parsedError.message
      pageState.value = 'error'
      return
    }

    publicationError.value = parsedError.message
    publicationActionState.value = 'error'
  }
}

async function refreshResponseStatus(): Promise<void> {
  if (
    statusRefreshState.value === 'loading'
    || confirmationActionState.value === 'saving'
  ) {
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  statusRefreshState.value = 'loading'
  statusRefreshError.value = ''

  try {
    const nextInvitation = await api.getManagedInvitation(invitationId.value, token)
    const announceNewFinalPlan = shouldAnnounceNewFinalPlan(
      invitation.value?.confirmed_at ?? null,
      nextInvitation.confirmed_at,
    )

    applyManagedInvitation(nextInvitation)
    statusRefreshState.value = 'success'
    planSaveState.value = 'idle'
    confirmationActionState.value = 'idle'
    confirmationError.value = ''
    confirmationConflict.value = false
    confirmationJustCompleted.value = announceNewFinalPlan
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
      errorMessage.value = parsedError.message
      pageState.value = 'error'
      return
    }

    statusRefreshError.value = parsedError.message
    statusRefreshState.value = 'error'
  }
}

async function confirmSelectedPlan(): Promise<void> {
  if (
    confirmationActionState.value === 'saving'
    || statusRefreshState.value === 'loading'
  ) {
    return
  }

  refreshCurrentTime()

  const expectedSelectedOption = selectedPlanOption.value

  if (confirmationStage.value !== 'ready' || !expectedSelectedOption) {
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  confirmationActionState.value = 'saving'
  confirmationError.value = ''
  confirmationConflict.value = false
  confirmationJustCompleted.value = false

  try {
    const nextInvitation = await api.confirmPlan(
      invitationId.value,
      token,
      buildPlanConfirmationPayload(expectedSelectedOption.id),
    )

    applyManagedInvitation(nextInvitation)
    confirmationActionState.value = 'idle'
    confirmationJustCompleted.value = true
  }
  catch (error: unknown) {
    const parsedError = parsePlanConfirmationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
      errorMessage.value = parsedError.message
      pageState.value = 'error'
      return
    }

    if (parsedError.code === 'selected_option_expired') {
      serverExpiredSelectionId.value = invitation.value?.selected_option_id ?? null
    }

    confirmationError.value = parsedError.message
    confirmationConflict.value = parsedError.status === 409
      || parsedError.code === 'selected_option_expired'
    confirmationActionState.value = 'error'
  }
}

function markPlanDirty(): void {
  planSaveState.value = 'idle'
  planSaveError.value = ''
}

async function savePlanningOptions(payload: PlanOptionsPayload): Promise<void> {
  if (planSaveState.value === 'saving') {
    return
  }

  if (planOptionsPayloadHasExpiredDate(payload, refreshCurrentTime())) {
    planSaveError.value = 'Одна из дат уже наступила. Обнови время и сохрани варианты снова.'
    planSaveState.value = 'error'
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  planSaveState.value = 'saving'
  planSaveError.value = ''

  try {
    const nextInvitation = await api.savePlanOptions(invitationId.value, token, payload)

    applyManagedInvitation(nextInvitation)
    planSaveState.value = 'success'
    confirmationJustCompleted.value = false
  }
  catch (error: unknown) {
    const parsedError = parsePlanningApiError(error, 'options')

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
      errorMessage.value = parsedError.message
      pageState.value = 'error'
      return
    }

    planSaveError.value = parsedError.message
    planSaveState.value = 'error'
  }
}

async function copyPublicUrl(): Promise<void> {
  if (!publicUrl.value) {
    return
  }

  copyStatus.value = await copyTextWithFallback(publicUrl.value) ? 'copied' : 'failed'
}

function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Дата не указана'
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(date)
}

onMounted(loadManagedInvitation)
</script>

<template>
  <main class="detail-page detail-page--management">
    <section class="manage-shell" aria-labelledby="manage-page-title">
      <NuxtLink class="brand-link" to="/" aria-label="Date Planner, перейти на главную">
        <img src="/images/envelope-heart.svg" alt="" width="46" height="40">
        <span>Date Planner</span>
      </NuxtLink>

      <div v-if="pageState === 'loading'" class="state-card" role="status" aria-live="polite">
        <span class="state-card__icon state-card__icon--loading" aria-hidden="true">♥</span>
        <h1 id="manage-page-title">Проверяем секретную ссылку…</h1>
        <p>Токен не передаётся в адресе запроса.</p>
      </div>

      <div v-else-if="pageState === 'missing-token'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔑</span>
        <h1 id="manage-page-title">В ссылке нет секретного ключа</h1>
        <p>
          Открой полную ссылку управления, которую получил сразу после создания приглашения.
        </p>
        <NuxtLink to="/">Вернуться на главную</NuxtLink>
      </div>

      <div v-else-if="pageState === 'error'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔐</span>
        <h1 id="manage-page-title">Доступ не подтверждён</h1>
        <p>{{ errorMessage }}</p>
        <div class="state-card__actions">
          <button v-if="canRetry" type="button" @click="loadManagedInvitation">
            Попробовать снова
          </button>
          <NuxtLink to="/">На главную</NuxtLink>
        </div>
      </div>

      <template v-else-if="invitation">
        <header class="manage-shell__heading">
          <p>Секретная страница автора</p>
          <h1 id="manage-page-title">Управление приглашением</h1>
          <span>Секрет удалён из адресной строки и сохранён только для этой вкладки.</span>
        </header>

        <article class="manage-card">
          <section
            class="publication-overview"
            :class="`publication-overview--${publicationPresentation.tone}`"
            aria-labelledby="publication-overview-title"
            :aria-busy="publicationActionState === 'publishing'"
          >
            <span class="publication-overview__icon" aria-hidden="true">
              {{ publicationPresentation.icon }}
            </span>
            <div class="publication-overview__copy">
              <p>Доступ получателю</p>
              <h2 id="publication-overview-title">{{ publicationPresentation.label }}</h2>
              <span>{{ publicationPresentation.description }}</span>
              <time
                v-if="invitation.published_at"
                :datetime="invitation.published_at"
              >
                Опубликовано: {{ formatDate(invitation.published_at) }}
              </time>
            </div>
            <button
              v-if="invitation.publication_status === 'draft'"
              type="button"
              :disabled="publicationActionState === 'publishing'"
              @click="publishDraft"
            >
              <span aria-hidden="true">
                {{ publicationActionState === 'publishing' ? '⏳' : '💌' }}
              </span>
              {{ publicationActionState === 'publishing'
                ? 'Публикуем…'
                : 'Опубликовать приглашение' }}
            </button>
            <p
              v-if="publicationActionState === 'error'"
              class="publication-overview__message publication-overview__message--error"
              role="alert"
            >
              {{ publicationError }}
            </p>
            <p
              v-else-if="publicationJustCompleted"
              class="publication-overview__message publication-overview__message--success"
              role="status"
              aria-live="polite"
            >
              Приглашение опубликовано. Теперь публичную ссылку можно отправлять получателю.
            </p>
          </section>

          <template v-if="invitation.publication_status === 'published'">
            <section
              class="response-overview"
              :class="`response-overview--${responsePresentation.tone}`"
              aria-labelledby="response-overview-title"
            >
              <span class="response-overview__icon" aria-hidden="true">
                {{ responsePresentation.icon }}
              </span>
              <div class="response-overview__copy">
                <p>Текущий ответ</p>
                <h2 id="response-overview-title">{{ responsePresentation.label }}</h2>
                <span>{{ responsePresentation.description }}</span>
                <time
                  v-if="invitation.responded_at"
                  :datetime="invitation.responded_at"
                >
                  Получен: {{ formatDate(invitation.responded_at) }}
                </time>
                <span v-else>Время ответа появится после выбора получателя.</span>
              </div>
              <button
                type="button"
                :disabled="statusRefreshState === 'loading'
                  || confirmationActionState === 'saving'"
                aria-label="Загрузить актуальный ответ получателя"
                @click="refreshResponseStatus"
              >
                {{ statusRefreshState === 'loading' ? 'Обновляем…' : 'Обновить статус' }}
              </button>
              <p
                v-if="statusRefreshState === 'success'"
                class="response-overview__refresh-message response-overview__refresh-message--success"
                role="status"
              >
                Статус обновлён.
              </p>
              <p
                v-else-if="statusRefreshState === 'error'"
                class="response-overview__refresh-message response-overview__refresh-message--error"
                role="alert"
              >
                {{ statusRefreshError }}
              </p>
            </section>

            <template v-if="confirmationStage === 'confirmed'">
              <FinalPlanCard
                v-if="selectedPlanOption && invitation.confirmed_at"
                :announce="confirmationJustCompleted"
                :confirmed-at="invitation.confirmed_at"
                :option="selectedPlanOption"
              />
              <section v-else class="plan-data-error" role="alert">
                Подтверждённый план не удалось загрузить. Обнови данные страницы.
              </section>
            </template>

            <section
              v-else-if="confirmationStage === 'ready'"
              class="plan-confirmation"
              aria-labelledby="plan-confirmation-title"
              :aria-busy="confirmationActionState === 'saving' || statusRefreshState === 'loading'"
            >
              <header>
                <span aria-hidden="true">💞</span>
                <div>
                  <p>Финальный шаг автора</p>
                  <h2 id="plan-confirmation-title">Подтверди выбранный план</h2>
                </div>
              </header>

              <div v-if="selectedPlanOption" class="plan-confirmation__summary">
                <time :datetime="selectedPlanOption.starts_at">
                  {{ formatPlanOptionDate(selectedPlanOption.starts_at) }}
                </time>
                <strong>{{ selectedPlanOption.place }}</strong>
                <span v-if="selectedPlanOption.comment">{{ selectedPlanOption.comment }}</span>
                <small v-if="invitation.selected_at">
                  Получатель выбрал {{ formatDate(invitation.selected_at) }}
                </small>
              </div>
              <p v-else class="plan-data-error" role="alert">
                Выбранный вариант не найден. Обнови данные перед подтверждением.
              </p>

              <p id="plan-confirmation-warning" class="plan-confirmation__warning">
                <span aria-hidden="true">⚠️</span>
                <strong>Это действие необратимо.</strong>
                После подтверждения получатель больше не сможет менять вариант.
              </p>

              <p
                v-if="confirmationActionState === 'error'"
                class="plan-confirmation__error"
                role="alert"
              >
                {{ confirmationError }}
              </p>

              <button
                v-if="confirmationConflict"
                type="button"
                :disabled="statusRefreshState === 'loading'
                  || confirmationActionState === 'saving'"
                @click="refreshResponseStatus"
              >
                {{ statusRefreshState === 'loading' ? 'Обновляем данные…' : 'Обновить данные' }}
              </button>
              <button
                v-else
                type="button"
                aria-describedby="plan-confirmation-warning"
                :disabled="confirmationActionState === 'saving'
                  || statusRefreshState === 'loading'
                  || !selectedPlanOption"
                @click="confirmSelectedPlan"
              >
                <span aria-hidden="true">
                  {{ confirmationActionState === 'saving' ? '⏳' : '✓' }}
                </span>
                {{ confirmationActionState === 'saving'
                  ? 'Подтверждаем план…'
                  : 'Подтвердить окончательно' }}
              </button>
            </section>

            <template v-else-if="confirmationStage === 'expired'">
              <section
                class="plan-recovery"
                aria-labelledby="plan-recovery-title"
                role="status"
                aria-live="polite"
              >
                <span class="plan-recovery__icon" aria-hidden="true">🕰️</span>
                <div>
                  <p>Нужно обновить план</p>
                  <h2 id="plan-recovery-title">Время выбранного варианта уже прошло</h2>
                  <p v-if="selectedPlanOption">
                    Получатель выбирал «{{ selectedPlanOption.place }}» —
                    {{ formatPlanOptionDate(selectedPlanOption.starts_at) }}.
                  </p>
                  <p>
                    Исправь даты или предложи новый набор ниже. Сохранение заменит устаревшие
                    варианты и сбросит прежний выбор, чтобы получатель мог выбрать снова.
                  </p>
                </div>
              </section>

              <PlanOptionsEditor
                :current-time="currentTime"
                :options="invitation.plan_options"
                :save-error="planSaveError"
                :save-state="planSaveState"
                @dirty="markPlanDirty"
                @save="savePlanningOptions"
              />
            </template>

            <PlanOptionsEditor
              v-else-if="invitation.response_status === 'accepted'"
              :current-time="currentTime"
              :options="invitation.plan_options"
              :save-error="planSaveError"
              :save-state="planSaveState"
              @dirty="markPlanDirty"
              @save="savePlanningOptions"
            />
          </template>

          <dl class="manage-card__details">
            <div>
              <dt>От кого</dt>
              <dd>{{ invitation.author_name }}</dd>
            </div>
            <div>
              <dt>Для кого</dt>
              <dd>{{ invitation.recipient_name }}</dd>
            </div>
            <div v-if="invitation.message.trim()" class="manage-card__message">
              <dt>Сообщение</dt>
              <dd>{{ invitation.message }}</dd>
            </div>
            <div>
              <dt>Режим</dt>
              <dd>
                {{ creationModePresentation.icon }} {{ creationModePresentation.label }}
              </dd>
            </div>
            <div>
              <dt>Статус публикации</dt>
              <dd>{{ publicationPresentation.icon }} {{ publicationPresentation.label }}</dd>
            </div>
            <div>
              <dt>Создано</dt>
              <dd>{{ formatDate(invitation.created_at) }}</dd>
            </div>
          </dl>

          <div v-if="invitation.publication_status === 'published'" class="created-link">
            <label for="managed-public-link">Ссылка для получателя</label>
            <div class="created-link__controls">
              <input id="managed-public-link" :value="publicUrl" type="text" readonly>
              <button
                type="button"
                :aria-label="copyStatus === 'copied'
                  ? 'Публичная ссылка скопирована'
                  : 'Скопировать публичную ссылку'"
                @click="copyPublicUrl"
              >
                {{ copyStatus === 'copied' ? 'Скопировано' : 'Копировать' }}
              </button>
            </div>
            <a :href="publicUrl">Открыть приглашение</a>
            <span v-if="copyStatus === 'failed'" class="created-link__copy-error" role="status">
              Не удалось скопировать — выдели ссылку вручную.
            </span>
            <span class="sr-only" aria-live="polite">
              {{ copyStatus === 'copied' ? 'Публичная ссылка скопирована.' : '' }}
            </span>
          </div>
          <p v-else class="manage-card__draft-notice" role="status">
            <span aria-hidden="true">📝</span>
            Публичная ссылка закрыта, пока приглашение находится в черновиках.
          </p>

          <p class="manage-card__notice">
            <span aria-hidden="true">🔐</span>
            Не передавай секретную ссылку: она открывает закрытую страницу автора.
          </p>
        </article>
      </template>
    </section>
  </main>
</template>
