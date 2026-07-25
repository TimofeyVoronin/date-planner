import {
  INVITATION_SCREEN_BUTTON_MAX_LENGTH,
  INVITATION_SCREEN_SUBTITLE_MAX_LENGTH,
  INVITATION_SCREEN_TITLE_MAX_LENGTH,
  INVITATION_SCREEN_TYPES,
  type InvitationScreenEditForm,
  type InvitationScreenEditableField,
  type InvitationScreenRecord,
  type InvitationScreenType,
  type InvitationScreenUpdatePayload,
  type InvitationScreenValidationErrors,
} from '../types/screen'
import type { BuilderStepNumber } from './builder'
import { isInvitationImageCompatible, isInvitationImageKey } from './invitationImages'

export type InvitationScreenPresentation = {
  icon: string
  label: string
  description: string
}

export type InvitationScreenApiError = {
  fieldErrors: InvitationScreenValidationErrors
  message: string
  status: number | null
}

type UnknownRecord = Record<string, unknown>

const SCREEN_STEP_MAP: Record<BuilderStepNumber, readonly InvitationScreenType[]> = {
  1: ['invitation', 'acceptance'],
  2: ['date_selection'],
  3: ['activity_selection'],
  4: ['final'],
}

const SCREEN_PRESENTATIONS: Record<InvitationScreenType, InvitationScreenPresentation> = {
  invitation: {
    icon: '💌',
    label: 'Экран приглашения',
    description: 'Первый вопрос и основные кнопки ответа.',
  },
  acceptance: {
    icon: '💘',
    label: 'Экран после согласия',
    description: 'Переход от ответа «Да» к совместному планированию.',
  },
  date_selection: {
    icon: '📅',
    label: 'Экран выбора даты',
    description: 'Предложенные автором варианты даты и времени.',
  },
  activity_selection: {
    icon: '✨',
    label: 'Экран выбора активности',
    description: 'Карточки занятий, из которых получатель выберет одно.',
  },
  final: {
    icon: '💞',
    label: 'Финальный экран',
    description: 'Итоговый текст и подтверждённый план свидания.',
  },
}

const EDITABLE_SCREEN_FIELDS: InvitationScreenEditableField[] = [
  'title',
  'subtitle',
  'button_text',
  'secondary_button_text',
  'image_key',
]

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readStringField(record: UnknownRecord, field: keyof InvitationScreenRecord): string {
  const value = record[field]

  if (typeof value !== 'string') {
    throw new Error(`Некорректное поле конфигурации экрана: ${field}.`)
  }

  return value
}

function extractStatus(error: unknown): number | null {
  if (!isRecord(error)) {
    return null
  }

  if (typeof error.statusCode === 'number') {
    return error.statusCode
  }
  if (typeof error.status === 'number') {
    return error.status
  }
  if (isRecord(error.response) && typeof error.response.status === 'number') {
    return error.response.status
  }

  return null
}

function extractResponseData(error: unknown): UnknownRecord | null {
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

function firstErrorMessage(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value.trim()
  }
  if (Array.isArray(value)) {
    const first = value.find(item => typeof item === 'string' && item.trim())
    return typeof first === 'string' ? first.trim() : null
  }

  return null
}

export function isInvitationScreenType(value: unknown): value is InvitationScreenType {
  return INVITATION_SCREEN_TYPES.some(screenType => screenType === value)
}

export function sortInvitationScreens(
  screens: readonly InvitationScreenRecord[],
): InvitationScreenRecord[] {
  const order = new Map(
    INVITATION_SCREEN_TYPES.map((screenType, index) => [screenType, index]),
  )

  return [...screens].sort(
    (left, right) => order.get(left.screen_type)! - order.get(right.screen_type)!,
  )
}

