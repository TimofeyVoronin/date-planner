<script setup lang="ts">
import { computed } from 'vue'
import type { ActivityOptionRecord } from '../../types/activity'
import type { InvitationScreenRecord } from '../../types/screen'
import {
  findSelectedActivityOption,
  getActivitySelectionScreenPresentation,
  sortActivityOptions,
} from '../../utils/activities'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'

type SaveState = 'error' | 'idle' | 'saved' | 'saving'

type Props = {
  modelValue: string | null
  options: ActivityOptionRecord[]
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

const presentation = computed(() => getActivitySelectionScreenPresentation(props.screen))
const sortedOptions = computed(() => sortActivityOptions(props.options))
const hasOptions = computed(() => sortedOptions.value.length > 0)
const selectedOption = computed(() => findSelectedActivityOption(
  sortedOptions.value,
  props.modelValue,
))
const persistedOption = computed(() => findSelectedActivityOption(
  sortedOptions.value,
  props.persistedOptionId,
))
const hasChanges = computed(() => Boolean(
  selectedOption.value && selectedOption.value.id !== persistedOption.value?.id,
))
const canSave = computed(() => Boolean(
  selectedOption.value
  && props.saveState !== 'saving'
  && (hasChanges.value || props.saveState === 'error'),
))
const showSaveStatus = computed(() => (
  props.saveState !== 'idle'
  && (props.saveState !== 'saved' || Boolean(persistedOption.value))
))
const heroImage = computed(() => (
  getInvitationImageByKey(presentation.value.imageKey)
  ?? getInvitationImageByKey('activity-selection-default')!
))
const heroImageUrl = computed(() => resolveInvitationImageUrl(
  heroImage.value.assetPath,
  config.app.baseURL,
))

function optionImage(option: ActivityOptionRecord) {
  return getInvitationImageByKey(option.image_key)
    ?? getInvitationImageByKey('activity-selection-default')!
}

function optionImageUrl(option: ActivityOptionRecord): string {
  return resolveInvitationImageUrl(optionImage(option).assetPath, config.app.baseURL)
}

function chooseOption(option: ActivityOptionRecord): void {
  emit('update:modelValue', option.id)
}

function requestSave(): void {
  if (selectedOption.value && props.saveState !== 'saving') {
    emit('save')
  }
}
</script>

<template>
  <section class="activity-selector" aria-labelledby="activity-selector-title">
    <div class="activity-selector__hero">
      <img
        :src="heroImageUrl"
        :alt="heroImage.altText"
        width="640"
        height="420"
      >
    </div>

    <div class="activity-selector__body">
      <header class="plan-section-heading">
        <p>Выбор активности</p>
        <h2 id="activity-selector-title">{{ presentation.title }}</h2>
        <span v-if="presentation.subtitle">{{ presentation.subtitle }}</span>
      </header>

      <fieldset v-if="hasOptions" class="activity-selector__options">
        <legend class="sr-only">Доступные варианты активности</legend>
        <label
          v-for="option in sortedOptions"
          :key="option.id"
          class="activity-choice"
          :class="{ 'activity-choice--checked': props.modelValue === option.id }"
        >
          <input
            type="radio"
            name="activity-option"
            :value="option.id"
            :checked="props.modelValue === option.id"
            @change="chooseOption(option)"
          >
          <span class="activity-choice__marker" aria-hidden="true" />
          <img
            :src="optionImageUrl(option)"
            :alt="optionImage(option).altText"
            width="320"
            height="220"
          >
          <span class="activity-choice__copy">
            <strong>{{ option.title }}</strong>
            <span v-if="option.description">{{ option.description }}</span>
            <small v-if="option.place">
              <span aria-hidden="true">📍</span>
              {{ option.place }}
            </small>
            <span
              v-if="persistedOption?.id === option.id"
              class="activity-choice__saved-badge"
            >
              Текущий выбор
            </span>
          </span>
        </label>
      </fieldset>

      <div v-else class="activity-selector__empty" role="status" aria-live="polite">
        <span aria-hidden="true">✨</span>
        <div>
          <strong>Отдельные активности не предложены</strong>
          <p>Дата сохранена. Теперь остаётся дождаться окончательного подтверждения автора.</p>
        </div>
      </div>

      <div
        v-if="showSaveStatus"
        class="activity-selector__status"
        :class="`activity-selector__status--${props.saveState}`"
        :role="props.saveState === 'error' ? 'alert' : 'status'"
        aria-live="polite"
      >
        <template v-if="props.saveState === 'saving'">Сохраняем активность…</template>
        <template v-else-if="props.saveState === 'saved'">
          Активность сохранена. Автор увидит выбранный вариант на секретной странице.
        </template>
        <template v-else>{{ props.saveError }}</template>
      </div>

      <button
        class="activity-selector__submit"
        type="button"
        :disabled="!canSave"
        @click="requestSave"
      >
        <span aria-hidden="true">{{ props.saveState === 'saving' ? '⏳' : '✨' }}</span>
        <template v-if="props.saveState === 'saving'">Сохраняем…</template>
        <template v-else-if="!hasOptions">Активности не требуются</template>
        <template v-else-if="!selectedOption">Выбери активность</template>
        <template v-else-if="!hasChanges && persistedOption">Выбор сохранён</template>
        <template v-else-if="props.saveState === 'error'">Повторить сохранение</template>
        <template v-else>{{ presentation.buttonText }}</template>
      </button>
    </div>
  </section>
</template>
