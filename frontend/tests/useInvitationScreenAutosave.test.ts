import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useInvitationScreenAutosave } from '../composables/useInvitationScreenAutosave'
import type {
  InvitationScreenRecord,
  InvitationScreenUpdatePayload,
} from '../types/screen'

const screenRecord: InvitationScreenRecord = {
  screen_type: 'invitation',
  title: 'Ты пойдёшь со мной на свидание?',
  subtitle: 'Для тебя приготовили особенное приглашение 💌',
  button_text: 'Да! 😍',
  secondary_button_text: 'Нет',
  image_key: 'invitation-default',
  template_text: '',
}

const acceptanceScreenRecord: InvitationScreenRecord = {
  screen_type: 'acceptance',
  title: 'Ура! 💘',
  subtitle: 'Теперь давай выберем, когда увидимся.',
  button_text: 'Выбрать дату',
  secondary_button_text: '',
  image_key: 'acceptance-default',
  template_text: '',
}

const finalScreenRecord: InvitationScreenRecord = {
  screen_type: 'final',
  title: 'Договорились 💞',
  subtitle: 'Осталось дождаться итогового подтверждения плана.',
  button_text: 'Посмотреть план',
  secondary_button_text: '',
  image_key: 'final-default',
  template_text: '{recipient}, жду тебя {date} в {time}. Встречаемся в {place}, а дальше нас ждёт {activity} 💘',
}

