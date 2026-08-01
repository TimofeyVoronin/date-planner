const INVITATION_NAME_DIGIT_PATTERN = /\p{Number}/u
const INVITATION_NAME_DIGITS_PATTERN = /\p{Number}+/gu

type NameBeforeInputEvent = Pick<
  InputEvent,
  'cancelable' | 'data' | 'isComposing' | 'preventDefault'
>

type NameInputTarget = EventTarget & {
  value: string
}

function isNameInputTarget(target: EventTarget | null): target is NameInputTarget {
  if (target === null) {
    return false
  }

  return typeof (target as EventTarget & { value?: unknown }).value === 'string'
}

export function hasInvitationNameDigits(value: string): boolean {
  return INVITATION_NAME_DIGIT_PATTERN.test(value)
}

export function sanitizeInvitationName(value: string): string {
  return value.replace(INVITATION_NAME_DIGITS_PATTERN, '')
}

export function preventInvitationNameDigitInput(event: NameBeforeInputEvent): void {
  if (
    event.cancelable
    && !event.isComposing
    && event.data
    && hasInvitationNameDigits(event.data)
  ) {
    event.preventDefault()
  }
}

export function sanitizeInvitationNameInput(
  event: Event,
  updateModel: (value: string) => void,
): void {
  const inputEvent = event as Event & { isComposing?: boolean }
  if (inputEvent.isComposing || !isNameInputTarget(event.currentTarget)) {
    return
  }

  const currentValue = event.currentTarget.value
  const sanitizedValue = sanitizeInvitationName(currentValue)
  if (sanitizedValue !== currentValue) {
    event.currentTarget.value = sanitizedValue
    updateModel(sanitizedValue)
  }
}
