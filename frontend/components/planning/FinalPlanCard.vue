<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useId, watch } from 'vue'
import type { ActivityOptionRecord } from '../../types/activity'
import type { InvitationPlanOption } from '../../types/invitation'
import {
  DEFAULT_FINAL_TEXT_TEMPLATE,
  buildFinalTemplateContext,
  renderFinalTextTemplateSafely,
} from '../../utils/finalTemplates'
import { formatPlanOptionDate } from '../../utils/planning'
import PlanSummaryDetails from './PlanSummaryDetails.vue'

type Props = {
  activity?: ActivityOptionRecord | null
  announce?: boolean
  authorName: string
  confirmedAt: string
  option: InvitationPlanOption
  recipientName: string
  templateText?: string
}

const props = withDefaults(defineProps<Props>(), {
  activity: null,
  announce: false,
  templateText: DEFAULT_FINAL_TEXT_TEMPLATE,
})
const titleId = useId()
const titleRef = ref<HTMLElement | null>(null)
const renderedText = computed(() => renderFinalTextTemplateSafely(
  props.templateText,
  buildFinalTemplateContext({
    activityTitle: props.activity?.title,
    authorName: props.authorName,
    place: props.option.place,
    recipientName: props.recipientName,
    startsAt: props.option.starts_at,
  }),
))

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
    <p class="final-plan-card__message">{{ renderedText }}</p>
    <PlanSummaryDetails
      :activity="props.activity"
      :option="props.option"
    />
    <p class="final-plan-card__footer">
      <span aria-hidden="true">✓</span>
      Зафиксировано {{ formatPlanOptionDate(props.confirmedAt) }}
    </p>
  </article>
</template>
