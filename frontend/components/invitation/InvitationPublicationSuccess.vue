<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { copyTextWithFallback } from '../../composables/useClipboard'
import {
  buildInvitationSharePayload,
  buildTelegramShareUrl,
  buildWhatsAppShareUrl,
  shareInvitationNatively,
  supportsNativeShare,
} from '../../utils/sharing'

type CopyState = 'copied' | 'failed' | 'idle'
type NativeShareState = 'failed' | 'idle' | 'sharing'

const props = defineProps<{
  authorName: string
  managementUrl: string
  publicUrl: string
  recipientName: string
}>()

const publicCopyState = ref<CopyState>('idle')
const managementCopyState = ref<CopyState>('idle')
const nativeShareState = ref<NativeShareState>('idle')
const nativeShareSupported = ref(false)
const managementLinkRevealed = ref(false)
const sharePayload = computed(() => buildInvitationSharePayload(
  props.authorName,
  props.recipientName,
  props.publicUrl,
))
const telegramShareUrl = computed(() => buildTelegramShareUrl(sharePayload.value))
const whatsAppShareUrl = computed(() => buildWhatsAppShareUrl(sharePayload.value))

async function copyPublicLink(): Promise<void> {
  publicCopyState.value = await copyTextWithFallback(props.publicUrl)
    ? 'copied'
    : 'failed'
}

async function copyManagementLink(): Promise<void> {
  managementCopyState.value = await copyTextWithFallback(props.managementUrl)
    ? 'copied'
    : 'failed'
}

async function shareFromDevice(): Promise<void> {
  if (nativeShareState.value === 'sharing') {
    return
  }

  nativeShareState.value = 'sharing'

  const outcome = await shareInvitationNatively(
    sharePayload.value,
    typeof navigator === 'undefined' ? undefined : navigator,
  )

  nativeShareState.value = outcome === 'failed' || outcome === 'unsupported'
    ? 'failed'
    : 'idle'
}

function revealManagementLink(event: Event): void {
  managementLinkRevealed.value = (event.currentTarget as HTMLDetailsElement).open
}

onMounted(() => {
  nativeShareSupported.value = supportsNativeShare(navigator)
})
</script>

