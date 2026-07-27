<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { BuilderAutosaveStatus } from '../../composables/useBuilderAutosave'
import {
  INVITATION_SCREEN_SUBTITLE_MAX_LENGTH,
  INVITATION_SCREEN_TITLE_MAX_LENGTH,
  type InvitationScreenValidationErrors,
} from '../../types/screen'
import {
  FINAL_TEMPLATE_MAX_LENGTH,
  FINAL_TEMPLATE_VARIABLES,
  type FinalTemplateVariable,
} from '../../utils/finalTemplates'

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
const templateText = defineModel<string>('templateText', { required: true })
const templateInput = ref<HTMLTextAreaElement | null>(null)
const escapedBracesExample = '{{текст}}'

const statusPresentation = computed(() => {
  switch (props.status) {
    case 'dirty':
      return { icon: '●', label: 'Финальный экран не сохранён', tone: 'dirty' }
    case 'saving':
      return { icon: '⏳', label: 'Сохраняем финальный экран…', tone: 'saving' }
    case 'saved':
      return { icon: '✓', label: 'Финальный экран сохранён', tone: 'saved' }
    case 'error':
      return { icon: '!', label: 'Финальный экран не сохранён', tone: 'error' }
    default:
      return { icon: '✓', label: 'Финальный экран синхронизирован', tone: 'idle' }
  }
})

function formatTemplateVariable(variable: FinalTemplateVariable): string {
  return `{${variable}}`
}

async function insertTemplateVariable(variable: FinalTemplateVariable): Promise<void> {
  const token = formatTemplateVariable(variable)
  const input = templateInput.value

  if (!input) {
    templateText.value += token
    return
  }

  const start = input.selectionStart ?? templateText.value.length
  const end = input.selectionEnd ?? start
  templateText.value = `${templateText.value.slice(0, start)}${token}${templateText.value.slice(end)}`

  await nextTick()
  input.focus()
  input.setSelectionRange(start + token.length, start + token.length)
}

function fieldDescription(...ids: Array<string | false | undefined>): string | undefined {
  const description = ids.filter((id): id is string => typeof id === 'string').join(' ')
  return description || undefined
}
</script>

<template>
  <section class="builder-screen-editor builder-final-editor" aria-labelledby="builder-final-editor-title">
    <header class="builder-screen-editor__heading">
      <div>
        <p>Финальный экран</p>
        <h3 id="builder-final-editor-title">Настрой итоговое впечатление</h3>
        <span>
          Заголовок, описание, иллюстрация и безопасный шаблон сразу обновляются в предпросмотре.
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
          <label for="builder-final-title">Заголовок</label>
          <span aria-hidden="true">{{ title.length }}/{{ INVITATION_SCREEN_TITLE_MAX_LENGTH }}</span>
        </div>
        <textarea
          id="builder-final-title"
          v-model="title"
          name="title"
          rows="2"
          required
          :maxlength="INVITATION_SCREEN_TITLE_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.title)"
          :aria-describedby="fieldDescription(
            'builder-final-title-hint',
            fieldErrors.title && 'builder-final-title-error',
          )"
        />
        <span id="builder-final-title-hint" class="form-field__hint">
          Эта фраза станет главным заголовком подтверждённого плана.
        </span>
        <span
          v-if="fieldErrors.title"
          id="builder-final-title-error"
          class="form-field__error"
        >
          {{ fieldErrors.title }}
        </span>
      </div>

      <div class="form-field">
        <div class="form-field__label-row">
          <label for="builder-final-subtitle">
            Описание <span>(необязательно)</span>
          </label>
          <span aria-hidden="true">
            {{ subtitle.length }}/{{ INVITATION_SCREEN_SUBTITLE_MAX_LENGTH }}
          </span>
        </div>
        <textarea
          id="builder-final-subtitle"
          v-model="subtitle"
          name="subtitle"
          rows="3"
          :maxlength="INVITATION_SCREEN_SUBTITLE_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.subtitle)"
          :aria-describedby="fieldErrors.subtitle ? 'builder-final-subtitle-error' : undefined"
        />
        <span
          v-if="fieldErrors.subtitle"
          id="builder-final-subtitle-error"
          class="form-field__error"
        >
          {{ fieldErrors.subtitle }}
        </span>
      </div>

      <div class="form-field builder-final-editor__template-field">
        <div class="form-field__label-row">
          <label for="builder-final-template">Персональный итоговый текст</label>
          <span aria-hidden="true">
            {{ templateText.length }}/{{ FINAL_TEMPLATE_MAX_LENGTH }}
          </span>
        </div>
        <textarea
          id="builder-final-template"
          ref="templateInput"
          v-model="templateText"
          name="template_text"
          rows="7"
          required
          :maxlength="FINAL_TEMPLATE_MAX_LENGTH"
          :aria-invalid="Boolean(fieldErrors.template_text)"
          :aria-describedby="fieldDescription(
            'builder-final-template-hint',
            fieldErrors.template_text && 'builder-final-template-error',
          )"
        />
        <span id="builder-final-template-hint" class="form-field__hint">
          Переменные заменяются обычным текстом выбранного плана. Произвольный код и обращения к
          полям объектов не выполняются.
        </span>
        <span
          v-if="fieldErrors.template_text"
          id="builder-final-template-error"
          class="form-field__error"
        >
          {{ fieldErrors.template_text }}
        </span>
      </div>

      <div class="builder-final-editor__variables">
        <strong>Вставить переменную в позицию курсора</strong>
        <div role="group" aria-label="Разрешённые переменные финального текста">
          <button
            v-for="variable in FINAL_TEMPLATE_VARIABLES"
            :key="variable"
            type="button"
            @click="insertTemplateVariable(variable)"
          >
            <code>{{ formatTemplateVariable(variable) }}</code>
          </button>
        </div>
        <p>
          Для обычных фигурных скобок используй двойную запись:
          <code>{{ escapedBracesExample }}</code>.
        </p>
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
          Сохранить финальный экран сейчас
        </button>
      </div>
    </form>
  </section>
</template>
