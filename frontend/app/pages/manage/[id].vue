<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { copyTextWithFallback } from '../../../composables/useClipboard'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import type { InvitationRecord } from '../../../types/invitation'
import {
  buildPublicInvitationUrl,
  isInvitationId,
  isManagementToken,
  managementTokenSessionKey,
  parseInvitationApiError,
  readManagementToken,
} from '../../../utils/invitations'

type PageState = 'error' | 'loading' | 'missing-token' | 'ready'

const route = useRoute()
const api = useInvitationsApi()
const invitation = ref<InvitationRecord | null>(null)
const publicUrl = ref('')
const pageState = ref<PageState>('loading')
const errorMessage = ref('')
const copyStatus = ref<'idle' | 'copied' | 'failed'>('idle')
const canRetry = ref(true)
const managementToken = ref<string | null>(null)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')

useHead({
  title: 'Управление приглашением — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

function takeTokenFromBrowser(): string | null {
  const key = managementTokenSessionKey(invitationId.value)
  const hasHash = window.location.hash.length > 0
  const tokenFromHash = readManagementToken(window.location.hash)

  if (hasHash) {
    window.history.replaceState(
      window.history.state,
      '',
      `${window.location.pathname}${window.location.search}`,
    )

    if (!tokenFromHash) {
      managementToken.value = null

      try {
        window.sessionStorage.removeItem(key)
      }
      catch {
        // Storage can be unavailable in private browsing modes.
      }

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

async function loadManagedInvitation(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  canRetry.value = true

  if (!isInvitationId(invitationId.value)) {
    errorMessage.value = 'Проверь адрес секретной ссылки.'
    pageState.value = 'error'
    return
  }

  const token = takeTokenFromBrowser()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  try {
    invitation.value = await api.getManagedInvitation(invitationId.value, token)
    publicUrl.value = buildPublicInvitationUrl(window.location.origin, invitationId.value)
    pageState.value = 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      managementToken.value = null
      canRetry.value = false

      try {
        window.sessionStorage.removeItem(managementTokenSessionKey(invitationId.value))
      }
      catch {
        // Storage can be unavailable in private browsing modes.
      }
    }

    errorMessage.value = parsedError.message
    pageState.value = 'error'
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
          <dl class="manage-card__details">
            <div>
              <dt>От кого</dt>
              <dd>{{ invitation.author_name }}</dd>
            </div>
            <div>
              <dt>Для кого</dt>
              <dd>{{ invitation.recipient_name }}</dd>
            </div>
            <div class="manage-card__message">
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