export function normalizeInvitationScreen(payload: unknown): InvitationScreenRecord {
  if (!isRecord(payload) || !isInvitationScreenType(payload.screen_type)) {
    throw new Error('Сервер вернул неизвестный тип экрана приглашения.')
  }

  const imageKey = readStringField(payload, 'image_key')
  if (!isInvitationImageKey(imageKey)) {
    throw new Error('Сервер вернул неизвестное изображение экрана приглашения.')
  }
  if (!isInvitationImageCompatible(imageKey, payload.screen_type)) {
    throw new Error('Изображение не подходит для указанного экрана приглашения.')
  }

  return {
    screen_type: payload.screen_type,
    title: readStringField(payload, 'title'),
    subtitle: readStringField(payload, 'subtitle'),
    button_text: readStringField(payload, 'button_text'),
    secondary_button_text: readStringField(payload, 'secondary_button_text'),
    image_key: imageKey,
  }
}

export function normalizeInvitationScreens(payload: unknown): InvitationScreenRecord[] {
  if (!Array.isArray(payload)) {
    throw new Error('Сервер вернул некорректный набор экранов приглашения.')
  }

  const screens = payload.map(normalizeInvitationScreen)

  const screenTypes = screens.map(screen => screen.screen_type)
  if (new Set(screenTypes).size !== screenTypes.length) {
    throw new Error('В конфигурации приглашения обнаружены повторяющиеся экраны.')
  }

  const missingTypes = INVITATION_SCREEN_TYPES.filter(
    screenType => !screenTypes.includes(screenType),
  )
  if (missingTypes.length > 0 || screens.length !== INVITATION_SCREEN_TYPES.length) {
    throw new Error('В конфигурации приглашения отсутствуют обязательные экраны.')
  }

  return sortInvitationScreens(screens)
}

export function getInvitationScreenPresentation(
  screenType: InvitationScreenType,
): InvitationScreenPresentation {
  return SCREEN_PRESENTATIONS[screenType]
}

export function getInvitationScreensForBuilderStep(
  screens: readonly InvitationScreenRecord[],
  step: BuilderStepNumber,
): InvitationScreenRecord[] {
  const allowedTypes = SCREEN_STEP_MAP[step]
  return screens.filter(screen => allowedTypes.includes(screen.screen_type))
}

export function getInvitationScreenByType(
  screens: readonly InvitationScreenRecord[],
  screenType: InvitationScreenType,
): InvitationScreenRecord | null {
  return screens.find(screen => screen.screen_type === screenType) ?? null
}

export function createInvitationScreenEditForm(
  screen: InvitationScreenRecord,
): InvitationScreenEditForm {
  return {
    title: screen.title,
    subtitle: screen.subtitle,
    button_text: screen.button_text,
    secondary_button_text: screen.secondary_button_text,
    image_key: screen.image_key,
  }
}

export function normalizeInvitationScreenEditForm(
  form: InvitationScreenEditForm,
): InvitationScreenEditForm {
  return {
    title: form.title.trim(),
    subtitle: form.subtitle.trim(),
    button_text: form.button_text.trim(),
    secondary_button_text: form.secondary_button_text.trim(),
    image_key: form.image_key,
  }
}

