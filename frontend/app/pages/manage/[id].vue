<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import PlanOptionsEditor from '../../../components/planning/PlanOptionsEditor.vue'
import { copyTextWithFallback } from '../../../composables/useClipboard'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import { useManagementToken } from '../../../composables/useManagementToken'
import type { InvitationRecord, PlanOptionsPayload } from '../../../types/invitation'
import {
  buildPublicInvitationUrl,
  getInvitationResponsePresentation,
  isInvitationId,
  parseInvitationApiError,
} from '../../../utils/invitations'
import {
  findSelectedPlanOption,
  formatPlanOptionDate,
  parsePlanningApiError,
} from '../../../utils/planning'

type PageState = 'error' | 'loading' | 'missing-token' | 'ready'
type StatusRefreshState = 'error' | 'idle' | 'loading' | 'success'
type PlanSaveState = 'error' | 'idle' | 'saving' | 'success'

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
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const { clearManagementToken, takeManagementToken } = useManagementToken(invitationId)
const responsePresentation = computed(() => getInvitationResponsePresentation(
  invitation.value?.response_status ?? 'pending',
))
const selectedPlanOption = computed(() => findSelectedPlanOption(
  invitation.value?.plan_options ?? [],
  invitation.value?.selected_option_id ?? null,
))

useHead({
  title: 'Управление приглашением — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

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
    invitation.value = await api.getManagedInvitation(invitationId.value, token)
    publicUrl.value = buildPublicInvitationUrl(window.location.origin, invitationId.value)
    planSaveState.value = 'idle'
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

async function refreshResponseStatus(): Promise<void> {
  if (statusRefreshState.value === 'loading') {
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
    invitation.value = await api.getManagedInvitation(invitationId.value, token)
    statusRefreshState.value = 'success'
    planSaveState.value = 'idle'
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

function markPlanDirty(): void {
  planSaveState.value = 'idle'
  planSaveError.value = ''
}

async function savePlanningOptions(payload: PlanOptionsPayload): Promise<void> {
  if (planSaveState.value === 'saving') {
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
    invitation.value = await api.savePlanOptions(invitationId.value, token, payload)
    planSaveState.value = 'success'
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
              :disabled="statusRefreshState === 'loading'"
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

          <section
            v-if="invitation.response_status === 'accepted' && invitation.selected_option_id"
            class="plan-locked"
            aria-labelledby="selected-plan-title"
          >
            <span class="plan-locked__icon" aria-hidden="true">💞</span>
            <div>
              <p>Выбранный вариант</p>
              <h2 id="selected-plan-title">План свидания согласован</h2>
              <template v-if="selectedPlanOption">
                <time :datetime="selectedPlanOption.starts_at">
                  {{ formatPlanOptionDate(selectedPlanOption.starts_at) }}
                </time>
                <strong>{{ selectedPlanOption.place }}</strong>
                <span v-if="selectedPlanOption.comment">{{ selectedPlanOption.comment }}</span>
              </template>
              <span v-else>Обнови страницу, чтобы загрузить выбранный вариант.</span>
              <small v-if="invitation.selected_at">
                Выбрано: {{ formatDate(invitation.selected_at) }}
              </small>
            </div>
            <p class="plan-locked__notice">
              <span aria-hidden="true">🔒</span>
              После выбора получателя набор вариантов заблокирован от изменений.
            </p>
          </section>

          <PlanOptionsEditor
            v-else-if="invitation.response_status === 'accepted'"
            :options="invitation.plan_options"
            :save-error="planSaveError"
            :save-state="planSaveState"
            @dirty="markPlanDirty"
            @save="savePlanningOptions"
          />

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
              <dt>Создано</dt>
              <dd>{{ formatDate(invitation.created_at) }}</dd>
            </div>
          </dl>

          <div class="created-link">
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

          <p class="manage-card__notice">
            <span aria-hidden="true">🔐</span>
            Не передавай секретную ссылку: она открывает закрытую страницу автора.
          </p>
        </article>
      </template>
    </section>
  </main>
</template>
