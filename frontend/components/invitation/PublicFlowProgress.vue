<script setup lang="ts">
import { computed } from 'vue'
import type { PublicInvitationStage } from '../../utils/publicFlow'
import {
  getPublicFlowCurrentStepIndex,
  getPublicFlowSteps,
} from '../../utils/publicFlow'

type Props = {
  hasActivityOptions: boolean
  stage: PublicInvitationStage
}

const props = defineProps<Props>()
const steps = computed(() => getPublicFlowSteps(props.hasActivityOptions))
const currentStepIndex = computed(() => getPublicFlowCurrentStepIndex(
  props.stage,
  props.hasActivityOptions,
))
const progressStyle = computed(() => `--public-flow-step-count: ${steps.value.length}`)
</script>

<template>
  <nav
    class="public-flow-progress"
    aria-label="Этапы приглашения"
    :style="progressStyle"
  >
    <ol>
      <li
        v-for="(step, index) in steps"
        :key="step.id"
        :aria-current="index === currentStepIndex ? 'step' : undefined"
        :class="{
          'public-flow-progress__item--active': index === currentStepIndex,
          'public-flow-progress__item--complete': index < currentStepIndex,
        }"
      >
        <span class="public-flow-progress__marker" aria-hidden="true">
          {{ index < currentStepIndex ? '✓' : step.icon }}
        </span>
        <span class="public-flow-progress__label">{{ step.label }}</span>
        <span v-if="index < steps.length - 1" class="public-flow-progress__line" aria-hidden="true" />
        <span v-if="index === currentStepIndex" class="sr-only">Текущий этап</span>
      </li>
    </ol>
  </nav>
</template>
