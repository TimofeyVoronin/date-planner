import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('DPL-701 publication success flow', () => {
  it('redirects published creations and draft publication to the dedicated result route', () => {
    const createForm = readFileSync(
      new URL('../components/invitation/InvitationCreateForm.vue', import.meta.url),
      'utf8',
    )
    const managePage = readFileSync(
      new URL('../app/pages/manage/[id]/index.vue', import.meta.url),
      'utf8',
    )

    expect(createForm).toContain("invitation.publication_status === 'published'")
    expect(createForm).toContain('navigateTo(buildPublicationSuccessPath(')
    expect(createForm).toContain('invitation.management_token')
    expect(managePage).toContain('await api.publishInvitation(invitationId.value, token)')
    expect(managePage).toContain(
      'await navigateTo(buildPublicationSuccessPath(invitationId.value, token))',
    )
  })

  it('loads the success page only through the management capability', () => {
    const page = readFileSync(
      new URL('../app/pages/manage/[id]/published.vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain('useManagementToken(invitationId)')
    expect(page).toContain('const token = takeManagementToken()')
    expect(page).toContain('api.getManagedInvitation(invitationId.value, token)')
    expect(page).toContain("nextInvitation.publication_status !== 'published'")
    expect(page).toContain("{ name: 'referrer', content: 'no-referrer' }")
    expect(page).toContain('buildManagementInvitationUrl(')
    expect(page).toContain('buildPublicInvitationUrl(')
  })

  it('separates the shareable link from the hidden management recovery link', () => {
    const component = readFileSync(
      new URL('../components/invitation/InvitationPublicationSuccess.vue', import.meta.url),
      'utf8',
    )

    expect(component).toContain('Ссылка для получателя')
    expect(component).toContain('В этой ссылке нет секретного ключа управления')
    expect(component).toContain('<details class="publication-success__secret"')
    expect(component).toContain('v-if="managementLinkRevealed"')
    expect(component).toContain('Показать резервную секретную ссылку')
    expect(component).toContain('Не пересылай её получателю')
    expect(component).toContain('@click="copyPublicLink"')
    expect(component).toContain('@click="copyManagementLink"')
    expect(component).not.toContain('Скопировать обе ссылки')
  })

  it('offers native, Telegram, WhatsApp, and manual-copy delivery paths', () => {
    const component = readFileSync(
      new URL('../components/invitation/InvitationPublicationSuccess.vue', import.meta.url),
      'utf8',
    )

    expect(component).toContain('buildInvitationSharePayload(')
    expect(component).toContain('props.publicUrl')
    expect(component).toContain('shareInvitationNatively(')
    expect(component).toContain('v-if="nativeShareSupported"')
    expect(component).toContain(':href="telegramShareUrl"')
    expect(component).toContain(':href="whatsAppShareUrl"')
    expect(component).toContain('target="_blank"')
    expect(component).toContain('rel="noopener noreferrer"')
    expect(component).toContain('@click="copyPublicLink"')
    expect(component).toContain('ручным запасным вариантом')
    expect(component).toMatch(
      /buildInvitationSharePayload\(\s*props\.authorName,\s*props\.recipientName,\s*props\.publicUrl,/,
    )
  })
})
