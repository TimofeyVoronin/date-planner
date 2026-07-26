import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { getPlanRecoveryPresentation } from '../utils/planning'

describe('expired plan recovery', () => {
  it('explains the narrow published before-acceptance recovery contract', () => {
    const presentation = getPlanRecoveryPresentation('before_acceptance')

    expect(presentation.eyebrow).toContain('Опубликованный набор')
    expect(presentation.description).toContain('единственное состояние')
    expect(presentation.description).toContain('не изменит само приглашение')
  })

  it('keeps the existing post-acceptance recovery explanation', () => {
    const presentation = getPlanRecoveryPresentation('after_acceptance')

    expect(presentation.eyebrow).toBe('Нужно обновить план')
    expect(presentation.description).toContain('сбросит прежний выбор')
  })

  it('opens one recovery editor for either planning mode', () => {
    const managementPage = readFileSync(
      new URL('../app/pages/manage/[id]/index.vue', import.meta.url),
      'utf8',
    )
    const editor = readFileSync(
      new URL('../components/planning/PlanOptionsEditor.vue', import.meta.url),
      'utf8',
    )

    expect(managementPage).toContain(`v-else-if="confirmationStage === 'expired'"`)
    expect(managementPage).not.toContain(
      `confirmationStage === 'expired'\n                && invitation.planning_mode === 'after_acceptance'`,
    )
    expect(managementPage).toContain('variant="recovery"')
    expect(managementPage).not.toContain('появится в DPL-304')
    expect(editor).toContain(`props.variant === 'recovery'`)
    expect(editor).toContain('Заменить устаревшие варианты')
  })
})
