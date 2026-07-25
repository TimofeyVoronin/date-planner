import {
  INVITATION_IMAGE_KEYS,
  type InvitationImageKey,
  type InvitationImageRecord,
} from '../types/invitation-image'
import type { InvitationScreenType } from '../types/screen'

export const INVITATION_IMAGE_LIBRARY = [
  {
    key: 'invitation-default',
    label: 'Письмо с сердцем',
    description: 'Нежное письмо и парящие сердца для первого вопроса.',
    altText: 'Розовый конверт с большим сердцем и маленькими сердцами вокруг',
    assetPath: '/images/invitation-library/invitation-default.svg',
    screenType: 'invitation',
  },
  {
    key: 'invitation-starlight',
    label: 'Звёздное признание',
    description: 'Тёмное небо, сияющее сердце и мягкие звёзды.',
    altText: 'Сияющее сердце на фоне ночного неба со звёздами',
    assetPath: '/images/invitation-library/invitation-starlight.svg',
    screenType: 'invitation',
  },
  {
    key: 'invitation-flowers',
    label: 'Цветочное письмо',
    description: 'Конверт в окружении светлых романтических цветов.',
    altText: 'Светлый конверт с сердцем среди розовых и кремовых цветов',
    assetPath: '/images/invitation-library/invitation-flowers.svg',
    screenType: 'invitation',
  },
  {
    key: 'invitation-moon',
    label: 'Под луной',
    description: 'Спокойная ночная композиция с луной и двумя сердцами.',
    altText: 'Полумесяц над двумя сердцами на тёмно-фиолетовом фоне',
    assetPath: '/images/invitation-library/invitation-moon.svg',
    screenType: 'invitation',
  },
  {
    key: 'acceptance-default',
    label: 'Ура, получилось!',
    description: 'Большое сердце, конфетти и праздничные искры.',
    altText: 'Большое розовое сердце среди конфетти и сияющих искр',
    assetPath: '/images/invitation-library/acceptance-default.svg',
    screenType: 'acceptance',
  },
  {
    key: 'acceptance-balloons',
    label: 'Воздушные сердца',
    description: 'Лёгкие шарики-сердца для радостного перехода дальше.',
    altText: 'Несколько воздушных шариков в форме сердец на светлом фоне',
    assetPath: '/images/invitation-library/acceptance-balloons.svg',
    screenType: 'acceptance',
  },
  {
    key: 'acceptance-fireworks',
    label: 'Праздничный вечер',
    description: 'Салют и сердечко для яркого подтверждения ответа.',
    altText: 'Розовое сердце и праздничный салют на вечернем небе',
    assetPath: '/images/invitation-library/acceptance-fireworks.svg',
    screenType: 'acceptance',
  },
  {
    key: 'acceptance-together',
    label: 'Теперь вместе',
    description: 'Два персонажа рядом и общее сердце между ними.',
    altText: 'Два стилизованных человека рядом с сердцем между ними',
    assetPath: '/images/invitation-library/acceptance-together.svg',
    screenType: 'acceptance',
  },
  {
    key: 'date-selection-default',
    label: 'Особенная дата',
    description: 'Календарь с отмеченным сердцем днём.',
    altText: 'Календарь с розовым сердцем на выбранной дате',
    assetPath: '/images/invitation-library/date-selection-default.svg',
    screenType: 'date_selection',
  },
  {
    key: 'date-sunset',
    label: 'Вечер на закате',
    description: 'Тёплый закат и часы для вечерней встречи.',
    altText: 'Закат над горизонтом и круглые часы с отмеченным временем',
    assetPath: '/images/invitation-library/date-sunset.svg',
    screenType: 'date_selection',
  },
  {
    key: 'date-weekend',
    label: 'Планы на выходные',
    description: 'Лист календаря, звёздочка и маленькое сердце.',
    altText: 'Лист календаря выходного дня со звездой и сердцем',
    assetPath: '/images/invitation-library/date-weekend.svg',
    screenType: 'date_selection',
  },
  {
    key: 'activity-selection-default',
    label: 'Выбери впечатление',
    description: 'Три карточки идей со звёздочками и сердцем.',
    altText: 'Три карточки вариантов активности со звёздами и сердцем',
    assetPath: '/images/invitation-library/activity-selection-default.svg',
    screenType: 'activity_selection',
  },
  {
    key: 'activity-coffee',
    label: 'Кофе вдвоём',
    description: 'Две чашки и общее сердце для спокойного свидания.',
    altText: 'Две чашки кофе рядом и маленькое сердце над ними',
    assetPath: '/images/invitation-library/activity-coffee.svg',
    screenType: 'activity_selection',
  },
  {
    key: 'activity-movie',
    label: 'Вечер в кино',
    description: 'Кинобилеты, попкорн и мягкое вечернее настроение.',
    altText: 'Два кинобилета и коробка попкорна с сердцем',
    assetPath: '/images/invitation-library/activity-movie.svg',
    screenType: 'activity_selection',
  },
  {
    key: 'final-default',
    label: 'План готов',
    description: 'Карточка итогового плана с галочкой и сердцем.',
    altText: 'Карточка готового плана свидания с галочкой и сердцем',
    assetPath: '/images/invitation-library/final-default.svg',
    screenType: 'final',
  },
  {
    key: 'final-toast',
    label: 'За нашу встречу',
    description: 'Два бокала и маленькие искры для праздничного финала.',
    altText: 'Два соприкасающихся бокала с сердцем и искрами',
    assetPath: '/images/invitation-library/final-toast.svg',
    screenType: 'final',
  },
  {
    key: 'final-night',
    label: 'Вечер впереди',
    description: 'Ночной город, луна и маршрут к общему сердцу.',
    altText: 'Ночной город с луной и дорожкой к светящемуся сердцу',
    assetPath: '/images/invitation-library/final-night.svg',
    screenType: 'final',
  },
  {
    key: 'final-route',
    label: 'Маршрут построен',
    description: 'Две точки встречи, соединённые романтическим маршрутом.',
    altText: 'Две отметки на карте, соединённые линией с сердцем посередине',
    assetPath: '/images/invitation-library/final-route.svg',
    screenType: 'final',
  },
] as const satisfies readonly InvitationImageRecord[]

