<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  MAX_PLAN_OPTIONS,
  MIN_PLAN_OPTIONS,
  PLAN_OPTION_COMMENT_MAX_LENGTH,
  PLAN_OPTION_PLACE_MAX_LENGTH,
  type InvitationPlanOption,
  type PlanOptionsPayload,
} from '../../types/invitation'
import {
  getMinimumPlanDateTime,
  planDraftsToPayload,
  planOptionDraftsHaveChanges,
  planOptionToDraft,
  sortPlanOptions,
  validatePlanOptionDrafts,
  type PlanOptionDraft,
  type PlanOptionDraftErrors,
} from '../../utils/planning'

type PlanOptionsSaveState = 'error' | 'idle' | 'saving' | 'success'

type EditorVariant = 'builder' | 'management'
type EditorRow = PlanOptionDraft & { key: number }

type Props = {
  currentTime: Date
  options: InvitationPlanOption[]
  saveError?: string
  saveState?: PlanOptionsSaveState
  variant?: EditorVariant
}

const props = withDefaults(defineProps<Props>(), {
  saveError: '',
  saveState: 'idle',
  variant: 'management',
})
const emit = defineEmits<{
  dirtyChange: [isDirty: boolean]
  edited: []
  draftsChange: [drafts: PlanOptionDraft[]]
  save: [payload: PlanOptionsPayload]
}>()

const rows = ref<EditorRow[]>([])
const baselineDrafts = ref<PlanOptionDraft[]>([])
const optionErrors = ref<PlanOptionDraftErrors[]>([])
const formError = ref('')
const statusRef = ref<HTMLElement | null>(null)
const minimumDateTime = computed(() => getMinimumPlanDateTime(props.currentTime))
const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'часовой пояс устройства'
let nextKey = 0
let persistedFingerprint = ''

const drafts = computed<PlanOptionDraft[]>(() => rows.value.map(({ startsAt, place, comment }) => ({
  startsAt,
  place,
  comment,
})))
const isDirty = computed(() => (
  planOptionDraftsHaveChanges(drafts.value, baselineDrafts.value)
))
const canAdd = computed(() => rows.value.length < MAX_PLAN_OPTIONS)
const canRemove = computed(() => rows.value.length > MIN_PLAN_OPTIONS)
const isSaving = computed(() => props.saveState === 'saving')
const canSubmit = computed(() => isDirty.value && !isSaving.value)
const copy = computed(() => props.variant === 'builder'
  ? {
      eyebrow: 'Варианты до публикации',
      title: 'Подготовь даты и места',
      description: (
        `Добавь от ${MIN_PLAN_OPTIONS} до ${MAX_PLAN_OPTIONS} вариантов. `
        + 'Они сохранятся в черновике и станут видны получателю только после ответа «Да».'
      ),
      success: 'Варианты сохранены в черновике и готовы к публикации.',
      submit: 'Сохранить варианты в черновике',
    }
  : {
      eyebrow: 'Следующий шаг',
      title: 'Предложи варианты свидания',
      description: (
        `Добавь от ${MIN_PLAN_OPTIONS} до ${MAX_PLAN_OPTIONS} вариантов. `
        + 'Получатель выберет один на своей странице.'
      ),
      success: 'Варианты сохранены — получатель сможет выбрать один по публичной ссылке.',
      submit: 'Сохранить варианты',
    })
const statusPresentation = computed(() => {
  if (props.saveState === 'saving') {
    return { icon: '⏳', label: 'Сохранение…', tone: 'saving' }
  }
  if (props.saveState === 'error') {
    return { icon: '!', label: 'Не удалось сохранить', tone: 'error' }
  }
  if (isDirty.value) {
    return { icon: '●', label: 'Есть несохранённые изменения', tone: 'dirty' }
  }
  if (props.saveState === 'success') {
    return { icon: '✓', label: 'Сохранено', tone: 'saved' }
  }

  return { icon: '✓', label: 'Варианты не изменены', tone: 'idle' }
})

function cloneDraft(draft: PlanOptionDraft): PlanOptionDraft {
  return {
    startsAt: draft.startsAt,
    place: draft.place,
    comment: draft.comment,
  }
}

function createRow(draft?: PlanOptionDraft): EditorRow {
  nextKey += 1

  return {
    key: nextKey,
    startsAt: draft?.startsAt ?? '',
    place: draft?.place ?? '',
    comment: draft?.comment ?? '',
  }
}

function fingerprintOptions(options: InvitationPlanOption[]): string {
  return JSON.stringify(sortPlanOptions(options).map(option => ({
    startsAt: option.starts_at,
    place: option.place,
    comment: option.comment,
    position: option.position,
  })))
}

