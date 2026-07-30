import type { BuilderStepNumber } from './builder'
import type { ActivityOptionDraft } from './activities'
import type { PlanOptionDraft } from './planning'
import {
  BUILDER_PREVIEW_DEVICE_IDS,
  BUILDER_PREVIEW_SCREENS,
  type BuilderPreviewDemoOption,
  type BuilderPreviewDevice,
  type BuilderPreviewDeviceId,
  type BuilderPreviewNoButtonTransform,
  type BuilderPreviewScreen,
  type BuilderPreviewScreenDefinition,
} from '../types/builder-preview'

export const BUILDER_PREVIEW_SCREEN_DEFINITIONS: readonly BuilderPreviewScreenDefinition[] = [
  {
    screen: 'invitation',
    builderStep: 1,
    icon: '💌',
    label: 'Приглашение',
  },
  {
    screen: 'acceptance',
    builderStep: 1,
    icon: '💘',
    label: 'Ответ «Да»',
  },
  {
    screen: 'date_selection',
    builderStep: 2,
    icon: '🗓️',
    label: 'Дата',
  },
  {
    screen: 'activity_selection',
    builderStep: 3,
    icon: '✨',
    label: 'Активность',
  },
  {
    screen: 'final',
    builderStep: 4,
    icon: '💞',
    label: 'Финал',
  },
]

export const BUILDER_PREVIEW_DEVICES: readonly BuilderPreviewDevice[] = [
  { id: 'compact', label: 'Компактный', width: 320 },
  { id: 'regular', label: 'Обычный', width: 375 },
  { id: 'large', label: 'Большой', width: 430 },
]

type BuilderPreviewDateDefinition = {
  description: string
  hours: number
  id: string
  minutes: number
  weekday: number
}

const BUILDER_PREVIEW_DATE_DEFINITIONS: readonly BuilderPreviewDateDefinition[] = [
  {
    id: 'date-friday',
    weekday: 5,
    hours: 19,
    minutes: 0,
    description: 'Кофейня у парка',
  },
  {
    id: 'date-saturday',
    weekday: 6,
    hours: 17,
    minutes: 30,
    description: 'Встречаемся у набережной',
  },
  {
    id: 'date-tuesday',
    weekday: 2,
    hours: 20,
    minutes: 0,
    description: 'Вечерняя прогулка по центру',
  },
]

const BUILDER_PREVIEW_DATE_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  weekday: 'long',
})

function getNextPreviewDate(
  referenceTime: Date,
  definition: BuilderPreviewDateDefinition,
): Date {
  const candidate = new Date(referenceTime)
  candidate.setHours(definition.hours, definition.minutes, 0, 0)

  let daysUntilTarget = (definition.weekday - candidate.getDay() + 7) % 7
  if (daysUntilTarget === 0 && candidate.getTime() <= referenceTime.getTime()) {
    daysUntilTarget = 7
  }

  candidate.setDate(candidate.getDate() + daysUntilTarget)

  return candidate
}

function capitalizePreviewDateLabel(value: string): string {
  return value.charAt(0).toLocaleUpperCase('ru-RU') + value.slice(1)
}

export function buildBuilderPreviewDemoDateOptions(
  referenceTime: Date,
): BuilderPreviewDemoOption[] {
  return BUILDER_PREVIEW_DATE_DEFINITIONS
    .map((definition) => {
      const startsAt = getNextPreviewDate(referenceTime, definition)
      const dateLabel = capitalizePreviewDateLabel(
        BUILDER_PREVIEW_DATE_FORMATTER.format(startsAt),
      )
      const timeLabel = `${String(definition.hours).padStart(2, '0')}:${String(definition.minutes).padStart(2, '0')}`

      return {
        startsAt,
        option: {
          id: definition.id,
          label: `${dateLabel} · ${timeLabel}`,
          description: definition.description,
        },
      }
    })
    .sort((left, right) => left.startsAt.getTime() - right.startsAt.getTime())
    .map(item => item.option)
}

