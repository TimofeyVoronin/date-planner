import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('bounded public decline flow', () => {
  it('uses a dedicated neutral decline card and an explicit reversible action', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const card = readFileSync(
      new URL('../components/invitation/PublicDeclinedCard.vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain('<PublicDeclinedCard')
    expect(page).toContain(`@accept="saveResponse('accepted')"`)
    expect(card).toContain('Спасибо за честный ответ')
    expect(card).toContain('Никаких дополнительных действий не требуется')
    expect(card).toContain('Всё-таки согласиться')
    expect(card).not.toContain('Очень жаль')
    expect(card).not.toContain('Может всё таки да')
  })

  it('enables four pointer evasions while waiting for the persisted decline', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const invitationCard = readFileSync(
      new URL('../components/invitation/InvitationPreviewCard.vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain('defer-decline-until-persisted')
    expect(page).toContain('runaway-decline')
    expect(page).toContain(`:answers-disabled="responseSaveState === 'saving'"`)
    expect(page).not.toContain('direct-decline')
    expect(invitationCard).toContain(
      "props.deferDeclineUntilPersisted && status === 'declined'",
    )
    expect(invitationCard).toContain('runawayEnabled: props.runawayDecline')
    expect(invitationCard).toContain(
      'runawayLimitReached: runawayLimitReached.value',
    )
    expect(invitationCard).toContain('keyboardActivation: event.detail === 0')
    expect(invitationCard).toContain('prefersReducedMotion: prefersReducedMotion.value')
    expect(invitationCard).toContain('{{ RUNAWAY_ATTEMPT_LIMIT }} попытках')
    expect(invitationCard).toContain('props.previewOnly || props.answersDisabled')
    expect(invitationCard.match(/:disabled="answersDisabled"/g)).toHaveLength(2)
  })
})
