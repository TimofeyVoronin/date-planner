import {
  INVITATION_MESSAGE_MAX_LENGTH,
  INVITATION_NAME_MAX_LENGTH,
  type InvitationCreatePayload,
  type InvitationField,
  type InvitationValidationErrors,
} from '../types/invitation'

export type InvitationApiError = {
  fieldErrors: InvitationValidationErrors
  message: string
  status: number | null
}

type UnknownRecord = Record<string, unknown>

const INVITATION_FIELDS: InvitationField[] = ['author_name', 'recipient_name', 'message']

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
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
    const firstMessage = value.find(item => typeof item === 'string' && item.trim())

    return typeof firstMessage === 'string' ? firstMessage.trim() : null
  }

  return null
}

export function normalizeInvitationPayload(
  payload: InvitationCreatePayload,
): InvitationCreatePayload {
  return {
    author_name: payload.author_name.trim(),
    recipient_name: payload.recipient_name.trim(),
    message: payload.message.trim(),
  }
}

export function validateInvitationPayload(
  payload: InvitationCreatePayload,
): InvitationValidationErrors {
  const normalized = normalizeInvitationPayload(payload)
  const errors: InvitationValidationErrors = {}

  if (!normalized.author_name) {
    errors.author_name = 'Напиши, от кого приглашение.'
  }
  else if (normalized.author_name.length > INVITATION_NAME_MAX_LENGTH) {
    errors.author_name = `Не больше ${INVITATION_NAME_MAX_LENGTH} символов.`
  }

  if (!normalized.recipient_name) {
    errors.recipient_name = 'Напиши имя того, кого приглашаешь.'
  }
  else if (normalized.recipient_name.length > INVITATION_NAME_MAX_LENGTH) {
    errors.recipient_name = `Не больше ${INVITATION_NAME_MAX_LENGTH} символов.`
  }

  if (!normalized.message) {
    errors.message = 'Добавь несколько тёплых слов.'
  }
  else if (normalized.message.length > INVITATION_MESSAGE_MAX_LENGTH) {
    errors.message = `Не больше ${INVITATION_MESSAGE_MAX_LENGTH} символов.`
  }

  return errors
}

export function hasInvitationValidationErrors(errors: InvitationValidationErrors): boolean {
  return INVITATION_FIELDS.some(field => Boolean(errors[field]))
}

export function buildPublicInvitationUrl(origin: string, id: string): string {
  return `${origin.replace(/\/+$/, '')}/invite/${encodeURIComponent(id)}`
}

export function buildManagementInvitationUrl(
  origin: string,
  id: string,
  token: string,
): string {
  const baseUrl = `${origin.replace(/\/+$/, '')}/manage/${encodeURIComponent(id)}`

  return `${baseUrl}#token=${encodeURIComponent(token)}`
}

export function isManagementToken(value: string): boolean {
  return /^[A-Za-z0-9_-]{43}$/.test(value)
}

export function readManagementToken(hash: string): string | null {
  const normalizedHash = hash.startsWith('#') ? hash.slice(1) : hash
  const token = new URLSearchParams(normalizedHash).get('token')?.trim()

  return token && isManagementToken(token) ? token : null
}

export function managementTokenSessionKey(id: string): string {
  return `date-planner:management-token:${id}`
}

export function isInvitationId(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

export function parseInvitationApiError(error: unknown): InvitationApiError {
  const status = extractStatus(error)
  const responseData = extractResponseData(error)
  const fieldErrors: InvitationValidationErrors = {}

  for (const field of INVITATION_FIELDS) {
    const message = firstErrorMessage(responseData?.[field])

    if (message) {
      fieldErrors[field] = message
    }
  }

  if (status === 429) {
    return {
      status,
      fieldErrors,
      message: 'Слишком много запросов. Подожди минуту и попробуй снова.',
    }
  }

  if (status === 404) {
    return {
      status,
      fieldErrors,
      message: 'Приглашение не найдено или ссылка больше не действует.',
    }
  }

  if (status === 401 || status === 403) {
    return {
      status,
      fieldErrors,
      message: 'Секретная ссылка не подходит для этого приглашения.',
    }
  }

  if (status === 400) {
    return {
      status,
      fieldErrors,
      message: hasInvitationValidationErrors(fieldErrors)
        ? 'Проверь заполненные поля.'
        : firstErrorMessage(responseData?.detail) ?? 'Не удалось проверить данные приглашения.',
    }
  }

  return {
    status,
    fieldErrors,
    message: 'Не удалось связаться с сервисом. Проверь соединение и попробуй снова.',
  }
}
