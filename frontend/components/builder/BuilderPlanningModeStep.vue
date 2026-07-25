<script setup lang="ts">
import { computed } from 'vue'
import type { BuilderAutosaveStatus } from '../../composables/useBuilderAutosave'
import {
  INVITATION_PLANNING_MODES,
  type InvitationPlanningMode,
  type InvitationValidationErrors,
} from '../../types/invitation'
import { getInvitationPlanningModePresentation } from '../../utils/invitations'

const props = defineProps<{
  errorMessage: string
  fieldErrors: InvitationValidationErrors
  isDirty: boolean
  status: BuilderAutosaveStatus
}>()

const emit = defineEmits<{
  retry: []
  saveNow: []
}>()

const planningMode = defineModel<InvitationPlanningMode>('planningMode', { required: true })
const planningModes = INVITATION_PLANNING_MODES
const statusPresentation = computed(() => {
  switch (props.status) {
    case 'dirty':
      return { icon: '●', label: 'Изменения не сохранены', tone: 'dirty' }
    case 'saving':
      return { icon: '⏳', label: 'Сохранение…', tone: 'saving' }
    case 'saved':
      return { icon: '✓', label: 'Сохранено', tone: 'saved' }
    case 'error':
      return { icon: '!', label: 'Не удалось сохранить', tone: 'error' }
    default:
      return { icon: '✓', label: 'Режим сохранён', tone: 'idle' }
  }
})
</script>

<template>
  <form
    class="builder-planning-mode"
    novalidate
    :aria-busy="status === 'saving'"
    @submit.prevent="emit('saveNow')"
  >
    <header class="builder-planning-mode__heading">
      <div>
        <p>Сценарий планирования</p>
        <h3>Когда подготовить варианты даты?</h3>
      </div>
      <span
        class="builder-autosave-badge"
        :class="`builder-autosave-badge--${statusPresentation.tone}`"
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true">{{ statusPresentation.icon }}</span>
        {{ statusPresentation.label }}
      </span>
    </header>

    <p class="builder-planning-mode__description">
      Выбор определяет, на каком этапе автор добавляет даты. Получатель в любом случае увидит
      варианты только после ответа «Да».
    </p>

    <fieldset
      class="creation-mode-fieldset builder-planning-mode__fieldset"
      :aria-describedby="fieldErrors.planning_mode
        ? 'builder-planning-mode-hint builder-planning-mode-error'
        : 'builder-planning-mode-hint'"
    >
      <legend>Выбери один вариант</legend>
      <div class="creation-mode-options builder-planning-mode__options">
        <label
          v-for="mode in planningModes"
          :key="mode"
          class="creation-mode-option"
        >
          <input
            v-model="planningMode"
            class="creation-mode-option__input"
            type="radio"
            name="planning_mode"
            :value="mode"
          >
          <span class="creation-mode-option__surface">
            <span class="creation-mode-option__icon" aria-hidden="true">
              {{ getInvitationPlanningModePresentation(mode).icon }}
            </span>
            <span class="creation-mode-option__copy">
              <strong>{{ getInvitationPlanningModePresentation(mode).label }}</strong>
              <span>{{ getInvitationPlanningModePresentation(mode).description }}</span>
            </span>
            <span class="creation-mode-option__check" aria-hidden="true">✓</span>
          </span>
        </label>
      </div>
      <span id="builder-planning-mode-hint" class="form-field__hint">
        Режим можно изменить только до публикации. При возврате к планированию после согласия
        черновые варианты дат будут очищены.
      </span>
      <span
        v-if="fieldErrors.planning_mode"
        id="builder-planning-mode-error"
        class="form-field__error"
      >
        {{ fieldErrors.planning_mode }}
      </span>
    </fieldset>

    <section class="builder-planning-mode__result" aria-live="polite">
      <span aria-hidden="true">
        {{ getInvitationPlanningModePresentation(planningMode).icon }}
      </span>
      <div>
        <strong>{{ getInvitationPlanningModePresentation(planningMode).label }}</strong>
        <p>{{ getInvitationPlanningModePresentation(planningMode).shortDescription }}</p>
      </div>
    </section>

    <p
      v-if="status === 'error' && errorMessage"
      class="builder-invitation-form__error"
      role="alert"
    >
      {{ errorMessage }}
    </p>

    <div class="builder-invitation-form__actions">
      <button
        v-if="status === 'error'"
        type="button"
        class="builder-invitation-form__retry"
        @click="emit('retry')"
      >
        Повторить
      </button>
      <button
        type="submit"
        class="builder-invitation-form__save-now"
        :disabled="status === 'saving' || !isDirty"
      >
        {{ status === 'saving' ? 'Сохраняем…' : 'Сохранить сейчас' }}
      </button>
    </div>
  </form>
</template>
