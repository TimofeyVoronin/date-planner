<script setup lang="ts">
import { computed } from 'vue'
import type { BuilderAutosaveStatus } from '../../composables/useBuilderAutosave'
import {
  INVITATION_CREATION_MODES,
  INVITATION_MESSAGE_MAX_LENGTH,
  INVITATION_NAME_MAX_LENGTH,
  type InvitationCreationMode,
  type InvitationValidationErrors,
} from '../../types/invitation'
import { getInvitationCreationModePresentation } from '../../utils/invitations'

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

const authorName = defineModel<string>('authorName', { required: true })
const recipientName = defineModel<string>('recipientName', { required: true })
const message = defineModel<string>('message', { required: true })
const creationMode = defineModel<InvitationCreationMode>('creationMode', { required: true })
const creationModes = INVITATION_CREATION_MODES
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
      return { icon: '✓', label: 'Все изменения сохранены', tone: 'idle' }
  }
})

function fieldDescription(...ids: Array<string | false | undefined>): string | undefined {
  const description = ids.filter((id): id is string => typeof id === 'string').join(' ')

  return description || undefined
}
</script>

<template>
  <form
    class="builder-invitation-form"
    novalidate
    :aria-busy="status === 'saving'"
    @submit.prevent="emit('saveNow')"
  >
    <header class="builder-invitation-form__heading">
      <div>
        <p>Основные данные</p>
        <h3>Кому и от кого приглашение</h3>
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

    <p class="builder-invitation-form__description">
      Можно продолжать печатать во время сохранения: сервис поставит последнее изменение в очередь
      и отправит его следом.
    </p>

    <div class="invitation-form__names">
      <div class="form-field">
        <label for="builder-author-name">Твоё имя</label>
        <input
          id="builder-author-name"
          v-model="authorName"
          name="author_name"
          type="text"
          autocomplete="name"
          required
          :maxlength="INVITATION_NAME_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.author_name)"
          :aria-describedby="fieldDescription(
            'builder-author-name-hint',
            fieldErrors.author_name && 'builder-author-name-error',
          )"
        >
        <span id="builder-author-name-hint" class="form-field__hint">
          Получатель увидит это имя на публичной странице.
        </span>
        <span
          v-if="fieldErrors.author_name"
          id="builder-author-name-error"
          class="form-field__error"
        >
          {{ fieldErrors.author_name }}
        </span>
      </div>

      <div class="form-field">
        <label for="builder-recipient-name">Имя получателя</label>
        <input
          id="builder-recipient-name"
          v-model="recipientName"
          name="recipient_name"
          type="text"
          autocomplete="off"
          required
          :maxlength="INVITATION_NAME_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.recipient_name)"
          :aria-describedby="fieldDescription(
            'builder-recipient-name-hint',
            fieldErrors.recipient_name && 'builder-recipient-name-error',
          )"
        >
        <span id="builder-recipient-name-hint" class="form-field__hint">
          Имя будет использоваться в тексте приглашения.
        </span>
        <span
          v-if="fieldErrors.recipient_name"
          id="builder-recipient-name-error"
          class="form-field__error"
        >
          {{ fieldErrors.recipient_name }}
        </span>
      </div>
    </div>

    <div class="form-field">
      <div class="form-field__label-row">
        <label for="builder-invitation-message">
          Личное сообщение <span>(необязательно)</span>
        </label>
        <span aria-hidden="true">{{ message.length }}/{{ INVITATION_MESSAGE_MAX_LENGTH }}</span>
      </div>
      <textarea
        id="builder-invitation-message"
        v-model="message"
        name="message"
        rows="5"
        :maxlength="INVITATION_MESSAGE_MAX_LENGTH"
        :aria-invalid="Boolean(fieldErrors.message)"
        :aria-describedby="fieldDescription(
          'builder-invitation-message-hint',
          fieldErrors.message && 'builder-invitation-message-error',
        )"
      />
      <span id="builder-invitation-message-hint" class="form-field__hint">
        Оставь поле пустым, если достаточно основного вопроса.
      </span>
      <span
        v-if="fieldErrors.message"
        id="builder-invitation-message-error"
        class="form-field__error"
      >
        {{ fieldErrors.message }}
      </span>
    </div>

    <fieldset
      class="creation-mode-fieldset builder-invitation-form__modes"
      :aria-describedby="fieldDescription(
        'builder-creation-mode-hint',
        fieldErrors.creation_mode && 'builder-creation-mode-error',
      )"
    >
      <legend>Режим настройки</legend>
      <div class="creation-mode-options">
        <label
          v-for="mode in creationModes"
          :key="mode"
          class="creation-mode-option"
        >
          <input
            v-model="creationMode"
            class="creation-mode-option__input"
            type="radio"
            name="creation_mode"
            :value="mode"
          >
          <span class="creation-mode-option__surface">
            <span class="creation-mode-option__icon" aria-hidden="true">
              {{ getInvitationCreationModePresentation(mode).icon }}
            </span>
            <span class="creation-mode-option__copy">
              <strong>{{ getInvitationCreationModePresentation(mode).label }}</strong>
              <span>{{ getInvitationCreationModePresentation(mode).description }}</span>
            </span>
            <span class="creation-mode-option__check" aria-hidden="true">✓</span>
          </span>
        </label>
      </div>
      <span id="builder-creation-mode-hint" class="form-field__hint">
        При переходе в быстрый режим конструктор сохранит изменение и вернёт тебя к обычному
        управлению приглашением.
      </span>
      <span
        v-if="fieldErrors.creation_mode"
        id="builder-creation-mode-error"
        class="form-field__error"
      >
        {{ fieldErrors.creation_mode }}
      </span>
    </fieldset>

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
        Сохранить сейчас
      </button>
    </div>
  </form>
</template>
