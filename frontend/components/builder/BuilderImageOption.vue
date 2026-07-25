<script setup lang="ts">
import type { InvitationImageRecord } from '../../types/invitation-image'

defineProps<{
  image: InvitationImageRecord
  imageUrl: string
  selected: boolean
  selectable: boolean
}>()

const emit = defineEmits<{
  select: [imageKey: InvitationImageRecord['key']]
}>()
</script>

<template>
  <label
    v-if="selectable"
    class="builder-image-library__card builder-image-library__card--selectable"
    :class="{ 'builder-image-library__card--selected': selected }"
  >
    <input
      class="sr-only"
      type="radio"
      name="invitation_screen_image"
      :value="image.key"
      :checked="selected"
      @change="emit('select', image.key)"
    >
    <span class="builder-image-library__selected-mark" aria-hidden="true">✓</span>
    <span class="builder-image-library__media">
      <img
        :src="imageUrl"
        :alt="image.altText"
        width="640"
        height="420"
        loading="lazy"
        decoding="async"
      >
    </span>
    <span class="builder-image-library__caption">
      <strong>{{ image.label }}</strong>
      <span>{{ image.description }}</span>
    </span>
  </label>

  <figure v-else class="builder-image-library__card">
    <div class="builder-image-library__media">
      <img
        :src="imageUrl"
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
</template>
