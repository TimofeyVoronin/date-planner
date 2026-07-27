<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH,
  ACTIVITY_OPTION_IMAGE_KEYS,
  ACTIVITY_OPTION_PLACE_MAX_LENGTH,
  ACTIVITY_OPTION_TITLE_MAX_LENGTH,
  MAX_ACTIVITY_OPTIONS,
  MIN_ACTIVITY_OPTIONS,
  type ActivityOptionImageKey,
  type ActivityOptionRecord,
  type ActivityOptionsPayload,
} from '../../types/activity'
import {
  activityDraftsToPayload,
  activityOptionDraftsHaveChanges,
  activityOptionToDraft,
  getDefaultActivityOptionImageKey,
  sortActivityOptions,
  validateActivityOptionDrafts,
  type ActivityOptionDraft,
  type ActivityOptionDraftErrors,
} from '../../utils/activities'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'

type ActivityOptionsSaveState = 'error' | 'idle' | 'saving' | 'success'
type EditorRow = ActivityOptionDraft & { key: number }

type Props = {
  options: ActivityOptionRecord[]
  saveError?: string
  saveState?: ActivityOptionsSaveState
}

const props = withDefaults(defineProps<Props>(), {
  saveError: '',
  saveState: 'idle',
})
const emit = defineEmits<{
  dirtyChange: [isDirty: boolean]
  draftsChange: [drafts: ActivityOptionDraft[]]
  edited: []
  save: [payload: ActivityOptionsPayload]
}>()

const config = useRuntimeConfig()
const images = ACTIVITY_OPTION_IMAGE_KEYS.map(key => {
  const image = getInvitationImageByKey(key)

  if (!image) {
    throw new Error(`Встроенное изображение активности ${key} не найдено.`)
  }

  return { ...image, key: key as ActivityOptionImageKey }
})
const rows = ref<EditorRow[]>([])
const baselineDrafts = ref<ActivityOptionDraft[]>([])
const optionErrors = ref<ActivityOptionDraftErrors[]>([])
const formError = ref('')
const statusRef = ref<HTMLElement | null>(null)
let nextKey = 0
let persistedFingerprint = ''

const drafts = computed<ActivityOptionDraft[]>(() => rows.value.map(row => ({
  title: row.title,
  description: row.description,
  imageKey: row.imageKey,
  place: row.place,
})))
const isDirty = computed(() => (
  activityOptionDraftsHaveChanges(drafts.value, baselineDrafts.value)
))
const canAdd = computed(() => rows.value.length < MAX_ACTIVITY_OPTIONS)
const canRemove = computed(() => rows.value.length > MIN_ACTIVITY_OPTIONS)
const isSaving = computed(() => props.saveState === 'saving')
const canSubmit = computed(() => isDirty.value && !isSaving.value)
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

  return { icon: '✓', label: 'Активности не изменены', tone: 'idle' }
})

function cloneDraft(draft: ActivityOptionDraft): ActivityOptionDraft {
  return {
    title: draft.title,
    description: draft.description,
    imageKey: draft.imageKey,
    place: draft.place,
  }
}

function createRow(draft?: ActivityOptionDraft): EditorRow {
  const index = nextKey
  nextKey += 1

  return {
    key: nextKey,
    title: draft?.title ?? '',
    description: draft?.description ?? '',
    imageKey: draft?.imageKey ?? getDefaultActivityOptionImageKey(index),
    place: draft?.place ?? '',
  }
}

function fingerprintOptions(options: ActivityOptionRecord[]): string {
  return JSON.stringify(sortActivityOptions(options).map(option => ({
    title: option.title,
    description: option.description,
    imageKey: option.image_key,
    place: option.place,
    position: option.position,
  })))
}