function syncRows(options: InvitationPlanOption[]): void {
  const nextDrafts = sortPlanOptions(options).map(planOptionToDraft)

  while (nextDrafts.length < MIN_PLAN_OPTIONS) {
    nextDrafts.push({ startsAt: '', place: '', comment: '' })
  }

  const limitedDrafts = nextDrafts.slice(0, MAX_PLAN_OPTIONS)

  rows.value = limitedDrafts.map(createRow)
  baselineDrafts.value = limitedDrafts.map(cloneDraft)
  optionErrors.value = rows.value.map(() => ({}))
  formError.value = ''
}

function addOption(): void {
  if (!canAdd.value || isSaving.value) {
    return
  }

  rows.value.push(createRow())
  optionErrors.value.push({})
  formError.value = ''
  emit('edited')
}

function removeOption(index: number): void {
  if (!canRemove.value || isSaving.value) {
    return
  }

  rows.value.splice(index, 1)
  optionErrors.value.splice(index, 1)
  formError.value = ''
  emit('edited')
}

function moveOption(index: number, direction: -1 | 1): void {
  const targetIndex = index + direction

  if (
    isSaving.value
    || targetIndex < 0
    || targetIndex >= rows.value.length
  ) {
    return
  }

  const [row] = rows.value.splice(index, 1)
  const [errors] = optionErrors.value.splice(index, 1)

  if (!row) {
    return
  }

  rows.value.splice(targetIndex, 0, row)
  optionErrors.value.splice(targetIndex, 0, errors ?? {})
  formError.value = ''
  emit('edited')
}

function clearOptionError(index: number, field: keyof PlanOptionDraft): void {
  formError.value = ''
  emit('edited')
  const errors = optionErrors.value[index]

  if (errors?.[field]) {
    errors[field] = undefined
  }
}

function focusStatus(): void {
  void nextTick(() => statusRef.value?.focus())
}

function preparePayload(): PlanOptionsPayload | null {
  const validation = validatePlanOptionDrafts(drafts.value, props.currentTime)

  optionErrors.value = validation.optionErrors
  formError.value = validation.formError ?? ''

  if (!validation.valid) {
    if (!formError.value) {
      formError.value = 'Проверь заполнение каждого варианта.'
    }
    focusStatus()
    return null
  }

  const payload = planDraftsToPayload(drafts.value)

  if (!payload) {
    formError.value = 'Не удалось распознать дату и время. Проверь варианты.'
    focusStatus()
    return null
  }

  formError.value = ''
  return payload
}

function applyServerErrors(
  nextFormError: string | null,
  nextOptionErrors: PlanOptionDraftErrors[],
): void {
  optionErrors.value = rows.value.map((_, index) => ({
    ...(nextOptionErrors[index] ?? {}),
  }))
  formError.value = nextFormError ?? (
    nextOptionErrors.some(errors => Object.keys(errors).length > 0)
      ? 'Проверь поля, отмеченные сервером.'
      : ''
  )
  focusStatus()
}

function submitOptions(): void {
  if (!canSubmit.value) {
    return
  }

  const payload = preparePayload()

  if (payload) {
    emit('save', payload)
  }
}

watch(
  () => props.options,
  (options: InvitationPlanOption[]) => {
    const nextFingerprint = fingerprintOptions(options)

    if (nextFingerprint === persistedFingerprint) {
      return
    }

    persistedFingerprint = nextFingerprint
    syncRows(options)
  },
  { deep: true, immediate: true },
)

watch(
  drafts,
  (currentDrafts: PlanOptionDraft[]) => {
    emit('draftsChange', currentDrafts.map(cloneDraft))
  },
  { deep: true, immediate: true },
)

watch(
  isDirty,
  value => emit('dirtyChange', value),
  { immediate: true },
)

watch(
  () => props.saveState,
  (state) => {
    if (state === 'error' || state === 'success') {
      focusStatus()
    }
  },
)

defineExpose({
  applyServerErrors,
  preparePayload,
})
</script>