<template>
  <article class="publication-success" aria-labelledby="publication-success-title">
    <header class="publication-success__header">
      <span class="publication-success__icon" aria-hidden="true">✓</span>
      <p>Публикация завершена</p>
      <h1 id="publication-success-title">Приглашение готово к отправке</h1>
      <span>
        {{ authorName }}, отправь {{ recipientName }} только ссылку из первого блока.
      </span>
    </header>

    <section
      class="publication-success__public"
      aria-labelledby="publication-public-link-title"
    >
      <div class="publication-success__section-heading">
        <span aria-hidden="true">💌</span>
        <div>
          <p>Можно отправлять</p>
          <h2 id="publication-public-link-title">Ссылка для получателя</h2>
        </div>
      </div>

      <p class="publication-success__instruction">
        Эта ссылка открывает только приглашение. Скопируй её и отправь {{ recipientName }}.
      </p>

      <div class="created-link">
        <label for="published-public-link">Публичная ссылка</label>
        <div class="created-link__controls">
          <input
            id="published-public-link"
            :value="publicUrl"
            type="text"
            readonly
          >
          <button
            type="button"
            :aria-label="publicCopyState === 'copied'
              ? 'Публичная ссылка скопирована'
              : 'Скопировать публичную ссылку'"
            @click="copyPublicLink"
          >
            {{ publicCopyState === 'copied' ? 'Скопировано' : 'Копировать' }}
          </button>
        </div>
        <a :href="publicUrl">Открыть приглашение</a>
        <span
          v-if="publicCopyState === 'failed'"
          class="created-link__copy-error"
          role="status"
        >
          Не удалось скопировать автоматически — выдели ссылку вручную.
        </span>
      </div>

      <div
        class="publication-success__sharing"
        aria-labelledby="publication-sharing-title"
      >
        <div class="publication-success__sharing-heading">
          <div>
            <p>Выбери удобный способ</p>
            <h3 id="publication-sharing-title">Отправить приглашение</h3>
          </div>
          <span aria-hidden="true">↗</span>
        </div>

        <div class="publication-success__share-actions">
          <button
            v-if="nativeShareSupported"
            class="publication-success__share-action publication-success__share-action--native"
            type="button"
            :disabled="nativeShareState === 'sharing'"
            @click="shareFromDevice"
          >
            <span aria-hidden="true">📤</span>
            {{ nativeShareState === 'sharing' ? 'Открываем…' : 'Поделиться' }}
          </button>

          <a
            class="publication-success__share-action publication-success__share-action--telegram"
            :href="telegramShareUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span aria-hidden="true">✈</span>
            Telegram
          </a>

          <a
            class="publication-success__share-action publication-success__share-action--whatsapp"
            :href="whatsAppShareUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span aria-hidden="true">💬</span>
            WhatsApp
          </a>
        </div>

        <p class="publication-success__sharing-hint">
          В сервис откроется готовый текст только с публичной ссылкой. Перед отправкой его можно
          изменить. Поле со ссылкой выше всегда остаётся ручным запасным вариантом.
        </p>

        <p
          v-if="nativeShareState === 'failed'"
          class="publication-success__sharing-error"
          role="status"
        >
          Системное меню отправки не открылось. Используй Telegram, WhatsApp или скопируй ссылку.
        </p>
      </div>

      <p class="publication-success__public-note">
        <span aria-hidden="true">✓</span>
        В этой ссылке нет секретного ключа управления.
      </p>
    </section>

    <section
      class="publication-success__management"
      aria-labelledby="publication-management-title"
    >
      <div class="publication-success__section-heading">
        <span aria-hidden="true">🔐</span>
        <div>
          <p>Только для автора</p>
          <h2 id="publication-management-title">Доступ к управлению</h2>
        </div>
      </div>

      <p>
        Секретная ссылка позволяет изменять приглашение и подтверждать итоговый план.
        Не пересылай её получателю и не публикуй открыто.
      </p>

      <a class="publication-success__manage-link" :href="managementUrl">
        Перейти в управление
      </a>

      <details class="publication-success__secret" @toggle="revealManagementLink">
        <summary>Показать резервную секретную ссылку</summary>
        <div v-if="managementLinkRevealed" class="publication-success__secret-content">
          <p>
            Сохрани её в надёжном месте. Без аккаунта восстановить этот доступ нельзя.
          </p>
          <div class="created-link created-link--secret">
            <label for="published-management-link">Секретная ссылка автора</label>
            <div class="created-link__controls">
              <input
                id="published-management-link"
                :value="managementUrl"
                type="text"
                readonly
              >
              <button
                type="button"
                :aria-label="managementCopyState === 'copied'
                  ? 'Секретная ссылка скопирована'
                  : 'Скопировать секретную ссылку автора'"
                @click="copyManagementLink"
              >
                {{ managementCopyState === 'copied' ? 'Скопировано' : 'Копировать' }}
              </button>
            </div>
            <span
              v-if="managementCopyState === 'failed'"
              class="created-link__copy-error"
              role="status"
            >
              Не удалось скопировать автоматически — выдели ссылку вручную.
            </span>
          </div>
        </div>
      </details>
    </section>

    <footer class="publication-success__footer">
      <NuxtLink to="/">Создать ещё одно приглашение</NuxtLink>
    </footer>

    <p class="sr-only" aria-live="polite">
      <template v-if="publicCopyState === 'copied'">Публичная ссылка скопирована.</template>
      <template v-if="managementCopyState === 'copied'">Секретная ссылка скопирована.</template>
    </p>
  </article>
</template>