const IMAGE_BY_KEY = new Map<InvitationImageKey, InvitationImageRecord>(
  INVITATION_IMAGE_LIBRARY.map(image => [image.key, image]),
)

export function isInvitationImageKey(value: unknown): value is InvitationImageKey {
  return typeof value === 'string' && INVITATION_IMAGE_KEYS.some(key => key === value)
}

export function getInvitationImageByKey(
  imageKey: string,
): InvitationImageRecord | undefined {
  return isInvitationImageKey(imageKey) ? IMAGE_BY_KEY.get(imageKey) : undefined
}

export function getInvitationImagesForScreenType(
  screenType: InvitationScreenType,
): InvitationImageRecord[] {
  return INVITATION_IMAGE_LIBRARY.filter(image => image.screenType === screenType)
}

export function getInvitationImagesForScreens(
  screenTypes: readonly InvitationScreenType[],
): InvitationImageRecord[] {
  const allowedTypes = new Set(screenTypes)

  return INVITATION_IMAGE_LIBRARY.filter(image => allowedTypes.has(image.screenType))
}

export function isInvitationImageCompatible(
  imageKey: string,
  screenType: InvitationScreenType,
): boolean {
  return getInvitationImageByKey(imageKey)?.screenType === screenType
}

export function resolveInvitationImageUrl(
  assetPath: string,
  appBaseUrl = '/',
): string {
  const normalizedBaseUrl = appBaseUrl.endsWith('/') ? appBaseUrl : `${appBaseUrl}/`
  const normalizedAssetPath = assetPath.replace(/^\/+/, '')

  return `${normalizedBaseUrl}${normalizedAssetPath}`
}
