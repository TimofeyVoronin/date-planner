import { describe, expect, it } from 'vitest'
import {
  BUILDER_STEPS,
  builderStepSessionKey,
  buildBuilderPath,
  getBuilderAccessBlock,
  getBuilderStepDefinition,
  getNextBuilderStep,
  getPreviousBuilderStep,
  isBuilderStepNumber,
  parseBuilderStep,
  resolveBuilderStep,
} from '../utils/builder'

describe('builder step navigation', () => {
  it('defines four ordered and uniquely identified steps', () => {
    expect(BUILDER_STEPS.map(step => step.number)).toEqual([1, 2, 3, 4])
    expect(new Set(BUILDER_STEPS.map(step => step.id)).size).toBe(4)
    expect(BUILDER_STEPS.every(step => step.plannedFeatures.length >= 3)).toBe(true)
  })

  it('recognizes only supported integer step numbers', () => {
    expect(isBuilderStepNumber(1)).toBe(true)
    expect(isBuilderStepNumber(4)).toBe(true)
    expect(isBuilderStepNumber(0)).toBe(false)
    expect(isBuilderStepNumber(5)).toBe(false)
    expect(isBuilderStepNumber('2')).toBe(false)
  })

  it('parses canonical query values and rejects malformed input', () => {
    expect(parseBuilderStep('1')).toBe(1)
    expect(parseBuilderStep('4')).toBe(4)
    expect(parseBuilderStep('01')).toBeNull()
    expect(parseBuilderStep('2.0')).toBeNull()
    expect(parseBuilderStep(['2'])).toBeNull()
    expect(parseBuilderStep(null)).toBeNull()
  })

  it('prefers a valid URL step and falls back to the saved step or the beginning', () => {
    expect(resolveBuilderStep('3', '2')).toBe(3)
    expect(resolveBuilderStep('invalid', '2')).toBe(2)
    expect(resolveBuilderStep(undefined, '4')).toBe(4)
    expect(resolveBuilderStep('7', '9')).toBe(1)
  })

  it('stops navigation at the first and last step', () => {
    expect(getPreviousBuilderStep(1)).toBeNull()
    expect(getPreviousBuilderStep(3)).toBe(2)
    expect(getNextBuilderStep(2)).toBe(3)
    expect(getNextBuilderStep(4)).toBeNull()
  })

  it('returns the presentation for the active step', () => {
    expect(getBuilderStepDefinition(1)).toMatchObject({
      id: 'invitation',
      label: 'Приглашение',
    })
    expect(getBuilderStepDefinition(4)).toMatchObject({
      id: 'final',
      label: 'Финал',
    })
  })
})

describe('builder routing and access', () => {
  const id = 'd9428888-122b-11e1-b85c-61cd3cbb3210'

  it('builds an invitation-specific route and session key', () => {
    expect(buildBuilderPath(id)).toBe(`/manage/${id}/builder?step=1`)
    expect(buildBuilderPath(id, 3)).toBe(`/manage/${id}/builder?step=3`)
    expect(builderStepSessionKey(id)).toBe(`date-planner:builder-step:${id}`)
  })

  it('allows only extended unpublished invitations into the builder', () => {
    expect(getBuilderAccessBlock({
      creation_mode: 'extended',
      publication_status: 'draft',
    })).toBeNull()
    expect(getBuilderAccessBlock({
      creation_mode: 'quick',
      publication_status: 'published',
    })).toBe('quick-mode')
    expect(getBuilderAccessBlock({
      creation_mode: 'extended',
      publication_status: 'published',
    })).toBe('published')
  })
})
