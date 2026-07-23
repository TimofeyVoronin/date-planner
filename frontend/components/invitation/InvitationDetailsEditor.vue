<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  INVITATION_CREATION_MODES,
  INVITATION_MESSAGE_MAX_LENGTH,
  INVITATION_NAME_MAX_LENGTH,
  type InvitationCreatePayload,
  type InvitationEditSaveState,
  type InvitationRecord,
  type InvitationUpdatePayload,
  type InvitationValidationErrors,
} from '../../types/invitation'
import {
  buildInvitationUpdatePayload,
  createInvitationEditForm,
  getInvitationCreationModePresentation,
  hasInvitationValidationErrors,
  invitationEditFormHasChanges,
  validateInvitationPayload,
} from '../../utils/invitations'

const props = defineProps<{
  invitation: InvitationRecord
  saveError: string
  saveState: InvitationEditSaveState
  serverFieldErrors: InvitationValidationErrors
}>()

const emit = defineEmits<{
  dirty: [isDirty: boolean]
  save: [payload: InvitationUpdatePayload]
}>()

const form = reactive<InvitationCreatePayload>(createInvitationEditForm(props.invitation))
const localErrors = ref<InvitationValidationErrors>({})
const isLocallyDirty = ref(false)
const creationModes = INVITATION_CREATION_MODES
const hasChanges = computed(() => invitationEditFormHasChanges(form, props.invitation))
const displayedErrors = computed<InvitationValidationErrors>(() => ({
  ...props.serverFieldErrors,
  ...localErrors.value,
}))

function fieldDescription(...ids: Array<string | false | undefined>): string | undefined {
  const description = ids.filter((id): id is string => typeof id === 'string').join(' ')

  return description || undefined
}

function resetForm(): void {
  Object.assign(form, createInvitationEditForm(props.invitation))
  localErrors.value = {}
  isLocallyDirty.value = false
  emit('dirty', false)
}

function submitChanges(): void {
  const validationErrors = validateInvitationPayload(form)

  localErrors.value = validationErrors
  if (hasInvitationValidationErrors(validationErrors)) {
    return
  }

  const payload = buildInvitationUpdatePayload(form, props.invitation)
  if (Object.keys(payload).length === 0) {
    emit('dirty', false)
    return
  }

  emit('save', payload)
}

watch(
  () => [
    props.invitation.author_name,
    props.invitation.recipient_name,
    props.invitation.message,
    props.invitation.creation_mode,
  ] as const,
  () => {
    if (props.saveState === 'saving' || !isLocallyDirty.value || !hasChanges.value) {
      resetForm()
    }
  },
)

watch(
  form,
  () => {
    localErrors.value = {}
    isLocallyDirty.value = hasChanges.value
    emit('dirty', isLocallyDirty.value)
  },
  { deep: true },
)
</script>

