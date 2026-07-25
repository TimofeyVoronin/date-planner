<script setup lang="ts">
import { computed } from 'vue'
import type { BuilderAutosaveStatus } from '../../composables/useBuilderAutosave'
import type { InvitationRecord } from '../../types/invitation'
import type { InvitationImageKey } from '../../types/invitation-image'
import {
  INVITATION_SCREEN_BUTTON_MAX_LENGTH,
  INVITATION_SCREEN_SUBTITLE_MAX_LENGTH,
  INVITATION_SCREEN_TITLE_MAX_LENGTH,
  type InvitationScreenValidationErrors,
} from '../../types/screen'
import InvitationPreviewCard from '../invitation/InvitationPreviewCard.vue'

const props = defineProps<{
  errorMessage: string
  fieldErrors: InvitationScreenValidationErrors
  invitation: InvitationRecord
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
const secondaryButtonText = defineModel<string>('secondaryButtonText', { required: true })
const imageKey = defineModel<InvitationImageKey>('imageKey', { required: true })

const previewScreen = computed(() => ({
  title: title.value,
  subtitle: subtitle.value,
  button_text: buttonText.value,
  secondary_button_text: secondaryButtonText.value,
  image_key: imageKey.value,
}))

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
  <section class="builder-screen-editor" aria-labelledby="builder-screen-editor-title">
    <header class="builder-screen-editor__heading">
      <div>
        <p>Экран 1</p>
        <h3 id="builder-screen-editor-title">Настрой первое впечатление</h3>
        <span>
          Текст и кнопки сразу обновляются в мобильном предпросмотре.
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

    <div class="builder-screen-editor__layout">
      <form
        class="builder-screen-editor__form"
        novalidate
        :aria-busy="status === 'saving'"
        @submit.prevent="emit('saveNow')"
      >
        <div class="form-field">
          <div class="form-field__label-row">
            <label for="builder-screen-title">Главный вопрос</label>
            <span aria-hidden="true">{{ title.length }}/{{ INVITATION_SCREEN_TITLE_MAX_LENGTH }}</span>
          </div>
          <textarea
            id="builder-screen-title"
            v-model="title"
            name="title"
            rows="3"
            required
            :maxlength="INVITATION_SCREEN_TITLE_MAX_LENGTH"
            :aria-invalid="Boolean(fieldErrors.title)"
            :aria-describedby="fieldDescription(
              'builder-screen-title-hint',
              fieldErrors.title && 'builder-screen-title-error',
            )"
          />
          <span id="builder-screen-title-hint" class="form-field__hint">
            Короткий вопрос лучше помещается на экране телефона.
          </span>
          <span
            v-if="fieldErrors.title"
            id="builder-screen-title-error"
            class="form-field__error"
          >
            {{ fieldErrors.title }}
          </span>
        </div>

        <div class="form-field">
          <div class="form-field__label-row">
            <label for="builder-screen-subtitle">
              Подзаголовок <span>(необязательно)</span>
            </label>
            <span aria-hidden="true">
              {{ subtitle.length }}/{{ INVITATION_SCREEN_SUBTITLE_MAX_LENGTH }}
            </span>
          </div>
          <textarea
            id="builder-screen-subtitle"
            v-model="subtitle"
            name="subtitle"
            rows="3"
            :maxlength="INVITATION_SCREEN_SUBTITLE_MAX_LENGTH"
            :aria-invalid="Boolean(fieldErrors.subtitle)"
            :aria-describedby="fieldErrors.subtitle ? 'builder-screen-subtitle-error' : undefined"
          />
          <span
            v-if="fieldErrors.subtitle"
            id="builder-screen-subtitle-error"
            class="form-field__error"
          >
            {{ fieldErrors.subtitle }}
          </span>
        </div>

        <div class="builder-screen-editor__buttons">
          <div class="form-field">
            <div class="form-field__label-row">
              <label for="builder-screen-yes-button">Кнопка «Да»</label>
              <span aria-hidden="true">
                {{ buttonText.length }}/{{ INVITATION_SCREEN_BUTTON_MAX_LENGTH }}
              </span>
            </div>
            <input
              id="builder-screen-yes-button"
              v-model="buttonText"
              name="button_text"
              type="text"
              required
              :maxlength="INVITATION_SCREEN_BUTTON_MAX_LENGTH"
              :aria-invalid="Boolean(fieldErrors.button_text)"
              :aria-describedby="fieldErrors.button_text ? 'builder-screen-yes-error' : undefined"
            >
            <span
              v-if="fieldErrors.button_text"
              id="builder-screen-yes-error"
              class="form-field__error"
            >
              {{ fieldErrors.button_text }}
            </span>
          </div>

          <div class="form-field">
            <div class="form-field__label-row">
              <label for="builder-screen-no-button">Кнопка «Нет»</label>
              <span aria-hidden="true">
                {{ secondaryButtonText.length }}/{{ INVITATION_SCREEN_BUTTON_MAX_LENGTH }}
              </span>
            </div>
            <input
              id="builder-screen-no-button"
              v-model="secondaryButtonText"
              name="secondary_button_text"
              type="text"
              required
              :maxlength="INVITATION_SCREEN_BUTTON_MAX_LENGTH"
              :aria-invalid="Boolean(fieldErrors.secondary_button_text)"
              :aria-describedby="fieldErrors.secondary_button_text
                ? 'builder-screen-no-error'
                : undefined"
            >
            <span
              v-if="fieldErrors.secondary_button_text"
              id="builder-screen-no-error"
              class="form-field__error"
            >
              {{ fieldErrors.secondary_button_text }}
            </span>
          </div>
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

      <aside class="builder-screen-editor__preview" aria-labelledby="builder-live-preview-title">
        <div class="builder-screen-editor__preview-heading">
          <p>Живой предпросмотр</p>
          <h4 id="builder-live-preview-title">Так увидит получатель</h4>
        </div>
        <div class="builder-phone-preview">
          <div class="builder-phone-preview__speaker" aria-hidden="true" />
          <InvitationPreviewCard
            :allow-reset="false"
            :author-name="invitation.author_name"
            :message="invitation.message"
            preview-only
            :recipient-name="invitation.recipient_name"
            :screen="previewScreen"
          />
          <div class="builder-phone-preview__home" aria-hidden="true" />
        </div>
      </aside>
    </div>
  </section>
</template>
