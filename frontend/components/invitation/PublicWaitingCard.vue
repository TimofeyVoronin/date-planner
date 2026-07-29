<script setup lang="ts">
import type { ActivityOptionRecord } from '../../types/activity'
import type { InvitationPlanOption } from '../../types/invitation'
import PlanSummaryDetails from '../planning/PlanSummaryDetails.vue'

type RefreshState = 'error' | 'idle' | 'loading'

type Props = {
  activity?: ActivityOptionRecord | null
  option: InvitationPlanOption
  refreshError?: string
  refreshState?: RefreshState
}

const props = withDefaults(defineProps<Props>(), {
  activity: null,
  refreshError: '',
  refreshState: 'idle',
})
const emit = defineEmits<{
  refresh: []
}>()
</script>

<template>
  <article class="public-waiting-card" aria-labelledby="public-waiting-title">
    <div class="public-waiting-card__icon" aria-hidden="true">💌</div>
    <p>Выбор отправлен автору</p>
    <h2 id="public-waiting-title">Осталось дождаться подтверждения</h2>
    <span>
      Дата<span v-if="props.activity"> и активность</span> сохранена. Автор увидит выбранный
      план на своей секретной странице и зафиксирует его целиком.
    </span>

    <PlanSummaryDetails :activity="props.activity" :option="props.option" />

    <div
      v-if="props.refreshState === 'error'"
      class="public-waiting-card__error"
      role="alert"
    >
      {{ props.refreshError }}
    </div>

    <button
      type="button"
      :disabled="props.refreshState === 'loading'"
      @click="emit('refresh')"
    >
      <span aria-hidden="true">{{ props.refreshState === 'loading' ? '⏳' : '↻' }}</span>
      {{ props.refreshState === 'loading' ? 'Проверяем…' : 'Проверить статус' }}
    </button>
  </article>
</template>
