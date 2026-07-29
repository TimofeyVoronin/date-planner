<script setup lang="ts">
import type { PublicResumeNotice } from '../../utils/publicFlow'

type Props = {
  notice: PublicResumeNotice
}

defineProps<Props>()

const emit = defineEmits<{
  dismiss: []
}>()
</script>

<template>
  <aside
    class="public-resume-notice"
    :class="`public-resume-notice--${notice.tone}`"
    role="status"
    aria-live="polite"
  >
    <span class="public-resume-notice__icon" aria-hidden="true">{{ notice.icon }}</span>
    <div>
      <strong>{{ notice.title }}</strong>
      <p>{{ notice.description }}</p>
    </div>
    <button type="button" aria-label="Скрыть сообщение о восстановлении" @click="emit('dismiss')">
      ×
    </button>
  </aside>
</template>
