import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useBuilderAutosave } from '../composables/useBuilderAutosave'
import type {
  InvitationRecord,
  InvitationUpdatePayload,
} from '../types/invitation'

const invitationRecord: InvitationRecord = {
  id: 'd9428888-122b-11e1-b85c-61cd3cbb3210',
  author_name: 'Алиса',
  recipient_name: 'Борис',
  message: 'Давай сходим на свидание?',
  creation_mode: 'extended',
  publication_status: 'draft',
  published_at: null,
  response_status: 'pending',
  responded_at: null,
  plan_options: [],
  selected_option_id: null,
  selected_at: null,
  confirmed_at: null,
  server_now: '2030-01-01T10:00:00Z',
  created_at: '2030-01-01T10:00:00Z',
  updated_at: '2030-01-01T10:00:00Z',
}

function savedRecord(
  payload: InvitationUpdatePayload,
  updatedAt = '2030-01-01T10:01:00Z',
): InvitationRecord {
  return {
    ...invitationRecord,
    ...payload,
    updated_at: updatedAt,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })

  return { promise, reject, resolve }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('builder autosave', () => {
  it('debounces rapid edits and sends only the latest minimal PATCH', async () => {
    vi.useFakeTimers()
    const save = vi.fn(async (payload: InvitationUpdatePayload) => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ debounceMs: 800, save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = 'Анна'
    autosave.form.message = 'Пойдём в кино?'

    expect(autosave.status.value).toBe('dirty')
    expect(autosave.hasUnsavedChanges.value).toBe(true)

    await vi.advanceTimersByTimeAsync(799)
    expect(save).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)

    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith({
      author_name: 'Анна',
      message: 'Пойдём в кино?',
    })
    expect(autosave.status.value).toBe('saved')
    expect(autosave.hasUnsavedChanges.value).toBe(false)
    scope.stop()
  })

  it('does not save unchanged or whitespace-only values', async () => {
    const save = vi.fn(async (payload: InvitationUpdatePayload) => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = '  Алиса  '
    autosave.form.message = ' Давай сходим на свидание? '

    expect(autosave.isDirty.value).toBe(false)
    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).not.toHaveBeenCalled()
    scope.stop()
  })

  it('queues the newest edit while one request is active', async () => {
    const firstRequest = deferred<InvitationRecord>()
    let persistedInvitation = invitationRecord
    const save = vi
      .fn<(payload: InvitationUpdatePayload) => Promise<InvitationRecord>>()
      .mockImplementationOnce((payload) => {
        persistedInvitation = { ...persistedInvitation, ...payload }
        return firstRequest.promise
      })
      .mockImplementationOnce(async (payload) => {
        persistedInvitation = {
          ...persistedInvitation,
          ...payload,
          updated_at: '2030-01-01T10:02:00Z',
        }
        return persistedInvitation
      })
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = 'Анна'
    const flushing = autosave.flush()

    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenNthCalledWith(1, { author_name: 'Анна' })

    autosave.form.recipient_name = 'Виктор'
    firstRequest.resolve({
      ...persistedInvitation,
      updated_at: '2030-01-01T10:01:00Z',
    })

    await expect(flushing).resolves.toBe(true)
    expect(save).toHaveBeenCalledTimes(2)
    expect(save).toHaveBeenNthCalledWith(2, { recipient_name: 'Виктор' })
    expect(autosave.form).toMatchObject({
      author_name: 'Анна',
      recipient_name: 'Виктор',
    })
    expect(autosave.status.value).toBe('saved')
    scope.stop()
  })

  it('reports a network error and retries the same pending change', async () => {
    const save = vi
      .fn<(payload: InvitationUpdatePayload) => Promise<InvitationRecord>>()
      .mockRejectedValueOnce({ statusCode: 503 })
      .mockImplementationOnce(async payload => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.message = 'Новое сообщение'

    await expect(autosave.flush()).resolves.toBe(false)
    expect(autosave.status.value).toBe('error')
    expect(autosave.errorMessage.value).toContain('связаться')
    expect(autosave.hasUnsavedChanges.value).toBe(true)

    await expect(autosave.retry()).resolves.toBe(true)
    expect(save).toHaveBeenCalledTimes(2)
    expect(autosave.status.value).toBe('saved')
    scope.stop()
  })

  it('blocks invalid data locally without making a request', async () => {
    const save = vi.fn(async (payload: InvitationUpdatePayload) => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = '   '

    await expect(autosave.flush()).resolves.toBe(false)
    expect(save).not.toHaveBeenCalled()
    expect(autosave.status.value).toBe('error')
    expect(autosave.fieldErrors.value.author_name).toContain('от кого')
    scope.stop()
  })

  it('flushes immediately before the debounce delay finishes', async () => {
    vi.useFakeTimers()
    const save = vi.fn(async (payload: InvitationUpdatePayload) => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ debounceMs: 5_000, save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.recipient_name = 'Галина'

    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).toHaveBeenCalledOnce()

    await vi.runAllTimersAsync()
    expect(save).toHaveBeenCalledOnce()
    scope.stop()
  })

  it('cancels a pending debounce timer when its component scope is disposed', async () => {
    vi.useFakeTimers()
    const save = vi.fn(async (payload: InvitationUpdatePayload) => savedRecord(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = 'Анна'
    scope.stop()

    await vi.runAllTimersAsync()
    expect(save).not.toHaveBeenCalled()
  })

  it('ignores a completed request after its component scope is disposed', async () => {
    const pendingRequest = deferred<InvitationRecord>()
    const onSaved = vi.fn()
    const save = vi.fn(() => pendingRequest.promise)
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ onSaved, save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.author_name = 'Анна'
    const flushing = autosave.flush()

    scope.stop()
    pendingRequest.resolve(savedRecord({ author_name: 'Анна' }))

    await expect(flushing).resolves.toBe(false)
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('surfaces authorization failures to the owning page', async () => {
    const onAuthorizationError = vi.fn()
    const save = vi.fn(async () => {
      throw { statusCode: 403 }
    })
    const scope = effectScope()
    const autosave = scope.run(() => useBuilderAutosave({ onAuthorizationError, save }))!

    autosave.resetFromInvitation(invitationRecord)
    autosave.form.message = 'Изменение'

    await expect(autosave.flush()).resolves.toBe(false)
    expect(onAuthorizationError).toHaveBeenCalledOnce()
    expect(onAuthorizationError).toHaveBeenCalledWith(expect.objectContaining({ status: 403 }))
    scope.stop()
  })
})
