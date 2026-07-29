import type { BuilderPreviewDemoOption } from '../types/builder-preview'

export const FINAL_TEMPLATE_MAX_LENGTH = 1000
export const FINAL_TEMPLATE_VARIABLES = [
  'author',
  'recipient',
  'date',
  'time',
  'place',
  'activity',
] as const

export const DEFAULT_FINAL_TEXT_TEMPLATE = '{recipient}, жду тебя {date} в {time}. Встречаемся в {place}, а дальше нас ждёт {activity} 💘'

export type FinalTemplateVariable = typeof FINAL_TEMPLATE_VARIABLES[number]
export type FinalTemplateContext = Record<FinalTemplateVariable, string>

type FinalTemplateToken =
  | { kind: 'literal', value: string }
  | { kind: 'variable', value: FinalTemplateVariable }

export class FinalTemplateValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FinalTemplateValidationError'
  }
}

function isFinalTemplateVariable(value: string): value is FinalTemplateVariable {
  return FINAL_TEMPLATE_VARIABLES.some(variable => variable === value)
}

export function parseFinalTextTemplate(template: string): FinalTemplateToken[] {
  const tokens: FinalTemplateToken[] = []
  let literal = ''
  let index = 0

  function flushLiteral(): void {
    if (!literal) {
      return
    }

    tokens.push({ kind: 'literal', value: literal })
    literal = ''
  }

  while (index < template.length) {
    const character = template[index]!

    if (character === '{') {
      if (template[index + 1] === '{') {
        literal += '{'
        index += 2
        continue
      }

      const closingIndex = template.indexOf('}', index + 1)
      if (closingIndex === -1) {
        throw new FinalTemplateValidationError('Закрой фигурную скобку в шаблоне.')
      }

      const variable = template.slice(index + 1, closingIndex)
      if (!variable) {
        throw new FinalTemplateValidationError('Пустая переменная в шаблоне недопустима.')
      }
      if (variable.includes('{')) {
        throw new FinalTemplateValidationError('Вложенные фигурные скобки недопустимы.')
      }
      if (!isFinalTemplateVariable(variable)) {
        throw new FinalTemplateValidationError(`Переменная {${variable}} не поддерживается.`)
      }

      flushLiteral()
      tokens.push({ kind: 'variable', value: variable })
      index = closingIndex + 1
      continue
    }

    if (character === '}') {
      if (template[index + 1] === '}') {
        literal += '}'
        index += 2
        continue
      }

      throw new FinalTemplateValidationError('Открывающая фигурная скобка отсутствует.')
    }

    literal += character
    index += 1
  }

  flushLiteral()
  return tokens
}

export function normalizeFinalTextTemplate(template: string): string {
  const normalized = template.trim()

  if (!normalized) {
    throw new FinalTemplateValidationError('Финальный текст не может быть пустым.')
  }
  if (Array.from(normalized).length > FINAL_TEMPLATE_MAX_LENGTH) {
    throw new FinalTemplateValidationError(
      `Финальный текст не может быть длиннее ${FINAL_TEMPLATE_MAX_LENGTH} символов.`,
    )
  }

  parseFinalTextTemplate(normalized)
  return normalized
}

export function renderFinalTextTemplate(
  template: string,
  context: FinalTemplateContext,
): string {
  return parseFinalTextTemplate(normalizeFinalTextTemplate(template))
    .map(token => token.kind === 'variable' ? context[token.value] : token.value)
    .join('')
}

export function renderFinalTextTemplateSafely(
  template: string,
  context: FinalTemplateContext,
): string {
  try {
    return renderFinalTextTemplate(template, context)
  }
  catch {
    return renderFinalTextTemplate(DEFAULT_FINAL_TEXT_TEMPLATE, context)
  }
}

export function buildFinalTemplateContext(input: {
  activityTitle?: string | null
  authorName: string
  place: string
  recipientName: string
  startsAt: string
}): FinalTemplateContext {
  const startsAt = new Date(input.startsAt)
  const hasValidDate = !Number.isNaN(startsAt.getTime())

  return {
    author: input.authorName.trim() || 'Автор приглашения',
    recipient: input.recipientName.trim() || 'Получатель приглашения',
    date: hasValidDate
      ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long' }).format(startsAt)
      : 'в выбранный день',
    time: hasValidDate
      ? new Intl.DateTimeFormat('ru-RU', { timeStyle: 'short' }).format(startsAt)
      : 'в выбранное время',
    place: input.place.trim() || 'в выбранном месте',
    activity: input.activityTitle?.trim() || 'приятное свидание',
  }
}

export function buildPreviewFinalTemplateContext(input: {
  activity: BuilderPreviewDemoOption
  authorName: string
  date: BuilderPreviewDemoOption
  recipientName: string
}): FinalTemplateContext {
  const [datePart = 'в выбранный день', timePart = 'в выбранное время'] = input.date.label
    .split('·', 2)
    .map(part => part.trim())
  const [place = input.date.description] = input.date.description.split('—', 1)

  return {
    author: input.authorName.trim() || 'Автор приглашения',
    recipient: input.recipientName.trim() || 'Получатель приглашения',
    date: datePart,
    time: timePart,
    place: place.trim() || 'в выбранном месте',
    activity: input.activity.label.trim() || 'приятное свидание',
  }
}
