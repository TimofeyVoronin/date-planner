import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('public invitation resume integration', () => {
  it('renders a dismissible restoration notice from the initial server snapshot', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const notice = readFileSync(
      new URL('../components/invitation/PublicResumeNotice.vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain('getPublicResumeNotice(nextInvitation, currentTime.value)')
    expect(page).toContain('<PublicResumeNotice')
    expect(page).toContain('@dismiss="clearResumeNotice"')
    expect(notice).toContain('Скрыть сообщение о восстановлении')
  })

  it('refreshes a stale snapshot when the tab becomes visible or focused again', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain("document.addEventListener('visibilitychange'")
    expect(page).toContain("window.addEventListener('focus'")
    expect(page).toContain('shouldRefreshPublicSnapshotOnResume(lastSnapshotReceivedAt)')
    expect(page).toContain('!force && hasUnsavedPublicChoice.value')
    expect(page).toContain('api.getPublicInvitation(invitationId.value)')
    expect(page).toContain('resumeNotice.value = getPublicResumeNotice(nextInvitation')
    expect(page).toContain('refreshPublicSnapshotOnResume(true)')
  })

  it('returns an open page to date selection when its saved date expires', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )

    expect(page).toContain('watch(serverStage')
    expect(page).toContain("nextStage === 'date_selection'")
    expect(page).toContain("previousStage === 'activity_selection'")
    expect(page).toContain("previousStage === 'awaiting_confirmation'")
    expect(page).toContain('applyPersistedPlanSelection(invitation.value)')
  })
})
