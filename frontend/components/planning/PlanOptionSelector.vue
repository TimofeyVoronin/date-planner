<script setup lang="ts">
import { computed } from 'vue'
import type { InvitationPlanOption } from '../../types/invitation'
import { formatPlanOptionDate, sortPlanOptions } from '../../utils/planning'

type SaveState = 'error' | 'idle' | 'saved' | 'saving'

type Props = {
  modelValue: string | null
  options: InvitationPlanOption[]
  persistedOptionId?: string | null
  saveError?: string
  saveState?: SaveState
}

const props = withDefaults(defineProps<Props>(), {
  persistedOptionId: null,
  saveError: '',
  saveState: 'idle',
})
const emit = defineEmits<{
  save: []
  'update:modelValue': [optionId: string]
}>()

const sortedOptions = computed(() => sortPlanOptions(props.options))
const hasChanges = computed(() => (
  Boolean(props.modelValue) && props.modelValue !== props.persistedOptionId
))
const canSave = computed(() => (
  Boolean(props.modelValue)
  && props.saveState !== 'saving'
  && (hasChanges.value || props.saveState === 'error')
))

function chooseOption(optionId: string): void {
  emit('update:modelValue', optionId)
}
</script>

<template>
  <section class="plan-selector" aria-labelledby="plan-selector-title">
    <header class="plan-section-heading">
      <p>Почти договорились</p>
      <h2 id="plan-selector-title">Выбери вариант свидания</h2>
      <span>Выбор можно изменить до этапа итогового подтверждения.</span>
    </header>

    <fieldset class="plan-selector__options">
      <legend class="sr-only">Доступные варианты даты и места</legend>
      <label
        v-for="(option, index) in sortedOptions"
        :key="option.id"
        class="plan-choice"
        :class="{
          'plan-choice--checked': props.modelValue === option.id,
          'plan-choice--persisted': props.persistedOptionId === option.id,
        }"
      >
        <input
          type="radio"
          name="plan-option"
          :value="option.id"
          :checked="props.modelValue === option.id"
          @change="chooseOption(option.id)"
        >
        <span class="plan-choice__marker" aria-hidden="true" />
        <span class="plan-choice__number">Вариант {{ index + 1 }}</span>
        <time class="plan-choice__date" :datetime="option.starts_at">
          {{ formatPlanOptionDate(option.starts_at) }}
        </time>
        <strong class="plan-choice__place">{{ option.place }}</strong>
        <span v-if="option.comment" class="plan-choice__comment">{{ option.comment }}</span>
        <span
          v-if="props.persistedOptionId === option.id"
          class="plan-choice__saved-badge"
        >
          Текущий выбор
        </span>
      </label>
    </fieldset>

    <div
      v-if="props.saveState !== 'idle'"
      class="plan-selector__status"
      :class="`plan-selector__status--${props.saveState}`"
      :role="props.saveState === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      <template v-if="props.saveState === 'saving'">Сохраняем твой выбор…</template>
      <template v-else-if="props.saveState === 'saved'">
        Выбор сохранён. Автор приглашения увидит его на своей странице.
      </template>
      <template v-else>{{ props.saveError }}</template>
    </div>

    <button
      class="plan-selector__submit"
      type="button"
      :disabled="!canSave"
      @click="emit('save')"
    >
      <span aria-hidden="true">{{ props.saveState === 'saving' ? '⏳' : '💗' }}</span>
      <template v-if="props.saveState === 'saving'">Сохраняем…</template>
      <template v-else-if="!hasChanges && props.persistedOptionId">Выбор сохранён</template>
      <template v-else-if="props.saveState === 'error'">Повторить сохранение</template>
      <template v-else>Сохранить выбор</template>
    </button>
  </section>
</template>
