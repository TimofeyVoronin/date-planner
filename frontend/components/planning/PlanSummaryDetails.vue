<script setup lang="ts">
import type { ActivityOptionRecord } from '../../types/activity'
import type { InvitationPlanOption } from '../../types/invitation'
import { formatPlanOptionDate } from '../../utils/planning'

type Props = {
  activity?: ActivityOptionRecord | null
  option: InvitationPlanOption
}

const props = withDefaults(defineProps<Props>(), {
  activity: null,
})
</script>

<template>
  <div class="plan-summary-details">
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
        <small>Место встречи</small>
        <strong>{{ props.option.place }}</strong>
      </div>
    </div>
    <div v-if="props.option.comment" class="plan-summary-details__comment">
      <span aria-hidden="true">💬</span>
      <div>
        <small>Комментарий автора</small>
        <span>{{ props.option.comment }}</span>
      </div>
    </div>
    <div v-if="props.activity" class="plan-summary-details__activity">
      <span aria-hidden="true">✨</span>
      <div>
        <small>Активность</small>
        <strong>{{ props.activity.title }}</strong>
        <span v-if="props.activity.description">{{ props.activity.description }}</span>
        <span v-if="props.activity.place">
          Место активности: {{ props.activity.place }}
        </span>
      </div>
    </div>
  </div>
</template>
