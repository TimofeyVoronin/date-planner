import { describe, expect, it, vi } from 'vitest'
import type { InvitationCreatePayload } from '../types/invitation'
import {
  buildManagementInvitationUrl,
  buildPublicInvitationUrl,
  hasInvitationValidationErrors,
  getInvitationCreationModePresentation,
  getInvitationPublicationPresentation,
  getInvitationResponsePresentation,
  isInvitationCreationMode,
  isInvitationPublicationStatus,
  isInvitationId,
  isFinalInvitationResponseStatus,
  isInvitationResponseStatus,
  isManagementToken,
  invitationStatusToAnswer,
  managementTokenSessionKey,
  normalizeInvitationPayload,
  parseInvitationApiError,
  parseInvitationResponseApiError,
  readManagementToken,
  refreshInvitationResponseAfterConflict,
  validateInvitationPayload,
} from '../utils/invitations'

const validPayload: InvitationCreatePayload = {
  author_name: 'Алиса',
  recipient_name: 'Борис',
  message: 'Давай сходим на свидание?',
  creation_mode: 'quick',
}

describe('invitation form helpers', () => {
  it('trims user input without mutating the original draft', () => {
    const draft = {
      author_name: '  Алиса ',
      recipient_name: ' Борис  ',
      message: '  Увидимся вечером?\n ',
      creation_mode: 'extended' as const,
    }

    expect(normalizeInvitationPayload(draft)).toEqual({
      author_name: 'Алиса',
      recipient_name: 'Борис',
      message: 'Увидимся вечером?',
      creation_mode: 'extended',
    })
    expect(draft.author_name).toBe('  Алиса ')
  })

  it('accepts a complete payload', () => {
    const errors = validateInvitationPayload(validPayload)

    expect(errors).toEqual({})
    expect(hasInvitationValidationErrors(errors)).toBe(false)
  })

  it('requires both names but accepts a blank personal message', () => {
    const errors = validateInvitationPayload({
      author_name: ' ',
      recipient_name: '\n',
      message: '   ',
      creation_mode: 'quick',
    })

    expect(errors.author_name).toBeTruthy()
    expect(errors.recipient_name).toBeTruthy()
    expect(errors.message).toBeUndefined()
    expect(hasInvitationValidationErrors(errors)).toBe(true)
  })

  it('enforces the same maximum lengths as the API', () => {
    const errors = validateInvitationPayload({
      author_name: 'A'.repeat(101),
      recipient_name: 'R'.repeat(101),
      message: 'M'.repeat(1001),
      creation_mode: 'quick',
    })

    expect(errors.author_name).toContain('100')
    expect(errors.recipient_name).toContain('100')
    expect(errors.message).toContain('1000')
  })

  it('accepts values exactly at the API limits', () => {
    expect(validateInvitationPayload({
      author_name: 'A'.repeat(100),
      recipient_name: 'R'.repeat(100),
      message: 'M'.repeat(1000),
      creation_mode: 'extended',
    })).toEqual({})
  })

  it('recognizes and presents both creation modes', () => {
    expect(isInvitationCreationMode('quick')).toBe(true)
    expect(isInvitationCreationMode('extended')).toBe(true)
    expect(isInvitationCreationMode('wizard')).toBe(false)
    expect(isInvitationCreationMode(null)).toBe(false)

    expect(getInvitationCreationModePresentation('quick')).toMatchObject({
      label: 'Быстрое приглашение',
      submitLabel: 'Создать приглашение',
    })
    expect(getInvitationCreationModePresentation('extended')).toMatchObject({
      label: 'Расширенное приглашение',
      submitLabel: 'Создать основу приглашения',
    })
  })

  it('reports a missing runtime creation mode before sending the payload', () => {
    const malformedPayload = {
      ...validPayload,
      creation_mode: 'wizard',
    } as unknown as InvitationCreatePayload

    const errors = validateInvitationPayload(malformedPayload)

    expect(errors.creation_mode).toContain('режим')
    expect(hasInvitationValidationErrors(errors)).toBe(true)
  })
})

describe('invitation links', () => {
  const id = 'd9428888-122b-11e1-b85c-61cd3cbb3210'
  const token = 'a'.repeat(43)

  it('builds public and fragment-only management URLs', () => {
    expect(buildPublicInvitationUrl('https://dates.example/', id)).toBe(
      `https://dates.example/invite/${id}`,
    )
    const managementUrl = buildManagementInvitationUrl('https://dates.example/', id, token)
    const parsedManagementUrl = new URL(managementUrl)

    expect(managementUrl).toBe(`https://dates.example/manage/${id}#token=${token}`)
    expect(parsedManagementUrl.search).toBe('')
    expect(parsedManagementUrl.pathname).not.toContain(token)
    expect(parsedManagementUrl.hash).toBe(`#token=${token}`)
  })

  it('extracts only a correctly shaped token from the fragment', () => {
    expect(readManagementToken(`#token=${token}`)).toBe(token)
    expect(readManagementToken(`token=${token}`)).toBe(token)
    expect(readManagementToken('#token=too-short')).toBeNull()
    expect(readManagementToken(`#other=value&token=${'!'.repeat(43)}`)).toBeNull()
    expect(isManagementToken(token)).toBe(true)
  })

  it('uses an invitation-specific session key', () => {
    expect(managementTokenSessionKey(id)).toBe(`date-planner:management-token:${id}`)
  })

  it('recognizes UUID invitation identifiers', () => {
    expect(isInvitationId(id)).toBe(true)
    expect(isInvitationId('D9428888-122B-11E1-B85C-61CD3CBB3210')).toBe(true)
    expect(isInvitationId('../invitations')).toBe(false)
  })
})

