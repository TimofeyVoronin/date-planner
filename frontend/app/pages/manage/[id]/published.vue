<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import InvitationPublicationSuccess from '../../../../components/invitation/InvitationPublicationSuccess.vue'
import { useInvitationsApi } from '../../../../composables/useInvitationsApi'
import { useManagementToken } from '../../../../composables/useManagementToken'
import type { InvitationRecord } from '../../../../types/invitation'
import {
  buildManagementInvitationPath,
  buildManagementInvitationUrl,
  buildPublicInvitationUrl,
  isInvitationId,
  parseInvitationApiError,
} from '../../../../utils/invitations'

type PageState = 'draft' | 'error' | 'loading' | 'missing-token' | 'ready'

const route = useRoute()
const api = useInvitationsApi()
const invitation = ref<InvitationRecord | null>(null)
const pageState = ref<PageState>('loading')
const errorMessage = ref('')
const canRetry = ref(true)
const publicUrl = ref('')
const managementUrl = ref('')
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const managePath = computed(() => buildManagementInvitationPath(invitationId.value))
const { clearManagementToken, takeManagementToken } = useManagementToken(invitationId)

useHead({
  title: 'Приглашение опубликовано — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

async function loadPublishedInvitation(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  canRetry.value = true

  if (!isInvitationId(invitationId.value)) {
    errorMessage.value = 'Проверь адрес страницы публикации.'
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

    invitation.value = nextInvitation

    if (nextInvitation.publication_status !== 'published') {
      pageState.value = 'draft'
      return
    }

    publicUrl.value = buildPublicInvitationUrl(window.location.origin, nextInvitation.id)
    managementUrl.value = buildManagementInvitationUrl(
      window.location.origin,
      nextInvitation.id,
      token,
    )
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

onMounted(loadPublishedInvitation)
</script>

<template>
  <main class="detail-page detail-page--publication-success">
    <div class="background-heart background-heart--one" aria-hidden="true" />
    <div class="background-heart background-heart--two" aria-hidden="true" />

    <section class="publication-success-shell" aria-labelledby="publication-success-page-title">
      <NuxtLink class="brand-link" to="/" aria-label="Date Planner, перейти на главную">
        <img src="/images/envelope-heart.svg" alt="" width="46" height="40">
        <span>Date Planner</span>
      </NuxtLink>

      <div v-if="pageState === 'loading'" class="state-card" role="status" aria-live="polite">
        <span class="state-card__icon state-card__icon--loading" aria-hidden="true">♥</span>
        <h1 id="publication-success-page-title">Проверяем публикацию…</h1>
        <p>Секретный ключ будет удалён из адресной строки.</p>
      </div>

      <div v-else-if="pageState === 'missing-token'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔑</span>
        <h1 id="publication-success-page-title">Нет доступа к ссылкам автора</h1>
        <p>
          Открой полную секретную ссылку, полученную после создания приглашения,
          или вернись на уже открытую страницу управления.
        </p>
        <NuxtLink to="/">Вернуться на главную</NuxtLink>
      </div>

      <div v-else-if="pageState === 'draft'" class="state-card" role="status">
        <span class="state-card__icon" aria-hidden="true">📝</span>
        <h1 id="publication-success-page-title">Приглашение ещё не опубликовано</h1>
        <p>Заверши настройку и опубликуй черновик на странице управления.</p>
        <NuxtLink :to="managePath">Вернуться к управлению</NuxtLink>
      </div>

      <div v-else-if="pageState === 'error'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔐</span>
        <h1 id="publication-success-page-title">Не удалось открыть результат публикации</h1>
        <p>{{ errorMessage }}</p>
        <div class="state-card__actions">
          <button v-if="canRetry" type="button" @click="loadPublishedInvitation">
            Попробовать снова
          </button>
          <NuxtLink to="/">На главную</NuxtLink>
        </div>
      </div>

      <InvitationPublicationSuccess
        v-else-if="pageState === 'ready' && invitation"
        :author-name="invitation.author_name"
        :management-url="managementUrl"
        :public-url="publicUrl"
        :recipient-name="invitation.recipient_name"
      />
    </section>
  </main>
</template>
