<script setup lang="ts">
import InvitationPreviewCard from '../../components/invitation/InvitationPreviewCard.vue'

type ApiHealthResponse = {
  status: string
  service: string
}

const config = useRuntimeConfig()
const apiAvailable = ref(false)
const apiCheckFinished = ref(false)
const showApiStatus = import.meta.dev

onMounted(async () => {
  if (!import.meta.dev) {
    return
  }

  try {
    const response = await $fetch<ApiHealthResponse>('/api/v1/health/', {
      baseURL: config.public.apiBaseUrl,
      timeout: 3000,
    })

    apiAvailable.value = response.status === 'ok'
  }
  catch {
    apiAvailable.value = false
  }
  finally {
    apiCheckFinished.value = true
  }
})
</script>

<template>
  <main class="landing-page">
    <div class="background-heart background-heart--one" aria-hidden="true" />
    <div class="background-heart background-heart--two" aria-hidden="true" />

    <section class="hero" aria-labelledby="page-title">
      <header class="hero__header">
        <div class="hero__icon-shell" aria-hidden="true">
          <img
            class="hero__icon"
            src="/images/envelope-heart.svg"
            alt=""
            width="68"
            height="58"
          >
        </div>

        <p class="hero__eyebrow">Date Planner</p>
        <h1 id="page-title" class="hero__title">
          Создай приглашение<br class="hero__desktop-break">
          на свидание <span>ЗА 2 МИНУТЫ</span>
        </h1>
        <p class="hero__subtitle">Вот что увидит тот, кого ты позовёшь <span aria-hidden="true">👇</span></p>
      </header>

      <InvitationPreviewCard />

      <aside
        v-if="showApiStatus && apiCheckFinished"
        class="api-status"
        :class="apiAvailable ? 'api-status--online' : 'api-status--offline'"
        aria-live="polite"
      >
        <span class="api-status__dot" aria-hidden="true" />
        {{ apiAvailable ? 'API доступен' : 'API недоступен' }}
      </aside>
    </section>
  </main>
</template>
