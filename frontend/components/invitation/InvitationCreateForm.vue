<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import { copyTextWithFallback } from '../../composables/useClipboard'
import { useInvitationsApi } from '../../composables/useInvitationsApi'
import {
  INVITATION_CREATION_MODES,
  INVITATION_MESSAGE_MAX_LENGTH,
  INVITATION_NAME_MAX_LENGTH,
  type InvitationCreatePayload,
  type InvitationCreationMode,
  type InvitationPublicationStatus,
  type InvitationValidationErrors,
} from '../../types/invitation'
import {
  buildManagementInvitationUrl,
  buildPublicInvitationUrl,
  getInvitationCreationModePresentation,
  hasInvitationValidationErrors,
  normalizeInvitationPayload,
  parseInvitationApiError,
  validateInvitationPayload,
} from '../../utils/invitations'

type CopyTarget = 'management' | 'public'
type CopyState = 'idle' | 'copied' | 'failed'

type CreatedLinks = {
  creationMode: InvitationCreationMode
  management: string
  publicationStatus: InvitationPublicationStatus
  public: string | null
}

const api = useInvitationsApi()
const form = reactive<InvitationCreatePayload>({
  author_name: '',
  recipient_name: '',
  message: '',
  creation_mode: 'quick',
})
const validationErrors = ref<InvitationValidationErrors>({})
const requestError = ref('')
const isSubmitting = ref(false)
const createdLinks = ref<CreatedLinks | null>(null)
const statusHeadingRef = ref<HTMLElement | null>(null)
const creationModes = INVITATION_CREATION_MODES
const selectedModePresentation = computed(() => (
  getInvitationCreationModePresentation(form.creation_mode)
))
const copyState = reactive<Record<CopyTarget, CopyState>>({
  management: 'idle',
  public: 'idle',
})

function fieldDescription(...ids: Array<string | false | undefined>): string | undefined {
  const description = ids.filter((id): id is string => typeof id === 'string').join(' ')

  return description || undefined
}

function focusStatus(): void {
  void nextTick(() => statusHeadingRef.value?.focus())
}

async function submitInvitation(): Promise<void> {
  if (isSubmitting.value) {
    return
  }

  requestError.value = ''
  createdLinks.value = null
  copyState.public = 'idle'
  copyState.management = 'idle'
  validationErrors.value = validateInvitationPayload(form)

  if (hasInvitationValidationErrors(validationErrors.value)) {
    requestError.value = 'Проверь поля формы — некоторые данные нужно исправить.'
    focusStatus()
    return
  }

  isSubmitting.value = true

  try {
    const invitation = await api.createInvitation(normalizeInvitationPayload(form))
    const origin = window.location.origin

    createdLinks.value = {
      creationMode: invitation.creation_mode,
      publicationStatus: invitation.publication_status,
      public: invitation.publication_status === 'published'
        ? buildPublicInvitationUrl(origin, invitation.id)
        : null,
      management: buildManagementInvitationUrl(
        origin,
        invitation.id,
        invitation.management_token,
      ),
    }
    validationErrors.value = {}
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    requestError.value = parsedError.message
    validationErrors.value = parsedError.fieldErrors
  }
  finally {
    isSubmitting.value = false
    focusStatus()
  }
}

async function copyLink(target: CopyTarget): Promise<void> {
  const links = createdLinks.value

  if (!links) {
    return
  }

  const link = links[target]

  if (!link) {
    return
  }

  copyState[target] = await copyTextWithFallback(link) ? 'copied' : 'failed'
}
</script>