export function validateInvitationScreenEditForm(
  form: InvitationScreenEditForm,
  screenType: InvitationScreenType = 'invitation',
): InvitationScreenValidationErrors {
  const normalized = normalizeInvitationScreenEditForm(form)
  const errors: InvitationScreenValidationErrors = {}

  if (!normalized.title) {
    errors.title = screenType === 'acceptance'
      ? 'Напиши заголовок экрана после согласия.'
      : 'Напиши главный вопрос приглашения.'
  }
  else if (normalized.title.length > INVITATION_SCREEN_TITLE_MAX_LENGTH) {
    errors.title = `Не больше ${INVITATION_SCREEN_TITLE_MAX_LENGTH} символов.`
  }

  if (normalized.subtitle.length > INVITATION_SCREEN_SUBTITLE_MAX_LENGTH) {
    errors.subtitle = `Не больше ${INVITATION_SCREEN_SUBTITLE_MAX_LENGTH} символов.`
  }

  if (!normalized.button_text) {
    errors.button_text = screenType === 'acceptance'
      ? 'Напиши текст кнопки продолжения.'
      : 'Напиши текст кнопки согласия.'
  }
  else if (normalized.button_text.length > INVITATION_SCREEN_BUTTON_MAX_LENGTH) {
    errors.button_text = `Не больше ${INVITATION_SCREEN_BUTTON_MAX_LENGTH} символов.`
  }

  if (screenType === 'invitation') {
    if (!normalized.secondary_button_text) {
      errors.secondary_button_text = 'Напиши текст кнопки отказа.'
    }
    else if (
      normalized.secondary_button_text.length > INVITATION_SCREEN_BUTTON_MAX_LENGTH
    ) {
      errors.secondary_button_text = `Не больше ${INVITATION_SCREEN_BUTTON_MAX_LENGTH} символов.`
    }
  }

  if (!isInvitationImageCompatible(normalized.image_key, screenType)) {
    errors.image_key = screenType === 'acceptance'
      ? 'Выбери изображение для экрана после согласия.'
      : 'Выбери изображение для экрана приглашения.'
  }

  return errors
}

export function hasInvitationScreenValidationErrors(
  errors: InvitationScreenValidationErrors,
  screenType: InvitationScreenType = 'invitation',
): boolean {
  const fields = screenType === 'invitation'
    ? EDITABLE_SCREEN_FIELDS
    : EDITABLE_SCREEN_FIELDS.filter(field => field !== 'secondary_button_text')

  return fields.some(field => Boolean(errors[field]))
}

export function buildInvitationScreenUpdatePayload(
  form: InvitationScreenEditForm,
  screen: InvitationScreenRecord,
): InvitationScreenUpdatePayload {
  const normalized = normalizeInvitationScreenEditForm(form)
  const payload: InvitationScreenUpdatePayload = {}

  if (normalized.title !== screen.title) {
    payload.title = normalized.title
  }
  if (normalized.subtitle !== screen.subtitle) {
    payload.subtitle = normalized.subtitle
  }
  if (normalized.button_text !== screen.button_text) {
    payload.button_text = normalized.button_text
  }
  if (
    screen.screen_type === 'invitation'
    && normalized.secondary_button_text !== screen.secondary_button_text
  ) {
    payload.secondary_button_text = normalized.secondary_button_text
  }
  if (normalized.image_key !== screen.image_key) {
    payload.image_key = normalized.image_key
  }

  return payload
}

export function invitationScreenEditFormHasChanges(
  form: InvitationScreenEditForm,
  screen: InvitationScreenRecord,
): boolean {
  return Object.keys(buildInvitationScreenUpdatePayload(form, screen)).length > 0
}

export function parseInvitationScreenApiError(error: unknown): InvitationScreenApiError {
  const status = extractStatus(error)
  const data = extractResponseData(error)
  const fieldErrors: InvitationScreenValidationErrors = {}

  if (data) {
    for (const field of EDITABLE_SCREEN_FIELDS) {
      const message = firstErrorMessage(data[field])
      if (message) {
        fieldErrors[field] = message
      }
    }
  }

  const detail = data ? firstErrorMessage(data.detail) : null
  let message = detail ?? 'Не удалось сохранить экран приглашения.'

  if (status === 401 || status === 403) {
    message = 'Секретный доступ больше не действует. Открой полную ссылку автора заново.'
  }
  else if (status === 404) {
    message = 'Экран приглашения не найден.'
  }
  else if (status === 409) {
    message = detail ?? 'Этот экран уже нельзя редактировать.'
  }
  else if (status === 429) {
    message = 'Слишком много запросов. Подожди немного и повтори сохранение.'
  }
  else if (Object.keys(fieldErrors).length > 0) {
    message = 'Проверь заполненные поля экрана.'
  }

  return { fieldErrors, message, status }
}
