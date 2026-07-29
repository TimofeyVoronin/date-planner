<script setup lang="ts">
import { computed, useId } from 'vue'

type Props = {
  canChangeDecision?: boolean
  isSaving?: boolean
  recipientName?: string
}

const props = withDefaults(defineProps<Props>(), {
  canChangeDecision: true,
  isSaving: false,
  recipientName: '',
})

const emit = defineEmits<{
  accept: []
}>()

const titleId = `${useId()}-declined-title`
const title = computed(() => (
  props.recipientName
    ? `${props.recipientName}, спасибо за честный ответ`
    : 'Спасибо за честный ответ'
))
</script>

<template>
  <section class="public-declined-card" :aria-labelledby="titleId">
    <span class="public-declined-card__icon" aria-hidden="true">🌷</span>
    <p class="public-declined-card__eyebrow">Ответ сохранён</p>
    <h2 :id="titleId">{{ title }}</h2>
    <p class="public-declined-card__copy">
      Никаких дополнительных действий не требуется. Можно спокойно закрыть эту страницу.
    </p>
    <p v-if="canChangeDecision" class="public-declined-card__change-note">
      Если решение изменится до окончательного подтверждения плана, согласиться можно здесь.
    </p>
    <button
      v-if="canChangeDecision"
      type="button"
      :disabled="isSaving"
      @click="emit('accept')"
    >
      {{ isSaving ? 'Сохраняем решение…' : 'Всё-таки согласиться' }}
    </button>
  </section>
</template>