function savedScreen(payload: InvitationScreenUpdatePayload): InvitationScreenRecord {
  return {
    ...screenRecord,
    ...payload,
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

describe('invitation screen autosave', () => {
  it('debounces rapid edits and sends only the final minimal PATCH', async () => {
    vi.useFakeTimers()
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => savedScreen(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ debounceMs: 800, save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.title = 'Новый вопрос'
    autosave.form.button_text = 'Конечно'

    await vi.advanceTimersByTimeAsync(799)
    expect(save).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith({
      title: 'Новый вопрос',
      button_text: 'Конечно',
    })
    expect(autosave.status.value).toBe('saved')
    expect(autosave.hasUnsavedChanges.value).toBe(false)
    scope.stop()
  })

  it('does not save whitespace-only differences', async () => {
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => savedScreen(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.title = `  ${screenRecord.title}  `
    autosave.form.subtitle = ` ${screenRecord.subtitle} `

    expect(autosave.isDirty.value).toBe(false)
    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).not.toHaveBeenCalled()
    scope.stop()
  })

  it('queues a newer image choice while one request is active', async () => {
    const firstRequest = deferred<InvitationScreenRecord>()
    let persistedScreen = screenRecord
    const save = vi
      .fn<(payload: InvitationScreenUpdatePayload) => Promise<InvitationScreenRecord>>()
      .mockImplementationOnce((payload) => {
        persistedScreen = { ...persistedScreen, ...payload }
        return firstRequest.promise
      })
      .mockImplementationOnce(async (payload) => {
        persistedScreen = { ...persistedScreen, ...payload }
        return persistedScreen
      })
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.title = 'Новый вопрос'
    const flushing = autosave.flush()

    autosave.form.image_key = 'invitation-moon'
    firstRequest.resolve(persistedScreen)

    await expect(flushing).resolves.toBe(true)
    expect(save).toHaveBeenCalledTimes(2)
    expect(save).toHaveBeenNthCalledWith(2, { image_key: 'invitation-moon' })
    expect(autosave.form).toMatchObject({
      title: 'Новый вопрос',
      image_key: 'invitation-moon',
    })
    scope.stop()
  })

  it('autosaves the acceptance screen without requiring a decline button', async () => {
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => ({
      ...acceptanceScreenRecord,
      ...payload,
    }))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(acceptanceScreenRecord)
    autosave.form.title = 'Ты правда согласился?'
    autosave.form.image_key = 'acceptance-together'

    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).toHaveBeenCalledWith({
      title: 'Ты правда согласился?',
      image_key: 'acceptance-together',
    })
    expect(autosave.fieldErrors.value.secondary_button_text).toBeUndefined()
    expect(autosave.status.value).toBe('saved')
    scope.stop()
  })

  it('autosaves final presentation and safe template without an action button', async () => {
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => ({
      ...finalScreenRecord,
      ...payload,
    }))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(finalScreenRecord)
    autosave.form.title = 'До встречи!'
    autosave.form.button_text = ''
    autosave.form.image_key = 'final-night'
    autosave.form.template_text = '{recipient}, план готов: {date}, {time}, {place}, {activity}.'

    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).toHaveBeenCalledWith({
      title: 'До встречи!',
      image_key: 'final-night',
      template_text: '{recipient}, план готов: {date}, {time}, {place}, {activity}.',
    })
    expect(autosave.fieldErrors.value.button_text).toBeUndefined()
    expect(autosave.status.value).toBe('saved')
    scope.stop()
  })

  it('blocks an unsafe final template before making a request', async () => {
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => ({
      ...finalScreenRecord,
      ...payload,
    }))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(finalScreenRecord)
    autosave.form.template_text = '{author.name}'

    await expect(autosave.flush()).resolves.toBe(false)
    expect(save).not.toHaveBeenCalled()
    expect(autosave.fieldErrors.value.template_text).toBeTruthy()
    expect(autosave.status.value).toBe('error')
    scope.stop()
  })

  it('reports a validation error before making a request', async () => {
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => savedScreen(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.secondary_button_text = '   '

    await expect(autosave.flush()).resolves.toBe(false)
    expect(save).not.toHaveBeenCalled()
    expect(autosave.fieldErrors.value.secondary_button_text).toContain('отказа')
    expect(autosave.status.value).toBe('error')
    scope.stop()
  })

  it('retries the same pending edit after a network error', async () => {
    const save = vi
      .fn<(payload: InvitationScreenUpdatePayload) => Promise<InvitationScreenRecord>>()
      .mockRejectedValueOnce({ statusCode: 503 })
      .mockImplementationOnce(async payload => savedScreen(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.subtitle = 'Новый подзаголовок'

    await expect(autosave.flush()).resolves.toBe(false)
    expect(autosave.status.value).toBe('error')
    expect(autosave.hasUnsavedChanges.value).toBe(true)

    await expect(autosave.retry()).resolves.toBe(true)
    expect(save).toHaveBeenCalledTimes(2)
    expect(autosave.status.value).toBe('saved')
    scope.stop()
  })

  it('flushes immediately and cancels the scheduled duplicate request', async () => {
    vi.useFakeTimers()
    const save = vi.fn(async (payload: InvitationScreenUpdatePayload) => savedScreen(payload))
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ debounceMs: 5_000, save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.button_text = 'Идём!'

    await expect(autosave.flush()).resolves.toBe(true)
    expect(save).toHaveBeenCalledOnce()

    await vi.runAllTimersAsync()
    expect(save).toHaveBeenCalledOnce()
    scope.stop()
  })

  it('cancels pending work and ignores a completed request after disposal', async () => {
    vi.useFakeTimers()
    const pendingRequest = deferred<InvitationScreenRecord>()
    const onSaved = vi.fn()
    const save = vi.fn(() => pendingRequest.promise)
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({ onSaved, save }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.title = 'Новый вопрос'
    const flushing = autosave.flush()

    scope.stop()
    pendingRequest.resolve(savedScreen({ title: 'Новый вопрос' }))

    await expect(flushing).resolves.toBe(false)
    await vi.runAllTimersAsync()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('surfaces capability failures to the builder page', async () => {
    const onAuthorizationError = vi.fn()
    const save = vi.fn(async () => {
      throw { statusCode: 403 }
    })
    const scope = effectScope()
    const autosave = scope.run(() => useInvitationScreenAutosave({
      onAuthorizationError,
      save,
    }))!

    autosave.resetFromScreen(screenRecord)
    autosave.form.title = 'Новый вопрос'

    await expect(autosave.flush()).resolves.toBe(false)
    expect(onAuthorizationError).toHaveBeenCalledWith(expect.objectContaining({ status: 403 }))
    scope.stop()
  })
})
