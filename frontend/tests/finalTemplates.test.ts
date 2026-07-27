import { describe, expect, it } from 'vitest'
import {
  DEFAULT_FINAL_TEXT_TEMPLATE,
  FINAL_TEMPLATE_VARIABLES,
  FinalTemplateValidationError,
  buildFinalTemplateContext,
  buildPreviewFinalTemplateContext,
  normalizeFinalTextTemplate,
  renderFinalTextTemplate,
  renderFinalTextTemplateSafely,
} from '../utils/finalTemplates'

const context = {
  activity: 'Кино',
  author: 'Алиса',
  date: '27 июля',
  place: 'Кофейня',
  recipient: 'Борис',
  time: '19:00',
}

describe('safe final text templates', () => {
  it('publishes the exact supported variable allow-list', () => {
    expect(FINAL_TEMPLATE_VARIABLES).toEqual([
      'author',
      'recipient',
      'date',
      'time',
      'place',
      'activity',
    ])
  })

  it('renders every allowed variable as plain text', () => {
    expect(renderFinalTextTemplate(
      '{recipient}, {author} ждёт тебя {date} в {time}, место — {place}, план — {activity}.',
      context,
    )).toBe('Борис, Алиса ждёт тебя 27 июля в 19:00, место — Кофейня, план — Кино.')
  })

  it('does not parse substituted user values as another template', () => {
    expect(renderFinalTextTemplate('Получатель: {recipient}', {
      ...context,
      recipient: '{author.name}',
    })).toBe('Получатель: {author.name}')
  })

  it('supports literal escaped braces without treating them as variables', () => {
    expect(renderFinalTextTemplate('План {{готов}} для {recipient}', context))
      .toBe('План {готов} для Борис')
  })

  it.each([
    '{unknown}',
    '{author.name}',
    '{activity[title]}',
    '{date:>20}',
    '{recipient!r}',
    '{}',
    '{recipient',
    'recipient}',
  ])('rejects unsupported or malformed syntax: %s', (template) => {
    expect(() => normalizeFinalTextTemplate(template))
      .toThrow(FinalTemplateValidationError)
  })

  it('trims the template and rejects empty or oversized values', () => {
    const unicodeBoundaryTemplate = `${'x'.repeat(999)}💘`

    expect(normalizeFinalTextTemplate('  Привет, {recipient}!  '))
      .toBe('Привет, {recipient}!')
    expect(() => normalizeFinalTextTemplate('   ')).toThrow(/пустым/i)
    expect(normalizeFinalTextTemplate(unicodeBoundaryTemplate)).toBe(unicodeBoundaryTemplate)
    expect(() => normalizeFinalTextTemplate('x'.repeat(1001))).toThrow(/1000/i)
  })

  it('falls back to the stable default when persisted data is malformed', () => {
    expect(renderFinalTextTemplateSafely('{recipient.name}', context))
      .toBe(renderFinalTextTemplate(DEFAULT_FINAL_TEXT_TEMPLATE, context))
  })

  it('builds real and preview contexts without inventing executable values', () => {
    expect(buildFinalTemplateContext({
      activityTitle: '',
      authorName: ' Алиса ',
      place: ' Кофейня ',
      recipientName: ' Борис ',
      startsAt: 'not-a-date',
    })).toEqual({
      activity: 'приятное свидание',
      author: 'Алиса',
      date: 'в выбранный день',
      place: 'Кофейня',
      recipient: 'Борис',
      time: 'в выбранное время',
    })

    expect(buildPreviewFinalTemplateContext({
      activity: { id: 'activity', label: 'Кино', description: 'Премьера' },
      authorName: 'Алиса',
      date: {
        id: 'date',
        label: '27 июля · 19:00',
        description: 'Кофейня — столик у окна',
      },
      recipientName: 'Борис',
    })).toEqual({
      activity: 'Кино',
      author: 'Алиса',
      date: '27 июля',
      place: 'Кофейня',
      recipient: 'Борис',
      time: '19:00',
    })
  })
})
