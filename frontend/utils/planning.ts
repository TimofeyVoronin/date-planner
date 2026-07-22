import {
  MAX_PLAN_OPTIONS,
  MIN_PLAN_OPTIONS,
  PLAN_OPTION_COMMENT_MAX_LENGTH,
  PLAN_OPTION_PLACE_MAX_LENGTH,
  type InvitationPlanOption,
  type PlanOptionPayload,
  type PlanOptionsPayload,
} from '../types/invitation'
import { parseInvitationApiError, type InvitationApiError } from './invitations'

export type PlanOptionDraft = {
  comment: string
  place: string
  startsAt: string
}

export type PlanOptionDraftErrors = Partial<Record<keyof PlanOptionDraft, string>>

export type PlanOptionsValidation = {
  formError: string | null
  optionErrors: PlanOptionDraftErrors[]
  valid: boolean
}

function padDatePart(value: number): string {
  return String(value).padStart(2, '0')
}

export function localDateTimeToIso(value: string): string | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value)

  if (!parts) {
    return null
  }

  const year = Number(parts[1])
  const month = Number(parts[2])
  const day = Number(parts[3])
  const hours = Number(parts[4])
  const minutes = Number(parts[5])
  const seconds = Number(parts[6] ?? 0)
  const date = new Date(year, month - 1, day, hours, minutes, seconds)

  if (
    Number.isNaN(date.getTime())
    || date.getFullYear() !== year
    || date.getMonth() !== month - 1
    || date.getDate() !== day
    || date.getHours() !== hours
    || date.getMinutes() !== minutes
    || date.getSeconds() !== seconds
  ) {
    return null
  }

  return date.toISOString()
}

export function isoToLocalDateTime(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return [
    date.getFullYear(),
    '-',
    padDatePart(date.getMonth() + 1),
    '-',
    padDatePart(date.getDate()),
    'T',
    padDatePart(date.getHours()),
    ':',
    padDatePart(date.getMinutes()),
  ].join('')
}

export function getMinimumPlanDateTime(now: Date = new Date()): string {
  const nextMinute = new Date(now.getTime() + 60_000)
  nextMinute.setSeconds(0, 0)

  return isoToLocalDateTime(nextMinute.toISOString())
}

export function planOptionToDraft(option: InvitationPlanOption): PlanOptionDraft {
  return {
    startsAt: isoToLocalDateTime(option.starts_at),
    place: option.place,
    comment: option.comment,
  }
}

export function validatePlanOptionDrafts(
  options: PlanOptionDraft[],
  now: Date = new Date(),
): PlanOptionsValidation {
  let formError: string | null = null

  if (options.length < MIN_PLAN_OPTIONS) {
    formError = `Добавь минимум ${MIN_PLAN_OPTIONS} варианта.`
  }
  else if (options.length > MAX_PLAN_OPTIONS) {
    formError = `Можно предложить не больше ${MAX_PLAN_OPTIONS} вариантов.`
  }

  const optionErrors = options.map((option): PlanOptionDraftErrors => {
    const errors: PlanOptionDraftErrors = {}
    const startsAt = localDateTimeToIso(option.startsAt)

    if (!option.startsAt.trim() || !startsAt) {
      errors.startsAt = 'Выбери корректные дату и время.'
    }
    else if (new Date(startsAt).getTime() <= now.getTime()) {
      errors.startsAt = 'Дата и время должны быть в будущем.'
    }

    const place = option.place.trim()

    if (!place) {
      errors.place = 'Укажи место.'
    }
    else if (place.length > PLAN_OPTION_PLACE_MAX_LENGTH) {
      errors.place = `Не больше ${PLAN_OPTION_PLACE_MAX_LENGTH} символов.`
    }

    if (option.comment.trim().length > PLAN_OPTION_COMMENT_MAX_LENGTH) {
      errors.comment = `Не больше ${PLAN_OPTION_COMMENT_MAX_LENGTH} символов.`
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

export function planDraftsToPayload(options: PlanOptionDraft[]): PlanOptionsPayload | null {
  const payloadOptions: PlanOptionPayload[] = []

  for (const option of options) {
    const startsAt = localDateTimeToIso(option.startsAt)

    if (!startsAt) {
      return null
    }

    payloadOptions.push({
      starts_at: startsAt,
      place: option.place.trim(),
      comment: option.comment.trim(),
    })
  }

  return { options: payloadOptions }
}

export function sortPlanOptions(options: InvitationPlanOption[]): InvitationPlanOption[] {
  return [...options].sort((first, second) => (
    first.position - second.position || first.starts_at.localeCompare(second.starts_at)
  ))
}

export function findSelectedPlanOption(
  options: InvitationPlanOption[],
  selectedOptionId: string | null,
): InvitationPlanOption | null {
  if (!selectedOptionId) {
    return null
  }

  return options.find(option => option.id === selectedOptionId) ?? null
}

export function formatPlanOptionDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Дата не указана'
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(date)
}

export function parsePlanningApiError(
  error: unknown,
  action: 'options' | 'selection',
): InvitationApiError {
  const parsedError = parseInvitationApiError(error)

  if (parsedError.status === 400) {
    return {
      ...parsedError,
      message: action === 'options'
        ? 'Проверь даты, места и комментарии во всех вариантах.'
        : 'Этот вариант больше недоступен. Обнови страницу и выбери снова.',
    }
  }

  if (parsedError.status === 409) {
    return {
      ...parsedError,
      message: action === 'options'
        ? 'Варианты уже нельзя изменить: обнови страницу, чтобы увидеть сделанный выбор.'
        : 'Сейчас сохранить выбор нельзя. Обнови страницу и попробуй снова.',
    }
  }

  return parsedError
}
