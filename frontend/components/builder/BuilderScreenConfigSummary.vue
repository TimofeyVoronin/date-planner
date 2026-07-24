<script setup lang="ts">
import type { InvitationScreenRecord } from '../../types/screen'
import { getInvitationScreenPresentation } from '../../utils/screens'

defineProps<{
  screens: readonly InvitationScreenRecord[]
}>()
</script>

<template>
  <section class="builder-screen-summary" aria-labelledby="builder-screen-summary-title">
    <div class="builder-screen-summary__heading">
      <p>Подготовленные экраны</p>
      <h3 id="builder-screen-summary-title">Основа сценария уже создана</h3>
      <span>
        Сейчас показаны серверные значения по умолчанию. Редактирование текстов и изображений
        появится в следующих задачах.
      </span>
    </div>

    <div class="builder-screen-summary__grid">
      <article
        v-for="screen in screens"
        :key="screen.screen_type"
        class="builder-screen-summary__card"
      >
        <span class="builder-screen-summary__icon" aria-hidden="true">
          {{ getInvitationScreenPresentation(screen.screen_type).icon }}
        </span>
        <div>
          <p>{{ getInvitationScreenPresentation(screen.screen_type).label }}</p>
          <h4>{{ screen.title }}</h4>
          <span>{{ screen.subtitle }}</span>
          <small v-if="screen.button_text">Кнопка: {{ screen.button_text }}</small>
        </div>
      </article>
    </div>
  </section>
</template>
