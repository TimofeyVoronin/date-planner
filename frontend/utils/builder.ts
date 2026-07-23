import type { InvitationRecord } from '../types/invitation'

export const BUILDER_STEP_NUMBERS = [1, 2, 3, 4] as const

export type BuilderStepNumber = typeof BUILDER_STEP_NUMBERS[number]
export type BuilderAccessBlock = 'published' | 'quick-mode'

export type BuilderStepDefinition = {
  description: string
  icon: string
  id: 'activities' | 'date-time' | 'final' | 'invitation'
  label: string
  number: BuilderStepNumber
  plannedFeatures: readonly string[]
}

const BUILDER_STEP_QUERY_VALUES: Readonly<Record<string, BuilderStepNumber>> = {
  '1': 1,
  '2': 2,
  '3': 3,
  '4': 4,
}

export const BUILDER_STEPS: readonly BuilderStepDefinition[] = [
  {
    number: 1,
    id: 'invitation',
    icon: '💌',
    label: 'Приглашение',
    description: 'Настрой первый экран, личный текст и поведение ответа.',
    plannedFeatures: [
      'Заголовок и личное сообщение',
      'Изображение и оформление',
      'Тексты кнопок «Да» и «Нет»',
    ],
  },
  {
    number: 2,
    id: 'date-time',
    icon: '🗓️',
    label: 'Дата и время',
    description: 'Подготовь варианты, из которых получатель сможет выбрать удобный.',
    plannedFeatures: [
      'От двух до пяти вариантов',
      'Дата, время и место встречи',
      'Проверка будущего времени',
    ],
  },
  {
    number: 3,
    id: 'activities',
    icon: '🎨',
    label: 'Активности',
    description: 'Предложи несколько идей для совместного свидания.',
    plannedFeatures: [
      'Карточки активностей',
      'Изображение и краткое описание',
      'Выбор одного варианта получателем',
    ],
  },
  {
    number: 4,
    id: 'final',
    icon: '💞',
    label: 'Финал',
    description: 'Настрой итоговый экран, который завершит персональный сценарий.',
    plannedFeatures: [
      'Финальный заголовок и текст',
      'Подстановка выбранных данных',
      'Проверка всего сценария перед публикацией',
    ],
  },
]

export function isBuilderStepNumber(value: unknown): value is BuilderStepNumber {
  return BUILDER_STEP_NUMBERS.some(step => step === value)
}

export function parseBuilderStep(value: unknown): BuilderStepNumber | null {
  if (typeof value !== 'string') {
    return null
  }

  return BUILDER_STEP_QUERY_VALUES[value] ?? null
}

export function resolveBuilderStep(
  queryValue: unknown,
  storedValue: string | null,
): BuilderStepNumber {
  return parseBuilderStep(queryValue) ?? parseBuilderStep(storedValue) ?? 1
}

export function getBuilderStepDefinition(step: BuilderStepNumber): BuilderStepDefinition {
  return BUILDER_STEPS[step - 1]!
}

export function getPreviousBuilderStep(step: BuilderStepNumber): BuilderStepNumber | null {
  const previous = step - 1

  return isBuilderStepNumber(previous) ? previous : null
}

export function getNextBuilderStep(step: BuilderStepNumber): BuilderStepNumber | null {
  const next = step + 1

  return isBuilderStepNumber(next) ? next : null
}

export function builderStepSessionKey(id: string): string {
  return `date-planner:builder-step:${id}`
}

export function buildBuilderPath(id: string, step: BuilderStepNumber = 1): string {
  return `/manage/${encodeURIComponent(id)}/builder?step=${step}`
}

export function getBuilderAccessBlock(
  invitation: Pick<InvitationRecord, 'creation_mode' | 'publication_status'>,
): BuilderAccessBlock | null {
  if (invitation.creation_mode !== 'extended') {
    return 'quick-mode'
  }

  if (invitation.publication_status !== 'draft') {
    return 'published'
  }

  return null
}
