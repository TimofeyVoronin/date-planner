import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('respectful public decline flow', () => {
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

  it('keeps the playful runaway demo out of the real recipient decline action', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const invitationCard = readFileSync(
      new URL('../components/invitation/InvitationPreviewCard.vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain(':direct-decline="true"')
    expect(invitationCard).toContain('if (props.previewOnly || props.directDecline)')
    expect(invitationCard).toContain("props.directDecline && status === 'declined'")
    expect(invitationCard).toContain('v-if="!previewOnly && !directDecline"')
  })
})