<template>
  <section class="invitation-details-editor" aria-labelledby="invitation-editor-title">
    <header class="invitation-details-editor__heading">
      <div>
        <p>Основные данные</p>
        <h2 id="invitation-editor-title">Настрой приглашение</h2>
      </div>
      <span
        v-if="hasChanges"
        class="invitation-details-editor__unsaved"
        role="status"
      >
        Есть несохранённые изменения
      </span>
    </header>

    <p class="invitation-details-editor__description">
      <template v-if="invitation.publication_status === 'published'">
        После сохранения новые имена и сообщение сразу увидит получатель.
      </template>
      <template v-else>
        Черновик останется закрытым, пока ты отдельно не опубликуешь его.
      </template>
    </p>

    <form
      class="invitation-details-editor__form"
      novalidate
      :aria-busy="saveState === 'saving'"
      @submit.prevent="submitChanges"
    >
      <fieldset class="invitation-details-editor__fields" :disabled="saveState === 'saving'">
        <div class="invitation-form__names">
          <div class="form-field">
            <label for="managed-author-name">Твоё имя</label>
            <input
              id="managed-author-name"
              v-model="form.author_name"
              name="author_name"
              type="text"
              autocomplete="name"
              required
              :maxlength="INVITATION_NAME_MAX_LENGTH"
              :aria-invalid="Boolean(displayedErrors.author_name)"
              :aria-describedby="fieldDescription(
                'managed-author-name-hint',
                displayedErrors.author_name && 'managed-author-name-error',
              )"
            >
            <span id="managed-author-name-hint" class="form-field__hint">
              Отображается на публичной странице.
            </span>
            <span
              v-if="displayedErrors.author_name"
              id="managed-author-name-error"
              class="form-field__error"
            >
              {{ displayedErrors.author_name }}
            </span>
          </div>

          <div class="form-field">
            <label for="managed-recipient-name">Имя получателя</label>
            <input
              id="managed-recipient-name"
              v-model="form.recipient_name"
              name="recipient_name"
              type="text"
              autocomplete="off"
              required
              :maxlength="INVITATION_NAME_MAX_LENGTH"
              :aria-invalid="Boolean(displayedErrors.recipient_name)"
              :aria-describedby="fieldDescription(
                'managed-recipient-name-hint',
                displayedErrors.recipient_name && 'managed-recipient-name-error',
              )"
            >
            <span id="managed-recipient-name-hint" class="form-field__hint">
              Используется в тексте приглашения.
            </span>
            <span
              v-if="displayedErrors.recipient_name"
              id="managed-recipient-name-error"
              class="form-field__error"
            >
              {{ displayedErrors.recipient_name }}
            </span>
          </div>
        </div>

        <div class="form-field">
          <div class="form-field__label-row">
            <label for="managed-invitation-message">
              Личное сообщение <span>(необязательно)</span>
            </label>
            <span aria-hidden="true">
              {{ form.message.length }}/{{ INVITATION_MESSAGE_MAX_LENGTH }}
            </span>
          </div>
          <textarea
            id="managed-invitation-message"
            v-model="form.message"
            name="message"
            rows="4"
            :maxlength="INVITATION_MESSAGE_MAX_LENGTH"
            :aria-invalid="Boolean(displayedErrors.message)"
            :aria-describedby="fieldDescription(
              'managed-invitation-message-hint',
              displayedErrors.message && 'managed-invitation-message-error',
            )"
          />
          <span id="managed-invitation-message-hint" class="form-field__hint">
            Можно очистить поле и оставить только основной вопрос.
          </span>
          <span
            v-if="displayedErrors.message"
            id="managed-invitation-message-error"
            class="form-field__error"
          >
            {{ displayedErrors.message }}
          </span>
        </div>

        <fieldset
          class="creation-mode-fieldset invitation-details-editor__modes"
          :aria-describedby="fieldDescription(
            'managed-creation-mode-hint',
            displayedErrors.creation_mode && 'managed-creation-mode-error',
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
                v-model="form.creation_mode"
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
          <span id="managed-creation-mode-hint" class="form-field__hint">
            Смена режима не публикует черновик и не сбрасывает ответ или планирование.
          </span>
          <span
            v-if="displayedErrors.creation_mode"
            id="managed-creation-mode-error"
            class="form-field__error"
          >
            {{ displayedErrors.creation_mode }}
          </span>
        </fieldset>
      </fieldset>

      <p
        v-if="saveState === 'error'"
        class="invitation-details-editor__message invitation-details-editor__message--error"
        role="alert"
      >
        {{ saveError }}
      </p>
      <p
        v-else-if="saveState === 'success'"
        class="invitation-details-editor__message invitation-details-editor__message--success"
        role="status"
        aria-live="polite"
      >
        Изменения сохранены.
      </p>

      <div class="invitation-details-editor__actions">
        <button
          type="button"
          class="invitation-details-editor__reset"
          :disabled="saveState === 'saving' || !hasChanges"
          @click="resetForm"
        >
          Отменить изменения
        </button>
        <button
          type="submit"
          class="invitation-details-editor__save"
          :disabled="saveState === 'saving' || !hasChanges"
        >
          <span aria-hidden="true">{{ saveState === 'saving' ? '⏳' : '✓' }}</span>
          {{ saveState === 'saving' ? 'Сохраняем…' : 'Сохранить изменения' }}
        </button>
      </div>
    </form>
  </section>
</template>
