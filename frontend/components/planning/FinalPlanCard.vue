<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useId, watch } from 'vue'
import type { ConfirmedPlanRecord } from '../../types/invitation'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'
import {
  confirmedPlanToActivity,
  confirmedPlanToOption,
  formatPlanOptionDate,
} from '../../utils/planning'
import PlanSummaryDetails from './PlanSummaryDetails.vue'

type Props = {
  announce?: boolean
  plan: ConfirmedPlanRecord
}

const props = withDefaults(defineProps<Props>(), {
  announce: false,
})
const config = useRuntimeConfig()
const titleId = useId()
const titleRef = ref<HTMLElement | null>(null)
const finalImage = computed(() => getInvitationImageByKey(props.plan.final_image_key))
const finalImageUrl = computed(() => (
  finalImage.value
    ? resolveInvitationImageUrl(finalImage.value.assetPath, config.app.baseURL)
    : null
))
const option = computed(() => confirmedPlanToOption(props.plan))
const activity = computed(() => confirmedPlanToActivity(props.plan))

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
    <div v-if="finalImageUrl" class="final-plan-card__image">
      <img
        :src="finalImageUrl"
        :alt="finalImage?.altText ?? ''"
        width="640"
        height="420"
      >
    </div>
    <div v-else class="final-plan-card__icon" aria-hidden="true">💞</div>
    <p>Итоговый план</p>
    <h2
      :id="titleId"
      ref="titleRef"
      :tabindex="props.announce ? -1 : undefined"
    >
      {{ props.plan.final_title }}
    </h2>
    <p v-if="props.plan.final_subtitle" class="final-plan-card__subtitle">
      {{ props.plan.final_subtitle }}
    </p>
    <p class="final-plan-card__message">{{ props.plan.final_text }}</p>
    <PlanSummaryDetails
      :activity="activity"
      :option="option"
    />
    <p class="final-plan-card__footer">
      <span aria-hidden="true">✓</span>
      Зафиксировано
      {{ formatPlanOptionDate(props.plan.confirmed_at, props.plan.time_zone) }}
    </p>
  </article>
</template>
