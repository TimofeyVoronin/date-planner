import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import type { ActivityOptionRecord } from '../types/activity'
import {
  findSelectedActivityOption,
  getActivitySelectionScreenPresentation,
  getPersistedActivitySelectionState,
  parseActivitySelectionApiError,
  refreshActivitySelectionAfterRejection,
  shouldRefreshActivitySelection,
} from '../utils/activities'

const options: ActivityOptionRecord[] = [
  {
    id: 'activity-b',
    title: 'Кино',
    description: 'Премьера',
    image_key: 'activity-movie',
    place: 'Кинотеатр',
    position: 1,
  },
  {
    id: 'activity-a',
    title: 'Кофе',
    description: 'Спокойный разговор',
    image_key: 'activity-coffee',
    place: 'Кофейня',
    position: 0,
  },
]

describe('recipient activity selection helpers', () => {
  it('resolves saved selections without inventing unknown options', () => {
    expect(findSelectedActivityOption(options, 'activity-a')?.title).toBe('Кофе')
    expect(findSelectedActivityOption(options, 'missing')).toBeNull()
    expect(findSelectedActivityOption(options, null)).toBeNull()

    expect(getPersistedActivitySelectionState(options, 'activity-b')).toEqual({
      isSaved: true,
      selectedOptionId: 'activity-b',
    })
    expect(getPersistedActivitySelectionState(options, 'missing')).toEqual({
      isSaved: false,
      selectedOptionId: null,
    })
  })

  it('uses configured activity-selection copy and safe defaults', () => {
    expect(getActivitySelectionScreenPresentation(null)).toEqual({
      buttonText: 'Сохранить активность',
      imageKey: 'activity-selection-default',
      subtitle: 'Выбор можно изменить до окончательного подтверждения автором.',
      title: 'Чем займёмся?',
    })

    expect(getActivitySelectionScreenPresentation({
      screen_type: 'activity_selection',
      title: 'Выбери наше приключение',
      subtitle: 'Можно передумать позже',
      button_text: 'Хочу это',
      secondary_button_text: '',
      image_key: 'activity-movie',
      template_text: '',
    })).toEqual({
      buttonText: 'Хочу это',
      imageKey: 'activity-movie',
      subtitle: 'Можно передумать позже',
      title: 'Выбери наше приключение',
    })
  })

  it('refreshes stale public state only for selection conflicts', async () => {
    expect(shouldRefreshActivitySelection({
      code: null,
      fieldErrors: {},
      message: 'Bad request',
      status: 400,
    })).toBe(true)
    expect(shouldRefreshActivitySelection({
      code: null,
      fieldErrors: {},
      message: 'Conflict',
      status: 409,
    })).toBe(true)
    expect(shouldRefreshActivitySelection({
      code: null,
      fieldErrors: {},
      message: 'Server error',
      status: 500,
    })).toBe(false)

    const loadLatest = vi.fn(async () => ({ id: 'latest' }))
    await expect(refreshActivitySelectionAfterRejection({
      code: null,
      fieldErrors: {},
      message: 'Conflict',
      status: 409,
    }, loadLatest)).resolves.toEqual({ id: 'latest' })
    expect(loadLatest).toHaveBeenCalledOnce()
  })

  it('maps unavailable and frozen selections to recipient-facing messages', () => {
    expect(parseActivitySelectionApiError({ statusCode: 400 }).message).toBe(
      'Эта активность больше недоступна. Обнови список и выбери другой вариант.',
    )
    expect(parseActivitySelectionApiError({ statusCode: 409 }).message).toBe(
      'Выбор активности уже нельзя изменить. Загрузи актуальное состояние приглашения.',
    )
  })
})

describe('DPL-403 public and management integration', () => {
  it('connects the public selector to the activity selection endpoint', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const api = readFileSync(
      new URL('../composables/useInvitationsApi.ts', import.meta.url),
      'utf8',
    )

    expect(page).toContain('<ActivityOptionSelector')
    expect(page).toContain(':save-state="activitySelectionSaveState"')
    expect(page).toContain('api.saveActivitySelection(invitationId.value')
    expect(page).toContain(':options="invitation.activity_options"')
    expect(api).toContain('/activity-selection/')
  })

  it('keeps author confirmation disabled until an activity is selected', () => {
    const managementPage = readFileSync(
      new URL('../app/pages/manage/[id]/index.vue', import.meta.url),
      'utf8',
    )
    const planning = readFileSync(
      new URL('../utils/planning.ts', import.meta.url),
      'utf8',
    )

    expect(managementPage).toContain('activitySelectionRequired')
    expect(managementPage).toContain('!selectedActivityOption')
    expect(managementPage).toContain('Получатель выбрал дату, но ещё не сохранил активность')
    expect(planning).toContain("parsedError.code === 'activity_selection_required'")
  })
})
