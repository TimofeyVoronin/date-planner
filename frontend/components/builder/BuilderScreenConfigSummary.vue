<script setup lang="ts">
import type { InvitationScreenRecord } from '../../types/screen'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'
import { getInvitationScreenPresentation } from '../../utils/screens'

defineProps<{
  screens: readonly InvitationScreenRecord[]
}>()

const config = useRuntimeConfig()

function imageUrl(imageKey: string): string | undefined {
  const image = getInvitationImageByKey(imageKey)
  return image ? resolveInvitationImageUrl(image.assetPath, config.app.baseURL) : undefined
}

function imageAlt(imageKey: string): string {
  return getInvitationImageByKey(imageKey)?.altText ?? ''
}

function imageLabel(imageKey: string): string {
  return getInvitationImageByKey(imageKey)?.label ?? imageKey
}
</script>

<template>
  <section class="builder-screen-summary" aria-labelledby="builder-screen-summary-title">
    <div class="builder-screen-summary__heading">
      <p>Подготовленные экраны</p>
      <h3 id="builder-screen-summary-title">Основа сценария уже создана</h3>
      <span>
        Сейчас показаны серверные значения по умолчанию. Редактирование текстов и выбор изображения
        появятся в следующих задачах.
      </span>
    </div>

    <div class="builder-screen-summary__grid">
      <article
        v-for="screen in screens"
        :key="screen.screen_type"
        class="builder-screen-summary__card"
      >
        <div class="builder-screen-summary__media">
          <img
            v-if="imageUrl(screen.image_key)"
            class="builder-screen-summary__image"
            :src="imageUrl(screen.image_key)"
            :alt="imageAlt(screen.image_key)"
            width="640"
            height="420"
            loading="lazy"
            decoding="async"
          >
          <span v-else class="builder-screen-summary__icon" aria-hidden="true">
            {{ getInvitationScreenPresentation(screen.screen_type).icon }}
          </span>
        </div>
        <div>
          <p>{{ getInvitationScreenPresentation(screen.screen_type).label }}</p>
          <h4>{{ screen.title }}</h4>
          <span>{{ screen.subtitle }}</span>
          <small v-if="screen.button_text">Кнопка: {{ screen.button_text }}</small>
          <small>Иллюстрация: {{ imageLabel(screen.image_key) }}</small>
        </div>
      </article>
    </div>
  </section>
</template>