describe('API error presentation', () => {
  it('shows a dedicated message for rate limiting', () => {
    expect(parseInvitationApiError({ statusCode: 429 }).message).toContain('минуту')
  })

  it('maps backend validation errors to fields without any casts', () => {
    const parsed = parseInvitationApiError({
      response: {
        status: 400,
        _data: {
          creation_mode: ['Недопустимый режим создания.'],
          author_name: ['Это поле обязательно.'],
          message: ['Убедитесь, что это значение содержит не более 1000 символов.'],
        },
      },
    })

    expect(parsed.message).toBe('Проверь заполненные поля.')
    expect(parsed.fieldErrors).toEqual({
      creation_mode: 'Недопустимый режим создания.',
      author_name: 'Это поле обязательно.',
      message: 'Убедитесь, что это значение содержит не более 1000 символов.',
    })
  })

  it('distinguishes missing and unauthorized invitations', () => {
    expect(parseInvitationApiError({ status: 404 }).message).toContain('не найдено')
    expect(parseInvitationApiError({ statusCode: 401 }).message).toContain('Секретная ссылка')
    expect(parseInvitationApiError({ response: { status: 403 } }).message).toContain(
      'Секретная ссылка',
    )
  })
})

describe('invitation publication lifecycle', () => {
  it('recognizes only draft and published states', () => {
    expect(isInvitationPublicationStatus('draft')).toBe(true)
    expect(isInvitationPublicationStatus('published')).toBe(true)
    expect(isInvitationPublicationStatus('private')).toBe(false)
    expect(isInvitationPublicationStatus(null)).toBe(false)
  })

  it('explains whether the recipient can open the invitation', () => {
    expect(getInvitationPublicationPresentation('draft')).toMatchObject({
      label: 'Черновик',
      tone: 'draft',
    })
    expect(getInvitationPublicationPresentation('published')).toMatchObject({
      label: 'Опубликовано',
      tone: 'published',
    })
  })
})

describe('invitation response state', () => {
  it('recognizes only supported persisted statuses', () => {
    expect(isInvitationResponseStatus('pending')).toBe(true)
    expect(isInvitationResponseStatus('accepted')).toBe(true)
    expect(isInvitationResponseStatus('declined')).toBe(true)
    expect(isInvitationResponseStatus('yes')).toBe(false)
    expect(isInvitationResponseStatus(null)).toBe(false)
  })

  it('maps only final statuses to a card answer', () => {
    expect(invitationStatusToAnswer('pending')).toBeNull()
    expect(invitationStatusToAnswer('accepted')).toBe('accepted')
    expect(invitationStatusToAnswer('declined')).toBe('declined')
    expect(isFinalInvitationResponseStatus('pending')).toBe(false)
  })

  it.each([
    ['pending', 'Ожидаем ответ', 'pending'],
    ['accepted', 'Приглашение принято', 'accepted'],
    ['declined', 'Приглашение отклонено', 'declined'],
  ] as const)('presents %s status in Russian', (status, label, tone) => {
    expect(getInvitationResponsePresentation(status)).toMatchObject({ label, tone })
  })

  it('keeps the accepted copy valid throughout planning and after confirmation', () => {
    expect(getInvitationResponsePresentation('accepted').description).toContain('актуальный этап')
  })

  it('provides actionable save errors', () => {
    expect(parseInvitationResponseApiError({ status: 400 }).message).toContain('«Да» или «Нет»')
    expect(parseInvitationResponseApiError({ status: 409 }).message).toContain('Обнови страницу')
    expect(parseInvitationResponseApiError({ status: 429 }).message).toContain('минуту')
  })

  it('refetches the authoritative invitation after a response conflict', async () => {
    const loadLatest = vi.fn(async () => ({ confirmed_at: '2030-01-01T10:00:00Z' }))
    const parsedError = parseInvitationResponseApiError({ status: 409 })

    await expect(refreshInvitationResponseAfterConflict(parsedError, loadLatest)).resolves.toEqual({
      confirmed_at: '2030-01-01T10:00:00Z',
    })
    expect(loadLatest).toHaveBeenCalledOnce()
  })

  it('does not refetch the invitation after a retryable response validation error', async () => {
    const loadLatest = vi.fn(async () => ({ confirmed_at: null }))
    const parsedError = parseInvitationResponseApiError({ status: 400 })

    await expect(refreshInvitationResponseAfterConflict(parsedError, loadLatest)).resolves.toBeNull()
    expect(loadLatest).not.toHaveBeenCalled()
  })
})
