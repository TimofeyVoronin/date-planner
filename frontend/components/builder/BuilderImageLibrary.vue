<script setup lang="ts">
import { computed } from 'vue'
import type { InvitationScreenType } from '../../types/screen'
import {
  getInvitationImagesForScreens,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'
import { getInvitationScreenPresentation } from '../../utils/screens'

const props = defineProps<{
  screenTypes: readonly InvitationScreenType[]
}>()

const config = useRuntimeConfig()
const imagesByScreen = computed(() => props.screenTypes.map(screenType => ({
  screenType,
  presentation: getInvitationScreenPresentation(screenType),
  images: getInvitationImagesForScreens([screenType]),
})))

function imageUrl(assetPath: string): string {
  return resolveInvitationImageUrl(assetPath, config.app.baseURL)
}
</script>

<template>
  <section class="builder-image-library" aria-labelledby="builder-image-library-title">
    <header class="builder-image-library__heading">
      <div>
        <p>Встроенная библиотека</p>
        <h3 id="builder-image-library-title">Иллюстрации для этого шага</h3>
      </div>
      <span>{{ getInvitationImagesForScreens(screenTypes).length }} вариантов</span>
    </header>

    <p class="builder-image-library__description">
      Все изображения хранятся внутри проекта, не загружаются со сторонних сайтов и уже имеют
      доступное текстовое описание. Выбор конкретной карточки подключим в редакторе экранов.
    </p>

    <section
      v-for="group in imagesByScreen"
      :key="group.screenType"
      class="builder-image-library__group"
      :aria-labelledby="`builder-image-group-${group.screenType}`"
    >
      <div class="builder-image-library__group-heading">
        <span aria-hidden="true">{{ group.presentation.icon }}</span>
        <div>
          <h4 :id="`builder-image-group-${group.screenType}`">
            {{ group.presentation.label }}
          </h4>
          <p>{{ group.presentation.description }}</p>
        </div>
      </div>

      <div class="builder-image-library__grid">
        <figure
          v-for="image in group.images"
          :key="image.key"
          class="builder-image-library__card"
        >
          <div class="builder-image-library__media">
            <img
              :src="imageUrl(image.assetPath)"
              :alt="image.altText"
              width="640"
              height="420"
              loading="lazy"
              decoding="async"
            >
          </div>
          <figcaption>
            <strong>{{ image.label }}</strong>
            <span>{{ image.description }}</span>
          </figcaption>
        </figure>
      </div>
    </section>
  </section>
</template>
