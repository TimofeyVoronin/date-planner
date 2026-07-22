<script setup lang="ts">
import { nextTick, onMounted, ref, useId, watch } from 'vue'
import type { InvitationPlanOption } from '../../types/invitation'
import { formatPlanOptionDate } from '../../utils/planning'

type Props = {
  announce?: boolean
  confirmedAt: string
  option: InvitationPlanOption
}

const props = withDefaults(defineProps<Props>(), {
  announce: false,
})
const titleId = useId()
const titleRef = ref<HTMLElement | null>(null)

function focusTitle(): void {
  void nextTick(() => titleRef.value?.focus())
}

onMounted(() => {
  if (props.announce) {
    focusTitle()
  }
})

watch(
  () => props.announce,
  (announce, previousValue) => {
    if (announce && !previousValue) {
      focusTitle()
    }
  },
)
</script>

<template>
  <article
    class="final-plan-card"
    :aria-labelledby="titleId"
    :aria-live="props.announce ? 'polite' : undefined"
    :aria-atomic="props.announce ? 'true' : undefined"
  >
    <span class="final-plan-card__spark final-plan-card__spark--left" aria-hidden="true">✦</span>
    <span class="final-plan-card__spark final-plan-card__spark--right" aria-hidden="true">✦</span>
    <div class="final-plan-card__icon" aria-hidden="true">💞</div>
    <p>Итоговый план</p>
    <h2
      :id="titleId"
      ref="titleRef"
      :tabindex="props.announce ? -1 : undefined"
    >
      Свидание подтверждено!
    </h2>
    <div class="final-plan-card__details">
      <div>
        <span aria-hidden="true">🗓️</span>
        <div>
          <small>Дата и время</small>
          <time :datetime="props.option.starts_at">
            {{ formatPlanOptionDate(props.option.starts_at) }}
          </time>
        </div>
      </div>
      <div>
        <span aria-hidden="true">📍</span>
        <div>
          <small>Место</small>
          <strong>{{ props.option.place }}</strong>
        </div>
      </div>
      <div v-if="props.option.comment" class="final-plan-card__comment">
        <span aria-hidden="true">💬</span>
        <div>
          <small>Комментарий</small>
          <span>{{ props.option.comment }}</span>
        </div>
      </div>
    </div>
    <p class="final-plan-card__footer">
      <span aria-hidden="true">✓</span>
      Зафиксировано {{ formatPlanOptionDate(props.confirmedAt) }}
    </p>
  </article>
</template>
