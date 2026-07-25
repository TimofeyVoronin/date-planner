<script setup lang="ts">
import { computed } from 'vue'
import type { InvitationImageKey } from '../../types/invitation-image'
import type { InvitationScreenType } from '../../types/screen'
import {
  getInvitationImagesForScreens,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'
import { getInvitationScreenPresentation } from '../../utils/screens'
import BuilderImageOption from './BuilderImageOption.vue'

const props = withDefaults(defineProps<{
  editableScreenType?: InvitationScreenType | null
  screenTypes: readonly InvitationScreenType[]
  selectedImageKey?: InvitationImageKey | null
}>(), {
  editableScreenType: null,
  selectedImageKey: null,
})

const emit = defineEmits<{
  selectImage: [imageKey: InvitationImageKey]
}>()

const config = useRuntimeConfig()
const imagesByScreen = computed(() => props.screenTypes.map(screenType => ({
  screenType,
  presentation: getInvitationScreenPresentation(screenType),
  images: getInvitationImagesForScreens([screenType]),
})))
const hasSelectableGroup = computed(() => (
  props.editableScreenType != null && props.screenTypes.includes(props.editableScreenType)
))

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
      <template v-if="hasSelectableGroup">
        Выбери иллюстрацию первого экрана. Розовая рамка показывает вариант, который будет сохранён
        и показан получателю.
      </template>
      <template v-else>
        Все изображения хранятся внутри проекта, не загружаются со сторонних сайтов и уже имеют
        доступное текстовое описание.
      </template>
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
          <p>
            {{ group.presentation.description }}
            <strong v-if="group.screenType === editableScreenType"> Выбери один вариант.</strong>
          </p>
        </div>
      </div>

      <div class="builder-image-library__grid">
        <BuilderImageOption
          v-for="image in group.images"
          :key="image.key"
          :image="image"
          :image-url="imageUrl(image.assetPath)"
          :selectable="group.screenType === editableScreenType"
          :selected="image.key === selectedImageKey"
          @select="emit('selectImage', $event)"
        />
      </div>
    </section>
  </section>
</template>
