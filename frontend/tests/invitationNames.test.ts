import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import {
  hasInvitationNameDigits,
  preventInvitationNameDigitInput,
  sanitizeInvitationName,
  sanitizeInvitationNameInput,
} from '../utils/invitationNames'

type FakeNameInputTarget = EventTarget & {
  value: string
}

function nameInputEvent(
  value: string,
  isComposing = false,
): {
  event: Event
  target: FakeNameInputTarget
} {
  const target = { value } as FakeNameInputTarget
  const event = {
    currentTarget: target,
    isComposing,
  } as unknown as Event

  return { event, target }
}

describe('invitation name input helpers', () => {
  it.each([
    'Алиса2',
    'علي٢',
    'Женя２',
    'Алиса²',
    'Женя①',
    'МарияⅣ',
  ])('recognizes Unicode number characters in %s', (value) => {
    expect(hasInvitationNameDigits(value)).toBe(true)
  })

  it.each([
    'Анна-Мария',
    'O\'Connor',
    'D’Angelo',
    'Марʼяна',
    '李 小龍',
    '李四',
    'علي',
  ])('preserves an international name without digits: %s', (value) => {
    expect(hasInvitationNameDigits(value)).toBe(false)
    expect(sanitizeInvitationName(value)).toBe(value)
  })

  it('removes decimal, superscript, circled, and numeral number characters', () => {
    expect(sanitizeInvitationName('Анна2 علي٣ Женя４²①Ⅳ')).toBe('Анна علي Женя')
  })

  it('prevents a cancelable non-composing digit insertion before it reaches the input', () => {
    const preventDefault = vi.fn()

    preventInvitationNameDigitInput({
      cancelable: true,
      data: '٢',
      isComposing: false,
      preventDefault,
    })

    expect(preventDefault).toHaveBeenCalledOnce()
  })

  it.each([
    {
      cancelable: false,
      data: '2',
      isComposing: false,
    },
    {
      cancelable: true,
      data: 'Анна',
      isComposing: false,
    },
    {
      cancelable: true,
      data: '２',
      isComposing: true,
    },
    {
      cancelable: true,
      data: null,
      isComposing: false,
    },
  ])('does not cancel input for $data when cancellation is inappropriate', (event) => {
    const preventDefault = vi.fn()

    preventInvitationNameDigitInput({
      ...event,
      preventDefault,
    })

    expect(preventDefault).not.toHaveBeenCalled()
  })

  it('repairs both the DOM value and model when beforeinput could not block the change', () => {
    const { event, target } = nameInputEvent('O\'Connor2 علي٣ Женя４')
    const updateModel = vi.fn()

    sanitizeInvitationNameInput(event, updateModel)

    expect(target.value).toBe('O\'Connor علي Женя')
    expect(updateModel).toHaveBeenCalledOnce()
    expect(updateModel).toHaveBeenCalledWith('O\'Connor علي Женя')
  })

  it('does not modify the DOM or model during an active IME composition', () => {
    const { event, target } = nameInputEvent('李２', true)
    const updateModel = vi.fn()

    sanitizeInvitationNameInput(event, updateModel)

    expect(target.value).toBe('李２')
    expect(updateModel).not.toHaveBeenCalled()
  })

  it('leaves an already valid DOM value alone so the browser preserves the caret', () => {
    const { event, target } = nameInputEvent('Анна-Мария')
    const updateModel = vi.fn()

    sanitizeInvitationNameInput(event, updateModel)

    expect(target.value).toBe('Анна-Мария')
    expect(updateModel).not.toHaveBeenCalled()
  })

  it('ignores input events without a text input target', () => {
    const updateModel = vi.fn()
    const event = {
      currentTarget: null,
      isComposing: false,
    } as unknown as Event

    sanitizeInvitationNameInput(event, updateModel)

    expect(updateModel).not.toHaveBeenCalled()
  })
})

describe('invitation name field integration', () => {
  it.each([
    '../components/invitation/InvitationCreateForm.vue',
    '../components/invitation/InvitationDetailsEditor.vue',
    '../components/builder/BuilderInvitationStep.vue',
  ])('guards both name fields in %s', (componentPath) => {
    const source = readFileSync(new URL(componentPath, import.meta.url), 'utf8')

    expect(
      source.match(/@beforeinput="preventInvitationNameDigitInput"/g),
    ).toHaveLength(2)
    expect(
      source.match(/@input="handle(?:Author|Recipient)NameInput"/g),
    ).toHaveLength(2)
  })
})
