<script setup lang="ts">
import { computed } from 'vue'
import type { BuilderAutosaveStatus } from '../../composables/useBuilderAutosave'
import {
  INVITATION_SCREEN_BUTTON_MAX_LENGTH,
  INVITATION_SCREEN_SUBTITLE_MAX_LENGTH,
  INVITATION_SCREEN_TITLE_MAX_LENGTH,
  type InvitationScreenValidationErrors,
} from '../../types/screen'

const props = defineProps<{
  errorMessage: string
  fieldErrors: InvitationScreenValidationErrors
  isDirty: boolean
  status: BuilderAutosaveStatus
}>()

const emit = defineEmits<{
  retry: []
  saveNow: []
}>()

const title = defineModel<string>('title', { required: true })
const subtitle = defineModel<string>('subtitle', { required: true })
const buttonText = defineModel<string>('buttonText', { required: true })

const statusPresentation = computed(() => {
  switch (props.status) {
    case 'dirty':
      return { icon: '●', label: 'Экран не сохранён', tone: 'dirty' }
    case 'saving':
      return { icon: '⏳', label: 'Сохраняем экран…', tone: 'saving' }
    case 'saved':
      return { icon: '✓', label: 'Экран сохранён', tone: 'saved' }
    case 'error':
      return { icon: '!', label: 'Экран не сохранён', tone: 'error' }
    default:
      return { icon: '✓', label: 'Экран синхронизирован', tone: 'idle' }
  }
})

function fieldDescription(...ids: Array<string | false | undefined>): string | undefined {
  const description = ids.filter((id): id is string => typeof id === 'string').join(' ')
  return description || undefined
}
</script>

<template>
  <section class="builder-screen-editor" aria-labelledby="builder-acceptance-editor-title">
    <header class="builder-screen-editor__heading">
      <div>
        <p>Экран 2</p>
        <h3 id="builder-acceptance-editor-title">Настрой момент после ответа «Да»</h3>
        <span>
          Получатель увидит этот экран перед переходом к выбору даты и дальнейшему планированию.
        </span>
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

    <form
      class="builder-screen-editor__form"
      novalidate
      :aria-busy="status === 'saving'"
      @submit.prevent="emit('saveNow')"
    >
      <div class="form-field">
        <div class="form-field__label-row">
          <label for="builder-acceptance-title">Заголовок после согласия</label>
          <span aria-hidden="true">{{ title.length }}/{{ INVITATION_SCREEN_TITLE_MAX_LENGTH }}</span>
        </div>
        <textarea
          id="builder-acceptance-title"
          v-model="title"
          name="title"
          rows="3"
          required
          :maxlength="INVITATION_SCREEN_TITLE_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.title)"
          :aria-describedby="fieldDescription(
            'builder-acceptance-title-hint',
            fieldErrors.title && 'builder-acceptance-title-error',
          )"
        />
        <span id="builder-acceptance-title-hint" class="form-field__hint">
          Короткая эмоциональная фраза лучше воспринимается после ответа «Да».
        </span>
        <span
          v-if="fieldErrors.title"
          id="builder-acceptance-title-error"
          class="form-field__error"
        >
          {{ fieldErrors.title }}
        </span>
      </div>

      <div class="form-field">
        <div class="form-field__label-row">
          <label for="builder-acceptance-subtitle">
            Подзаголовок <span>(необязательно)</span>
          </label>
          <span aria-hidden="true">
            {{ subtitle.length }}/{{ INVITATION_SCREEN_SUBTITLE_MAX_LENGTH }}
          </span>
        </div>
        <textarea
          id="builder-acceptance-subtitle"
          v-model="subtitle"
          name="subtitle"
          rows="3"
          :maxlength="INVITATION_SCREEN_SUBTITLE_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.subtitle)"
          :aria-describedby="fieldErrors.subtitle
            ? 'builder-acceptance-subtitle-error'
            : undefined"
        />
        <span
          v-if="fieldErrors.subtitle"
          id="builder-acceptance-subtitle-error"
          class="form-field__error"
        >
          {{ fieldErrors.subtitle }}
        </span>
      </div>

      <div class="form-field">
        <div class="form-field__label-row">
          <label for="builder-acceptance-button">Кнопка продолжения</label>
          <span aria-hidden="true">
            {{ buttonText.length }}/{{ INVITATION_SCREEN_BUTTON_MAX_LENGTH }}
          </span>
        </div>
        <input
          id="builder-acceptance-button"
          v-model="buttonText"
          name="button_text"
          type="text"
          required
          :maxlength="INVITATION_SCREEN_BUTTON_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.button_text)"
          :aria-describedby="fieldErrors.button_text
            ? 'builder-acceptance-button-error'
            : undefined"
        >
        <span
          v-if="fieldErrors.button_text"
          id="builder-acceptance-button-error"
          class="form-field__error"
        >
          {{ fieldErrors.button_text }}
        </span>
      </div>

      <p v-if="fieldErrors.image_key" class="form-field__error" role="alert">
        {{ fieldErrors.image_key }}
      </p>
      <p v-if="status === 'error'" class="builder-invitation-form__error" role="alert">
        {{ errorMessage }}
      </p>

      <div class="builder-invitation-form__actions">
        <button
          v-if="status === 'error'"
          type="button"
          class="builder-invitation-form__retry"
          @click="emit('retry')"
        >
          Повторить сохранение
        </button>
        <button
          type="submit"
          class="builder-invitation-form__save-now"
          :disabled="!isDirty || status === 'saving'"
        >
          Сохранить экран сейчас
        </button>
      </div>
    </form>
  </section>
</template>