<template>
  <section class="create-card" aria-labelledby="create-invitation-title">
    <div class="create-card__heading">
      <p class="create-card__step">Шаг 1</p>
      <h2 id="create-invitation-title">Кого пригласим?</h2>
      <p>Заполни два имени и при желании добавь личное сообщение.</p>
    </div>

    <form class="invitation-form" novalidate @submit.prevent="submitInvitation">
      <fieldset
        class="creation-mode-fieldset"
        :aria-describedby="fieldDescription(
          'creation-mode-hint',
          validationErrors.creation_mode && 'creation-mode-error',
        )"
      >
        <legend>Как хочешь создать приглашение?</legend>
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
        <span id="creation-mode-hint" class="form-field__hint">
          Режим сохраняется вместе с приглашением. Позже его нельзя будет подменить через
          публичную ссылку.
        </span>
        <span
          v-if="validationErrors.creation_mode"
          id="creation-mode-error"
          class="form-field__error"
        >
          {{ validationErrors.creation_mode }}
        </span>
      </fieldset>

      <div class="invitation-form__names">
        <div class="form-field">
          <label for="author-name">Твоё имя</label>
          <input
            id="author-name"
            v-model="form.author_name"
            name="author_name"
            type="text"
            autocomplete="name"
            required
            :maxlength="INVITATION_NAME_MAX_LENGTH"
            placeholder="Например, Саша"
            :aria-invalid="Boolean(validationErrors.author_name)"
            :aria-describedby="fieldDescription(
              'author-name-hint',
              validationErrors.author_name && 'author-name-error',
            )"
          >
          <span id="author-name-hint" class="form-field__hint">Будет видно получателю</span>
          <span
            v-if="validationErrors.author_name"
            id="author-name-error"
            class="form-field__error"
          >
            {{ validationErrors.author_name }}
          </span>
        </div>

        <div class="form-field">
          <label for="recipient-name">Имя получателя</label>
          <input
            id="recipient-name"
            v-model="form.recipient_name"
            name="recipient_name"
            type="text"
            autocomplete="off"
            required
            :maxlength="INVITATION_NAME_MAX_LENGTH"
            placeholder="Например, Женя"
            :aria-invalid="Boolean(validationErrors.recipient_name)"
            :aria-describedby="validationErrors.recipient_name ? 'recipient-name-error' : undefined"
          >
          <span
            v-if="validationErrors.recipient_name"
            id="recipient-name-error"
            class="form-field__error"
          >
            {{ validationErrors.recipient_name }}
          </span>
        </div>
      </div>

      <div class="form-field">
        <div class="form-field__label-row">
          <label for="invitation-message">Личное сообщение <span>(необязательно)</span></label>
          <span aria-hidden="true">{{ form.message.length }}/{{ INVITATION_MESSAGE_MAX_LENGTH }}</span>
        </div>
        <textarea
          id="invitation-message"
          v-model="form.message"
          name="message"
          rows="4"
          :maxlength="INVITATION_MESSAGE_MAX_LENGTH"
          placeholder="Напиши несколько слов, которые поймёте только вы..."
          :aria-invalid="Boolean(validationErrors.message)"
          :aria-describedby="fieldDescription(
            'invitation-message-hint',
            validationErrors.message && 'invitation-message-error',
          )"
        />
        <span id="invitation-message-hint" class="form-field__hint">
          Можно оставить пустым — приглашение всё равно будет персональным.
        </span>
        <span
          v-if="validationErrors.message"
          id="invitation-message-error"
          class="form-field__error"
        >
          {{ validationErrors.message }}
        </span>
      </div>

      <button class="invitation-form__submit" type="submit" :disabled="isSubmitting">
        <span aria-hidden="true">{{ isSubmitting ? '⏳' : '💌' }}</span>
        {{ isSubmitting ? 'Создаём приглашение…' : selectedModePresentation.submitLabel }}
      </button>
    </form>

    <div
      v-if="requestError"
      ref="statusHeadingRef"
      class="form-status form-status--error"
      role="alert"
      tabindex="-1"
    >
      <strong>Не получилось создать приглашение</strong>
      <span>{{ requestError }}</span>
    </div>

    <div
      v-else-if="createdLinks"
      ref="statusHeadingRef"
      class="created-invitation"
      tabindex="-1"
      aria-labelledby="created-invitation-title"
    >
      <div class="created-invitation__intro">
        <span class="created-invitation__icon" aria-hidden="true">✓</span>
        <div>
          <h3 id="created-invitation-title">
            {{ createdLinks.publicationStatus === 'draft'
              ? 'Черновик создан'
              : 'Приглашение готово' }}
          </h3>
          <p>
            {{ createdLinks.publicationStatus === 'draft'
              ? 'Сохрани секретную ссылку и продолжи настройку на странице автора.'
              : 'Отправь получателю только первую ссылку.' }}
          </p>
          <span class="created-invitation__mode">
            {{ getInvitationCreationModePresentation(createdLinks.creationMode).icon }}
            {{ getInvitationCreationModePresentation(createdLinks.creationMode).label }}
          </span>
        </div>
      </div>

      <div v-if="createdLinks.public" class="created-link">
        <label for="public-invitation-link">Публичная ссылка</label>
        <div class="created-link__controls">
          <input
            id="public-invitation-link"
            :value="createdLinks.public"
            type="text"
            readonly
          >
          <button
            type="button"
            :aria-label="copyState.public === 'copied'
              ? 'Публичная ссылка скопирована'
              : 'Скопировать публичную ссылку'"
            @click="copyLink('public')"
          >
            {{ copyState.public === 'copied' ? 'Скопировано' : 'Копировать' }}
          </button>
        </div>
        <a :href="createdLinks.public">Открыть приглашение</a>
        <span v-if="copyState.public === 'failed'" class="created-link__copy-error" role="status">
          Не удалось скопировать автоматически — выдели ссылку вручную.
        </span>
      </div>

      <div
        class="created-link created-link--secret"
        :class="{ 'created-link--draft': createdLinks.publicationStatus === 'draft' }"
      >
        <label for="management-invitation-link">
          {{ createdLinks.publicationStatus === 'draft'
            ? 'Секретная ссылка черновика'
            : 'Секретная ссылка управления' }}
        </label>
        <div class="created-link__controls">
          <input
            id="management-invitation-link"
            :value="createdLinks.management"
            type="text"
            readonly
          >
          <button
            type="button"
            :aria-label="copyState.management === 'copied'
              ? 'Секретная ссылка скопирована'
              : 'Скопировать секретную ссылку управления'"
            @click="copyLink('management')"
          >
            {{ copyState.management === 'copied' ? 'Скопировано' : 'Копировать' }}
          </button>
        </div>
        <a :href="createdLinks.management">
          {{ createdLinks.publicationStatus === 'draft'
            ? 'Продолжить настройку'
            : 'Открыть управление' }}
        </a>
        <span
          v-if="copyState.management === 'failed'"
          class="created-link__copy-error"
          role="status"
        >
          Не удалось скопировать автоматически — выдели ссылку вручную.
        </span>
      </div>

      <p class="created-invitation__warning">
        <span aria-hidden="true">🔐</span>
        <strong>Сохрани секретную ссылку сейчас.</strong>
        Она открывает закрытую страницу автора, восстановить её без аккаунта нельзя.
        <template v-if="createdLinks.publicationStatus === 'draft'">
          Публичная ссылка появится после публикации черновика.
        </template>
        <template v-else>Не отправляй секретную ссылку получателю.</template>
      </p>

      <p class="sr-only" aria-live="polite">
        <template v-if="copyState.public === 'copied'">Публичная ссылка скопирована.</template>
        <template v-if="copyState.management === 'copied'">Секретная ссылка скопирована.</template>
      </p>
    </div>
  </section>
</template>
