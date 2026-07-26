import {
  ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH,
  ACTIVITY_OPTION_IMAGE_KEYS,
  ACTIVITY_OPTION_PLACE_MAX_LENGTH,
  ACTIVITY_OPTION_TITLE_MAX_LENGTH,
  MAX_ACTIVITY_OPTIONS,
  MIN_ACTIVITY_OPTIONS,
  type ActivityOptionImageKey,
  type ActivityOptionPayload,
  type ActivityOptionRecord,
  type ActivityOptionsPayload,
} from '../types/activity'
import { parseInvitationApiError, type InvitationApiError } from './invitations'

export type ActivityOptionDraft = {
  title: string
  description: string
  imageKey: ActivityOptionImageKey
  place: string
}

export type ActivityOptionDraftErrors = Partial<Record<keyof ActivityOptionDraft, string>>

export type ActivityOptionsValidation = {
  formError: string | null
  optionErrors: ActivityOptionDraftErrors[]
  valid: boolean
}

export type ActivityOptionsApiError = InvitationApiError & {
  formError: string | null
  optionErrors: ActivityOptionDraftErrors[]
}

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasErrorMessage(value: unknown): boolean {
  if (typeof value === 'string') {
    return Boolean(value.trim())
  }

  if (Array.isArray(value)) {
    return value.some(hasErrorMessage)
  }

  if (isRecord(value)) {
    return Object.values(value).some(hasErrorMessage)
  }

  return false
}

function extractErrorData(error: unknown): UnknownRecord | null {
  if (!isRecord(error)) {
    return null
  }

  if (isRecord(error.data)) {
    return error.data
  }

  if (isRecord(error.response) && isRecord(error.response._data)) {
    return error.response._data
  }

  return null
}

export function isActivityOptionImageKey(value: unknown): value is ActivityOptionImageKey {
  return typeof value === 'string'
    && ACTIVITY_OPTION_IMAGE_KEYS.some(imageKey => imageKey === value)
}

export function getDefaultActivityOptionImageKey(index: number): ActivityOptionImageKey {
  const normalizedIndex = Math.max(0, Math.trunc(index))
  return ACTIVITY_OPTION_IMAGE_KEYS[normalizedIndex % ACTIVITY_OPTION_IMAGE_KEYS.length]!
}

export function normalizeActivityOption(value: unknown): ActivityOptionRecord {
  if (!isRecord(value)) {
    throw new Error('Сервер вернул некорректный вариант активности.')
  }

  const { id, title, description, image_key: imageKey, place, position } = value

  if (
    typeof id !== 'string'
    || typeof title !== 'string'
    || typeof description !== 'string'
    || typeof imageKey !== 'string'
    || typeof place !== 'string'
    || typeof position !== 'number'
    || !Number.isInteger(position)
    || position < 0
  ) {
    throw new Error('Сервер вернул неполные данные варианта активности.')
  }

  return {
    id,
    title,
    description,
    image_key: imageKey,
    place,
    position,
  }
}

export function sortActivityOptions(options: ActivityOptionRecord[]): ActivityOptionRecord[] {
  return [...options].sort((first, second) => (
    first.position - second.position || first.title.localeCompare(second.title)
  ))
}

export function normalizeActivityOptionsResponse(value: unknown): ActivityOptionRecord[] {
  if (!isRecord(value) || !Array.isArray(value.options)) {
    throw new Error('Сервер вернул некорректную коллекцию активностей.')
  }

  return sortActivityOptions(value.options.map(normalizeActivityOption))
}

export function activityOptionToDraft(option: ActivityOptionRecord): ActivityOptionDraft {
  return {
    title: option.title,
    description: option.description,
    imageKey: isActivityOptionImageKey(option.image_key)
      ? option.image_key
      : getDefaultActivityOptionImageKey(option.position),
    place: option.place,
  }
}

export function activityOptionDraftsHaveChanges(
  drafts: ActivityOptionDraft[],
  baseline: ActivityOptionDraft[],
): boolean {
  if (drafts.length !== baseline.length) {
    return true
  }

  return drafts.some((draft, index) => {
    const savedDraft = baseline[index]!

    return draft.title !== savedDraft.title
      || draft.description !== savedDraft.description
      || draft.imageKey !== savedDraft.imageKey
      || draft.place !== savedDraft.place
  })
}

export function activityStepRequiresOptionSave(
  isDirty: boolean,
  persistedOptionCount: number,
  requireCompleteStep: boolean,
): boolean {
  return isDirty || (
    requireCompleteStep
    && persistedOptionCount < MIN_ACTIVITY_OPTIONS
  )
}