export const BUILDER_PREVIEW_ACTIVITIES: readonly BuilderPreviewDemoOption[] = [
  {
    id: 'activity-walk',
    label: 'Прогулка и десерт',
    description: 'Неспешная прогулка, а затем любимое кафе',
    imageKey: 'activity-selection-default',
  },
  {
    id: 'activity-movie',
    label: 'Кино и обсуждение',
    description: 'Выбираем фильм и продолжаем вечер за кофе',
    imageKey: 'activity-movie',
  },
  {
    id: 'activity-surprise',
    label: 'Маленький сюрприз',
    description: 'План узнает только получатель приглашения',
    imageKey: 'activity-coffee',
  },
]

export function buildBuilderPreviewDateOptions(
  drafts: PlanOptionDraft[],
): BuilderPreviewDemoOption[] {
  return drafts.map((draft, index) => {
    const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(draft.startsAt)
    const label = parts
      ? `${parts[3]}.${parts[2]}.${parts[1]} · ${parts[4]}:${parts[5]}`
      : 'Дата и время пока не указаны'
    const place = draft.place.trim() || 'Место пока не указано'
    const comment = draft.comment.trim()

    return {
      id: `draft-date-${index + 1}`,
      label,
      description: comment ? `${place} — ${comment}` : place,
    }
  })
}

export function buildBuilderPreviewActivityOptions(
  drafts: ActivityOptionDraft[],
): BuilderPreviewDemoOption[] {
  return drafts.map((draft, index) => {
    const title = draft.title.trim() || 'Название активности пока не указано'
    const place = draft.place.trim()
    const description = draft.description.trim()
    const details = [place, description].filter(Boolean).join(' — ')

    return {
      id: `draft-activity-${index + 1}`,
      label: title,
      description: details || 'Описание пока не указано',
      imageKey: draft.imageKey,
    }
  })
}

const STEP_SCREEN_MAP: Readonly<Record<BuilderStepNumber, BuilderPreviewScreen>> = {
  1: 'invitation',
  2: 'date_selection',
  3: 'activity_selection',
  4: 'final',
}

const PREVIEW_NO_BUTTON_TRANSFORMS: readonly BuilderPreviewNoButtonTransform[] = [
  { x: 0, y: 0, scale: 1 },
  { x: 42, y: -12, scale: .92 },
  { x: -46, y: 18, scale: .84 },
  { x: 34, y: 30, scale: .76 },
  { x: -36, y: -26, scale: .68 },
]

export function isBuilderPreviewScreen(value: unknown): value is BuilderPreviewScreen {
  return BUILDER_PREVIEW_SCREENS.some(screen => screen === value)
}

export function isBuilderPreviewDeviceId(value: unknown): value is BuilderPreviewDeviceId {
  return BUILDER_PREVIEW_DEVICE_IDS.some(device => device === value)
}

export function getBuilderPreviewScreenForStep(
  step: BuilderStepNumber,
): BuilderPreviewScreen {
  return STEP_SCREEN_MAP[step]
}

export function getBuilderPreviewScreenDefinition(
  screen: BuilderPreviewScreen,
): BuilderPreviewScreenDefinition {
  return BUILDER_PREVIEW_SCREEN_DEFINITIONS.find(item => item.screen === screen)!
}

export function getBuilderPreviewDevice(
  deviceId: BuilderPreviewDeviceId,
): BuilderPreviewDevice {
  return BUILDER_PREVIEW_DEVICES.find(device => device.id === deviceId)!
}

export function getNextBuilderPreviewScreen(
  screen: BuilderPreviewScreen,
): BuilderPreviewScreen | null {
  const index = BUILDER_PREVIEW_SCREENS.indexOf(screen)
  return BUILDER_PREVIEW_SCREENS[index + 1] ?? null
}

export function getPreviousBuilderPreviewScreen(
  screen: BuilderPreviewScreen,
): BuilderPreviewScreen | null {
  const index = BUILDER_PREVIEW_SCREENS.indexOf(screen)
  return BUILDER_PREVIEW_SCREENS[index - 1] ?? null
}

export function getBuilderPreviewNoButtonTransform(
  attempts: number,
): BuilderPreviewNoButtonTransform {
  const normalizedAttempts = Math.max(
    0,
    Math.min(Math.trunc(attempts), PREVIEW_NO_BUTTON_TRANSFORMS.length - 1),
  )

  return PREVIEW_NO_BUTTON_TRANSFORMS[normalizedAttempts]!
}
