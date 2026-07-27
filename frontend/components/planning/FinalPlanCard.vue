<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useId, watch } from 'vue'
import type { ActivityOptionRecord } from '../../types/activity'
import type { InvitationPlanOption } from '../../types/invitation'
import type { InvitationScreenRecord } from '../../types/screen'
import {
  DEFAULT_FINAL_TEXT_TEMPLATE,
  buildFinalTemplateContext,
  renderFinalTextTemplateSafely,
} from '../../utils/finalTemplates'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'
import { formatPlanOptionDate } from '../../utils/planning'
import PlanSummaryDetails from './PlanSummaryDetails.vue'

type Props = {
  activity?: ActivityOptionRecord | null
  announce?: boolean
  authorName: string
  confirmedAt: string
  option: InvitationPlanOption
  recipientName: string
  screen?: InvitationScreenRecord | null
  templateText?: string
}

const props = withDefaults(defineProps<Props>(), {
  activity: null,
  announce: false,
  screen: null,
  templateText: DEFAULT_FINAL_TEXT_TEMPLATE,
})
const config = useRuntimeConfig()
const titleId = useId()
const titleRef = ref<HTMLElement | null>(null)
const templateText = computed(() => (
  props.screen?.template_text || props.templateText || DEFAULT_FINAL_TEXT_TEMPLATE
))
const renderedText = computed(() => renderFinalTextTemplateSafely(
  templateText.value,
  buildFinalTemplateContext({
    activityTitle: props.activity?.title,
    authorName: props.authorName,
    place: props.option.place,
    recipientName: props.recipientName,
    startsAt: props.option.starts_at,
  }),
))
const finalImage = computed(() => (
  props.screen ? getInvitationImageByKey(props.screen.image_key) : null
))
const finalImageUrl = computed(() => (
  finalImage.value
    ? resolveInvitationImageUrl(finalImage.value.assetPath, config.app.baseURL)
    : null
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
      {{ props.screen?.title || 'Свидание подтверждено!' }}
    </h2>
    <p v-if="props.screen?.subtitle" class="final-plan-card__subtitle">
      {{ props.screen.subtitle }}
    </p>
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