<template>
  <section
    class="plan-editor"
    :class="`plan-editor--${variant}`"
    aria-labelledby="plan-editor-title"
  >
    <header class="plan-editor__heading">
      <div>
        <p>{{ copy.eyebrow }}</p>
        <h2 id="plan-editor-title">{{ copy.title }}</h2>
        <span>{{ copy.description }}</span>
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

    <div class="plan-editor__timezone" role="note">
      <span aria-hidden="true">🌍</span>
      <p>
        Дата и время вводятся в часовом поясе <strong>{{ localTimeZone }}</strong>.
        Сервер сохранит точный момент с явным смещением времени.
      </p>
    </div>

    <form
      class="plan-editor__form"
      novalidate
      :aria-busy="isSaving"
      @submit.prevent="submitOptions"
    >
      <fieldset
        v-for="(row, index) in rows"
        :key="row.key"
        class="plan-option-editor"
        :disabled="isSaving"
      >
        <legend>
          <span>Вариант {{ index + 1 }}</span>
          <span class="plan-option-editor__actions">
            <button
              type="button"
              :disabled="index === 0 || isSaving"
              :aria-label="`Переместить вариант ${index + 1} выше`"
              @click="moveOption(index, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              :disabled="index === rows.length - 1 || isSaving"
              :aria-label="`Переместить вариант ${index + 1} ниже`"
              @click="moveOption(index, 1)"
            >
              ↓
            </button>
            <button
              v-if="canRemove"
              type="button"
              :disabled="isSaving"
              :aria-label="`Удалить вариант ${index + 1}`"
              @click="removeOption(index)"
            >
              Удалить
            </button>
          </span>
        </legend>

        <div class="plan-option-editor__grid">
          <div class="form-field">
            <label :for="`plan-start-${row.key}`">Дата и время</label>
            <input
              :id="`plan-start-${row.key}`"
              v-model="row.startsAt"
              type="datetime-local"
              required
              :min="minimumDateTime"
              :aria-invalid="Boolean(optionErrors[index]?.startsAt)"
              :aria-describedby="optionErrors[index]?.startsAt
                ? `plan-start-error-${row.key}`
                : `plan-start-hint-${row.key}`"
              @input="clearOptionError(index, 'startsAt')"
            >
            <span :id="`plan-start-hint-${row.key}`" class="form-field__hint">
              {{ localTimeZone }}
            </span>
            <span
              v-if="optionErrors[index]?.startsAt"
              :id="`plan-start-error-${row.key}`"
              class="form-field__error"
            >
              {{ optionErrors[index]?.startsAt }}
            </span>
          </div>

          <div class="form-field">
            <label :for="`plan-place-${row.key}`">Место</label>
            <input
              :id="`plan-place-${row.key}`"
              v-model="row.place"
              type="text"
              required
              :maxlength="PLAN_OPTION_PLACE_MAX_LENGTH"
              placeholder="Кафе, парк или адрес"
              :aria-invalid="Boolean(optionErrors[index]?.place)"
              :aria-describedby="optionErrors[index]?.place
                ? `plan-place-error-${row.key}`
                : undefined"
              @input="clearOptionError(index, 'place')"
            >
            <span
              v-if="optionErrors[index]?.place"
              :id="`plan-place-error-${row.key}`"
              class="form-field__error"
            >
              {{ optionErrors[index]?.place }}
            </span>
          </div>
        </div>

        <div class="form-field">
          <div class="form-field__label-row">
            <label :for="`plan-comment-${row.key}`">Комментарий <span>(необязательно)</span></label>
            <span aria-hidden="true">
              {{ row.comment.length }}/{{ PLAN_OPTION_COMMENT_MAX_LENGTH }}
            </span>
          </div>
          <textarea
            :id="`plan-comment-${row.key}`"
            v-model="row.comment"
            rows="2"
            :maxlength="PLAN_OPTION_COMMENT_MAX_LENGTH"
            placeholder="Например: столик у окна уже забронирован"
            :aria-invalid="Boolean(optionErrors[index]?.comment)"
            :aria-describedby="optionErrors[index]?.comment
              ? `plan-comment-error-${row.key}`
              : undefined"
            @input="clearOptionError(index, 'comment')"
          />
          <span
            v-if="optionErrors[index]?.comment"
            :id="`plan-comment-error-${row.key}`"
            class="form-field__error"
          >
            {{ optionErrors[index]?.comment }}
          </span>
        </div>
      </fieldset>

      <button
        class="plan-editor__add"
        type="button"
        :disabled="!canAdd || isSaving"
        @click="addOption"
      >
        <span aria-hidden="true">＋</span>
        {{ canAdd ? 'Добавить вариант' : `Максимум ${MAX_PLAN_OPTIONS} вариантов` }}
      </button>

      <div
        v-if="formError || props.saveState === 'error' || props.saveState === 'success'"
        ref="statusRef"
        class="plan-editor__status"
        :class="!formError && props.saveState === 'success'
          ? 'plan-editor__status--success'
          : 'plan-editor__status--error'"
        :role="!formError && props.saveState === 'success' ? 'status' : 'alert'"
        tabindex="-1"
      >
        <template v-if="!formError && props.saveState === 'success'">
          {{ copy.success }}
        </template>
        <template v-else>
          {{ formError || props.saveError }}
        </template>
      </div>

      <button
        class="plan-editor__submit"
        type="submit"
        :disabled="!canSubmit"
      >
        <span aria-hidden="true">{{ isSaving ? '⏳' : '✓' }}</span>
        {{ isSaving ? 'Сохраняем варианты…' : copy.submit }}
      </button>
    </form>
  </section>
</template>
