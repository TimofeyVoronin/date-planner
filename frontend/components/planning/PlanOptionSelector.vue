<script setup lang="ts">
import { computed } from 'vue'
import type { InvitationPlanOption } from '../../types/invitation'
import type { InvitationScreenRecord } from '../../types/screen'
import {
  findUsableSelectedPlanOption,
  formatPlanOptionDate,
  getPlanSelectionOptionState,
  getPlanSelectionScreenPresentation,
} from '../../utils/planning'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'

type SaveState = 'error' | 'idle' | 'saved' | 'saving'

type Props = {
  currentTime: Date
  modelValue: string | null
  options: InvitationPlanOption[]
  persistedOptionId?: string | null
  saveError?: string
  saveState?: SaveState
  screen?: InvitationScreenRecord | null
}

const props = withDefaults(defineProps<Props>(), {
  persistedOptionId: null,
  saveError: '',
  saveState: 'idle',
  screen: null,
})
const emit = defineEmits<{
  save: []
  'update:modelValue': [optionId: string]
}>()
const config = useRuntimeConfig()

const presentation = computed(() => getPlanSelectionScreenPresentation(props.screen))
const optionState = computed(() => getPlanSelectionOptionState(
  props.options,
  props.currentTime,
))
const selectableOptions = computed(() => optionState.value.options)
const hasOptions = computed(() => optionState.value.availability !== 'empty')
const hasSelectableOptions = computed(() => optionState.value.availability === 'available')
const activeImage = computed(() => (
  getInvitationImageByKey(presentation.value.imageKey)
  ?? getInvitationImageByKey('date-selection-default')!
))
const activeImageUrl = computed(() => resolveInvitationImageUrl(
  activeImage.value.assetPath,
  config.app.baseURL,
))
const selectedOptionIsUsable = computed(() => Boolean(findUsableSelectedPlanOption(
  selectableOptions.value,
  props.modelValue,
  props.currentTime,
)))
const usablePersistedOptionId = computed(() => findUsableSelectedPlanOption(
  selectableOptions.value,
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
const emptyTitle = computed(() => (
  hasOptions.value ? 'Все предложенные даты уже прошли' : 'Автор ещё готовит варианты'
))
const emptyCopy = computed(() => (
  hasOptions.value
    ? 'Попроси автора предложить новые даты. Прошедшие варианты выбрать повторно нельзя.'
    : 'Ответ уже сохранён. Актуальные даты и места появятся здесь, когда автор их добавит.'
))

function chooseOption(option: InvitationPlanOption): void {
  const selectedOption = findUsableSelectedPlanOption(
    selectableOptions.value,
    option.id,
    props.currentTime,
  )

  if (selectedOption) {
    emit('update:modelValue', selectedOption.id)
  }
}

function requestSave(): void {
  const selectedOption = findUsableSelectedPlanOption(
    selectableOptions.value,
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
    <div class="plan-selector__hero">
      <img
        :src="activeImageUrl"
        :alt="activeImage.altText"
        width="640"
        height="420"
      >
    </div>

    <div class="plan-selector__body">
      <header class="plan-section-heading">
        <p>Выбор даты</p>
        <h2 id="plan-selector-title">{{ presentation.title }}</h2>
        <span v-if="presentation.subtitle">{{ presentation.subtitle }}</span>
      </header>

      <fieldset v-if="hasSelectableOptions" class="plan-selector__options">
        <legend class="sr-only">Актуальные варианты даты и места</legend>
        <label
          v-for="(option, index) in selectableOptions"
          :key="option.id"
          class="plan-choice"
          :class="{
            'plan-choice--checked': props.modelValue === option.id,
          }"
        >
          <input
            type="radio"
            name="plan-option"
            :value="option.id"
            :checked="props.modelValue === option.id"
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
            v-if="usablePersistedOptionId === option.id"
            class="plan-choice__saved-badge"
          >
            Текущий выбор
          </span>
        </label>
      </fieldset>

      <div
        v-else
        class="plan-selector__empty"
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true">{{ hasOptions ? '⌛' : '🗓️' }}</span>
        <div>
          <strong>{{ emptyTitle }}</strong>
          <p>{{ emptyCopy }}</p>
        </div>
      </div>

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
        <template v-else-if="!hasSelectableOptions">Нет актуальных вариантов</template>
        <template v-else-if="!selectedOptionIsUsable">Выбери актуальный вариант</template>
        <template v-else-if="!hasChanges && usablePersistedOptionId">Выбор сохранён</template>
        <template v-else-if="props.saveState === 'error'">Повторить сохранение</template>
        <template v-else>{{ presentation.buttonText }}</template>
      </button>
    </div>
  </section>
</template>
