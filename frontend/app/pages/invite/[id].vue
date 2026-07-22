<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import InvitationPreviewCard from '../../../components/invitation/InvitationPreviewCard.vue'
import { useInvitationsApi } from '../../../composables/useInvitationsApi'
import type { InvitationRecord } from '../../../types/invitation'
import { isInvitationId, parseInvitationApiError } from '../../../utils/invitations'

type PageState = 'error' | 'loading' | 'ready'

const route = useRoute()
const api = useInvitationsApi()
const invitation = ref<InvitationRecord | null>(null)
const pageState = ref<PageState>('loading')
const errorMessage = ref('')
const isNotFound = ref(false)
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
    pageState.value = 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    errorMessage.value = parsedError.message
    isNotFound.value = parsedError.status === 404
    pageState.value = 'error'
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
          :author-name="invitation.author_name"
          :message="invitation.message"
          :recipient-name="invitation.recipient_name"
        />
        <p class="detail-shell__privacy">
          <span aria-hidden="true">🔒</span>
          Страница доступна только тем, у кого есть ссылка.
        </p>
      </template>
    </section>
  </main>
</template>