export function validateActivityOptionDrafts(
  options: ActivityOptionDraft[],
): ActivityOptionsValidation {
  let formError: string | null = null

  if (options.length < MIN_ACTIVITY_OPTIONS) {
    formError = `Добавь минимум ${MIN_ACTIVITY_OPTIONS} активности.`
  }
  else if (options.length > MAX_ACTIVITY_OPTIONS) {
    formError = `Можно предложить не больше ${MAX_ACTIVITY_OPTIONS} активностей.`
  }

  const optionErrors = options.map((option): ActivityOptionDraftErrors => {
    const errors: ActivityOptionDraftErrors = {}
    const title = option.title.trim()
    const description = option.description.trim()
    const place = option.place.trim()

    if (!title) {
      errors.title = 'Укажи название активности.'
    }
    else if (title.length > ACTIVITY_OPTION_TITLE_MAX_LENGTH) {
      errors.title = `Не больше ${ACTIVITY_OPTION_TITLE_MAX_LENGTH} символов.`
    }

    if (description.length > ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH) {
      errors.description = `Не больше ${ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH} символов.`
    }

    if (place.length > ACTIVITY_OPTION_PLACE_MAX_LENGTH) {
      errors.place = `Не больше ${ACTIVITY_OPTION_PLACE_MAX_LENGTH} символов.`
    }

    if (!isActivityOptionImageKey(option.imageKey)) {
      errors.imageKey = 'Выбери изображение из встроенной библиотеки.'
    }

    return errors
  })
  const hasOptionErrors = optionErrors.some(errors => Object.keys(errors).length > 0)

  return {
    formError,
    optionErrors,
    valid: formError === null && !hasOptionErrors,
  }
}

export function activityDraftsToPayload(
  options: ActivityOptionDraft[],
): ActivityOptionsPayload {
  const payloadOptions: ActivityOptionPayload[] = options.map(option => ({
    title: option.title.trim(),
    description: option.description.trim(),
    image_key: option.imageKey,
    place: option.place.trim(),
  }))

  return { options: payloadOptions }
}

export function parseActivityOptionsApiError(error: unknown): ActivityOptionsApiError {
  const parsedError = parseInvitationApiError(error)
  const responseData = extractErrorData(error)
  const rawOptions = responseData?.options
  const optionErrors: ActivityOptionDraftErrors[] = []
  let formError: string | null = null

  if (Array.isArray(rawOptions)) {
    for (const item of rawOptions) {
      if (!isRecord(item)) {
        if (hasErrorMessage(item)) {
          formError = `Добавь от ${MIN_ACTIVITY_OPTIONS} до ${MAX_ACTIVITY_OPTIONS} активностей.`
        }
        continue
      }

      const itemErrors: ActivityOptionDraftErrors = {}

      if (hasErrorMessage(item.title)) {
        itemErrors.title = `Укажи название длиной до ${ACTIVITY_OPTION_TITLE_MAX_LENGTH} символов.`
      }
      if (hasErrorMessage(item.description)) {
        itemErrors.description = `Описание должно быть не длиннее ${ACTIVITY_OPTION_DESCRIPTION_MAX_LENGTH} символов.`
      }
      if (hasErrorMessage(item.image_key)) {
        itemErrors.imageKey = 'Выбери корректное локальное изображение.'
      }
      if (hasErrorMessage(item.place)) {
        itemErrors.place = `Место должно быть не длиннее ${ACTIVITY_OPTION_PLACE_MAX_LENGTH} символов.`
      }

      optionErrors.push(itemErrors)
    }
  }
  else if (hasErrorMessage(rawOptions)) {
    formError = `Добавь от ${MIN_ACTIVITY_OPTIONS} до ${MAX_ACTIVITY_OPTIONS} активностей.`
  }

  const hasFieldErrors = optionErrors.some(item => Object.keys(item).length > 0)

  if (!formError && parsedError.status === 400 && !hasFieldErrors) {
    formError = parsedError.message
  }

  if (parsedError.status === 409) {
    parsedError.message = 'Активности уже нельзя изменить. Обнови страницу и проверь состояние приглашения.'
  }
  else if (parsedError.status === 400) {
    parsedError.message = 'Проверь названия, изображения и дополнительные поля активностей.'
  }

  return {
    ...parsedError,
    formError,
    optionErrors,
  }
}