function syncRows(options: ActivityOptionRecord[]): void {
  const nextDrafts = sortActivityOptions(options).map(activityOptionToDraft)

  while (nextDrafts.length < MIN_ACTIVITY_OPTIONS) {
    nextDrafts.push({
      title: '',
      description: '',
      imageKey: getDefaultActivityOptionImageKey(nextDrafts.length),
      place: '',
    })
  }

  const limitedDrafts = nextDrafts.slice(0, MAX_ACTIVITY_OPTIONS)

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

function clearOptionError(index: number, field: keyof ActivityOptionDraft): void {
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

function preparePayload(): ActivityOptionsPayload | null {
  const validation = validateActivityOptionDrafts(drafts.value)

  optionErrors.value = validation.optionErrors
  formError.value = validation.formError ?? ''

  if (!validation.valid) {
    if (!formError.value) {
      formError.value = 'Проверь заполнение каждой активности.'
    }
    focusStatus()
    return null
  }

  formError.value = ''
  return activityDraftsToPayload(drafts.value)
}

function applyServerErrors(
  nextFormError: string | null,
  nextOptionErrors: ActivityOptionDraftErrors[],
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
  (options: ActivityOptionRecord[]) => {
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
  (currentDrafts: ActivityOptionDraft[]) => {
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
  <section class="activity-editor" aria-labelledby="activity-editor-title">
    <header class="activity-editor__heading">
      <div>
        <p>Варианты впечатлений</p>
        <h2 id="activity-editor-title">Добавь активности для свидания</h2>
        <span>
          Подготовь от {{ MIN_ACTIVITY_OPTIONS }} до {{ MAX_ACTIVITY_OPTIONS }} карточек.
          Порядок ниже станет порядком на публичной странице.
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

    <div class="activity-editor__note" role="note">
      <span aria-hidden="true">🖼️</span>
      <p>
        Используются только встроенные локальные изображения. Описание и место необязательны,
        но помогают получателю понять идею до выбора.
      </p>
    </div>

    <form
      class="activity-editor__form"
      novalidate
      :aria-busy="isSaving"
      @submit.prevent="submitOptions"
    >
      <fieldset
        v-for="(row, index) in rows"
        :key="row.key"
        class="activity-option-editor"
        :disabled="isSaving"
      >
        <legend>
          <span>Активность {{ index + 1 }}</span>
          <span class="activity-option-editor__actions">
            <button
              type="button"
              :disabled="index === 0 || isSaving"
              :aria-label="`Переместить активность ${index + 1} выше`"
              @click="moveOption(index, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              :disabled="index === rows.length - 1 || isSaving"
              :aria-label="`Переместить активность ${index + 1} ниже`"
              @click="moveOption(index, 1)"
            >
              ↓
            </button>
            <button
              type="button"
              :disabled="!canRemove || isSaving"
              :aria-label="`Удалить активность ${index + 1}`"
              @click="removeOption(index)"
            >
              Удалить
            </button>
          </span>
        </legend>

        <label class="form-field">
          <span>Название</span>
          <input
            v-model="row.title"
            type="text"
            :maxlength="ACTIVITY_OPTION_TITLE_MAX_LENGTH"
            :aria-invalid="Boolean(optionErrors[index]?.title)"
            :aria-describedby="optionErrors[index]?.title
              ? `activity-title-error-${row.key}`
              : undefined"
            placeholder="Например, вечер в кино"
            @input="clearOptionError(index, 'title')"
          >
          <small>{{ row.title.length }}/{{ ACTIVITY_OPTION_TITLE_MAX_LENGTH }}</small>
          <em
            v-if="optionErrors[index]?.title"
            :id="`activity-title-error-${row.key}`"
            class="form-field__error"
          >
            {{ optionErrors[index]?.title }}
          </em>
        </label>

        <fieldset class="activity-option-editor__images">
          <legend>Изображение</legend>
          <div>
            <label
              v-for="image in images"
              :key="image.key"
              :class="{
                'activity-option-editor__image--selected': row.imageKey === image.key,
              }"
            >
              <input
                v-model="row.imageKey"
                type="radio"
                :name="`activity-image-${row.key}`"
                :value="image.key"
                @change="clearOptionError(index, 'imageKey')"
              >
              <img
                :src="resolveInvitationImageUrl(image.assetPath, config.app.baseURL)"
                :alt="image.altText"
                width="160"
                height="105"
              >
              <strong>{{ image.label }}</strong>
            </label>
          </div>
          <em v-if="optionErrors[index]?.imageKey" class="form-field__error">
            {{ optionErrors[index]?.imageKey }}
          </em>
        </fieldset>

        <div class="activity-option-editor__grid">
          <label class="form-field">
            <span>Место <small>необязательно</small></span>
            <input
              v-model="row.place"
              type="text"
              :maxlength="ACTIVITY_OPTION_PLACE_MAX_LENGTH"
              :aria-invalid="Boolean(optionErrors[index]?.place)"
              :aria-describedby="optionErrors[index]?.place
                ? `activity-place-error-${row.key}`
                : undefined"
              placeholder="Например, кинотеатр в центре"
              @input="clearOptionError(index, 'place')"
            >
            <small>{{ row.place.length }}/{{ ACTIVITY_OPTION_PLACE_MAX_LENGTH }}</small>
            <em
              v-if="optionErrors[index]?.place"
              :id="`activity-place-error-${row.key}`"
              class="form-field__error"
            >
              {{ optionErrors[index]?.place }}
            </em>
          </label>

          <label class="form-field">
            <span>Описание <small>необязательно</small></span>
            <textarea
              v-model="row.description"
              rows="3"
              :maxlength="ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH"
              :aria-invalid="Boolean(optionErrors[index]?.description)"
              :aria-describedby="optionErrors[index]?.description
                ? `activity-description-error-${row.key}`
                : undefined"
              placeholder="Что вас ждёт и почему этот вариант стоит выбрать"
              @input="clearOptionError(index, 'description')"
            />
            <small>{{ row.description.length }}/{{ ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH }}</small>
            <em
              v-if="optionErrors[index]?.description"
              :id="`activity-description-error-${row.key}`"
              class="form-field__error"
            >
              {{ optionErrors[index]?.description }}
            </em>
          </label>
        </div>
      </fieldset>

      <button
        type="button"
        class="activity-editor__add"
        :disabled="!canAdd || isSaving"
        @click="addOption"
      >
        + Добавить активность
      </button>

      <p
        v-if="formError || saveError"
        ref="statusRef"
        class="activity-editor__status activity-editor__status--error"
        role="alert"
        tabindex="-1"
      >
        {{ formError || saveError }}
      </p>
      <p
        v-else-if="saveState === 'success'"
        ref="statusRef"
        class="activity-editor__status activity-editor__status--success"
        role="status"
        tabindex="-1"
      >
        Активности сохранены в черновике и готовы для следующего шага.
      </p>

      <button
        type="submit"
        class="activity-editor__submit"
        :disabled="!canSubmit"
      >
        {{ isSaving ? 'Сохраняем…' : 'Сохранить активности' }}
      </button>
    </form>
  </section>
</template>
