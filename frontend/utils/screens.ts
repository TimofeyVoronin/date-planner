import {
  INVITATION_SCREEN_TYPES,
  type InvitationScreenRecord,
  type InvitationScreenType,
} from '../types/screen'
import type { BuilderStepNumber } from './builder'
import { isInvitationImageCompatible, isInvitationImageKey } from './invitationImages'

export type InvitationScreenPresentation = {
  icon: string
  label: string
  description: string
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
    description: 'Первый вопрос и основная кнопка ответа.',
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

export function normalizeInvitationScreens(payload: unknown): InvitationScreenRecord[] {
  if (!Array.isArray(payload)) {
    throw new Error('Сервер вернул некорректный набор экранов приглашения.')
  }

  const screens = payload.map((item) => {
    if (!isRecord(item) || !isInvitationScreenType(item.screen_type)) {
      throw new Error('Сервер вернул неизвестный тип экрана приглашения.')
    }

    const imageKey = readStringField(item, 'image_key')
    if (!isInvitationImageKey(imageKey)) {
      throw new Error('Сервер вернул неизвестное изображение экрана приглашения.')
    }
    if (!isInvitationImageCompatible(imageKey, item.screen_type)) {
      throw new Error('Изображение не подходит для указанного экрана приглашения.')
    }

    return {
      screen_type: item.screen_type,
      title: readStringField(item, 'title'),
      subtitle: readStringField(item, 'subtitle'),
      button_text: readStringField(item, 'button_text'),
      image_key: imageKey,
    }
  })

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
