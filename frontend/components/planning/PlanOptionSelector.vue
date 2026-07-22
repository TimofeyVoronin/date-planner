<script setup lang="ts">
import { computed } from 'vue'
import type { InvitationPlanOption } from '../../types/invitation'
import {
  findUsableSelectedPlanOption,
  formatPlanOptionDate,
  isPlanOptionExpired,
  sortPlanOptions,
} from '../../utils/planning'

type SaveState = 'error' | 'idle' | 'saved' | 'saving'

type Props = {
  currentTime: Date
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
const futureOptions = computed(() => sortedOptions.value.filter(option => (
  !isPlanOptionExpired(option, props.currentTime)
)))
const hasFutureOptions = computed(() => futureOptions.value.length > 0)
const selectedOptionIsUsable = computed(() => Boolean(findUsableSelectedPlanOption(
  sortedOptions.value,
  props.modelValue,
  props.currentTime,
)))
const usablePersistedOptionId = computed(() => findUsableSelectedPlanOption(
  sortedOptions.value,
  props.persistedOptionId,
  props.currentTime,
)?.id ?? null)
const hasChanges = computed(() => (
  selectedOptionIsUsable.value && props.modelValue !== usablePersistedOptionId.value
))
const canSave = computed(() => (
  selectedOptionIsUsable.value
  && props.saveState !== 'saving'
  && (hasChanges.value || props.saveState === 'error')
))
const showSaveStatus = computed(() => (
  props.saveState !== 'idle'
  && (props.saveState !== 'saved' || Boolean(usablePersistedOptionId.value))
))

function optionIsExpired(option: InvitationPlanOption): boolean {
  return isPlanOptionExpired(option, props.currentTime)
}

function chooseOption(option: InvitationPlanOption): void {
  if (!isPlanOptionExpired(option, props.currentTime)) {
    emit('update:modelValue', option.id)
  }
}

function requestSave(): void {
  const selectedOption = findUsableSelectedPlanOption(
    sortedOptions.value,
    props.modelValue,
    props.currentTime,
  )

  if (selectedOption && props.saveState !== 'saving') {
    emit('save')
  }
}
</script>

<template>
  <section class="plan-selector" aria-labelledby="plan-selector-title">
    <header class="plan-section-heading">
      <p>Почти договорились</p>
      <h2 id="plan-selector-title">Выбери вариант свидания</h2>
      <span v-if="hasFutureOptions">
        Выбор можно изменить до этапа итогового подтверждения.
      </span>
      <span v-else>
        Все предложенные даты уже прошли. Автору нужно обновить варианты.
      </span>
    </header>

    <fieldset class="plan-selector__options">
      <legend class="sr-only">Предложенные варианты даты и места</legend>
      <label
        v-for="(option, index) in sortedOptions"
        :key="option.id"
        class="plan-choice"
        :class="{
          'plan-choice--checked': props.modelValue === option.id && !optionIsExpired(option),
          'plan-choice--expired': optionIsExpired(option),
        }"
      >
        <input
          type="radio"
          name="plan-option"
          :value="option.id"
          :checked="props.modelValue === option.id && !optionIsExpired(option)"
          :disabled="optionIsExpired(option)"
          :aria-describedby="optionIsExpired(option)
            ? `plan-option-expired-${option.id}`
            : undefined"
          @change="chooseOption(option)"
        >
        <span class="plan-choice__marker" aria-hidden="true" />
        <span class="plan-choice__number">Вариант {{ index + 1 }}</span>
        <time class="plan-choice__date" :datetime="option.starts_at">
          {{ formatPlanOptionDate(option.starts_at) }}
        </time>
        <strong class="plan-choice__place">{{ option.place }}</strong>
        <span v-if="option.comment" class="plan-choice__comment">{{ option.comment }}</span>
        <span
          v-if="optionIsExpired(option)"
          :id="`plan-option-expired-${option.id}`"
          class="plan-choice__expired-badge"
        >
          Время прошло
        </span>
        <span
          v-else-if="usablePersistedOptionId === option.id"
          class="plan-choice__saved-badge"
        >
          Текущий выбор
        </span>
      </label>
    </fieldset>

    <p
      v-if="!hasFutureOptions"
      class="plan-selector__empty"
      role="status"
      aria-live="polite"
    >
      Попроси автора заменить прошедшие даты. После обновления здесь снова появится доступный выбор.
    </p>

    <div
      v-if="showSaveStatus"
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
      @click="requestSave"
    >
      <span aria-hidden="true">{{ props.saveState === 'saving' ? '⏳' : '💗' }}</span>
      <template v-if="props.saveState === 'saving'">Сохраняем…</template>
      <template v-else-if="!hasFutureOptions">Нет актуальных вариантов</template>
      <template v-else-if="!selectedOptionIsUsable">Выбери актуальный вариант</template>
      <template v-else-if="!hasChanges && usablePersistedOptionId">Выбор сохранён</template>
      <template v-else-if="props.saveState === 'error'">Повторить сохранение</template>
      <template v-else>Сохранить выбор</template>
    </button>
  </section>
</template>
