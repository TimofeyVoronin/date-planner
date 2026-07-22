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
  planOptionToDraft,
  sortPlanOptions,
  validatePlanOptionDrafts,
  type PlanOptionDraft,
  type PlanOptionDraftErrors,
} from '../../utils/planning'

type SaveState = 'error' | 'idle' | 'saving' | 'success'
type EditorRow = PlanOptionDraft & { key: number }

type Props = {
  currentTime: Date
  options: InvitationPlanOption[]
  saveError?: string
  saveState?: SaveState
}

const props = withDefaults(defineProps<Props>(), {
  saveError: '',
  saveState: 'idle',
})
const emit = defineEmits<{
  dirty: []
  save: [payload: PlanOptionsPayload]
}>()

const rows = ref<EditorRow[]>([])
const optionErrors = ref<PlanOptionDraftErrors[]>([])
const formError = ref('')
const statusRef = ref<HTMLElement | null>(null)
const minimumDateTime = computed(() => getMinimumPlanDateTime(props.currentTime))
let nextKey = 0

const canAdd = computed(() => rows.value.length < MAX_PLAN_OPTIONS)
const canRemove = computed(() => rows.value.length > MIN_PLAN_OPTIONS)

function createRow(draft?: PlanOptionDraft): EditorRow {
  nextKey += 1

  return {
    key: nextKey,
    startsAt: draft?.startsAt ?? '',
    place: draft?.place ?? '',
    comment: draft?.comment ?? '',
  }
}

function syncRows(options: InvitationPlanOption[]): void {
  const nextRows = sortPlanOptions(options).map(option => createRow(planOptionToDraft(option)))

  while (nextRows.length < MIN_PLAN_OPTIONS) {
    nextRows.push(createRow())
  }

  rows.value = nextRows.slice(0, MAX_PLAN_OPTIONS)
  optionErrors.value = rows.value.map(() => ({}))
  formError.value = ''
}

function addOption(): void {
  if (!canAdd.value) {
    return
  }

  rows.value.push(createRow())
  optionErrors.value.push({})
  formError.value = ''
  emit('dirty')
}

function removeOption(index: number): void {
  if (!canRemove.value) {
    return
  }

  rows.value.splice(index, 1)
  optionErrors.value.splice(index, 1)
  formError.value = ''
  emit('dirty')
}

function clearOptionError(index: number, field: keyof PlanOptionDraft): void {
  emit('dirty')
  formError.value = ''
  const errors = optionErrors.value[index]

  if (errors?.[field]) {
    errors[field] = undefined
  }
}

function focusStatus(): void {
  void nextTick(() => statusRef.value?.focus())
}

function submitOptions(): void {
  if (props.saveState === 'saving') {
    return
  }

  const drafts = rows.value.map(({ startsAt, place, comment }) => ({
    startsAt,
    place,
    comment,
  }))
  const validation = validatePlanOptionDrafts(drafts, props.currentTime)

  optionErrors.value = validation.optionErrors
  formError.value = validation.formError ?? ''

  if (!validation.valid) {
    if (!formError.value) {
      formError.value = 'Проверь заполнение каждого варианта.'
    }
    focusStatus()
    return
  }

  const payload = planDraftsToPayload(drafts)

  if (!payload) {
    formError.value = 'Не удалось распознать дату и время. Проверь варианты.'
    focusStatus()
    return
  }

  formError.value = ''
  emit('save', payload)
}

watch(
  () => props.options,
  syncRows,
  { deep: true, immediate: true },
)

watch(
  () => props.saveState,
  (state) => {
    if (state === 'error' || state === 'success') {
      focusStatus()
    }
  },
)
</script>

<template>
  <section class="plan-editor" aria-labelledby="plan-editor-title">
    <header class="plan-section-heading">
      <p>Следующий шаг</p>
      <h2 id="plan-editor-title">Предложи варианты свидания</h2>
      <span>
        Добавь от {{ MIN_PLAN_OPTIONS }} до {{ MAX_PLAN_OPTIONS }} вариантов.
        Получатель выберет один на своей странице.
      </span>
    </header>

    <form class="plan-editor__form" novalidate @submit.prevent="submitOptions">
      <fieldset
        v-for="(row, index) in rows"
        :key="row.key"
        class="plan-option-editor"
      >
        <legend>
          <span>Вариант {{ index + 1 }}</span>
          <button
            v-if="canRemove"
            type="button"
            :aria-label="`Удалить вариант ${index + 1}`"
            @click="removeOption(index)"
          >
            Удалить
          </button>
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
              В твоём часовом поясе
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
        :disabled="!canAdd"
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
          Варианты сохранены — получатель сможет выбрать один по публичной ссылке.
        </template>
        <template v-else>
          {{ formError || props.saveError }}
        </template>
      </div>

      <button
        class="plan-editor__submit"
        type="submit"
        :disabled="props.saveState === 'saving'"
      >
        <span aria-hidden="true">{{ props.saveState === 'saving' ? '⏳' : '✓' }}</span>
        {{ props.saveState === 'saving' ? 'Сохраняем варианты…' : 'Сохранить варианты' }}
      </button>
    </form>
  </section>
</template>
