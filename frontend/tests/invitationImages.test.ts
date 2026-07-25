import { describe, expect, it } from 'vitest'
import {
  getInvitationImageByKey,
  getInvitationImagesForScreens,
  getInvitationImagesForScreenType,
  INVITATION_IMAGE_LIBRARY,
  isInvitationImageCompatible,
  isInvitationImageKey,
  resolveInvitationImageUrl,
} from '../utils/invitationImages'

describe('built-in invitation image library', () => {
  it('contains unique local assets with accessible metadata', () => {
    const keys = INVITATION_IMAGE_LIBRARY.map(image => image.key)
    const assetPaths = INVITATION_IMAGE_LIBRARY.map(image => image.assetPath)

    expect(INVITATION_IMAGE_LIBRARY).toHaveLength(18)
    expect(new Set(keys).size).toBe(keys.length)
    expect(new Set(assetPaths).size).toBe(assetPaths.length)
    expect(INVITATION_IMAGE_LIBRARY.every(image => image.label.length > 0)).toBe(true)
    expect(INVITATION_IMAGE_LIBRARY.every(image => image.description.length > 0)).toBe(true)
    expect(INVITATION_IMAGE_LIBRARY.every(image => image.altText.length > 0)).toBe(true)
    expect(INVITATION_IMAGE_LIBRARY.every(image => (
      image.assetPath.startsWith('/images/invitation-library/')
      && image.assetPath.endsWith('.svg')
    ))).toBe(true)
  })

  it('provides a useful number of options for each screen', () => {
    expect(getInvitationImagesForScreenType('invitation')).toHaveLength(4)
    expect(getInvitationImagesForScreenType('acceptance')).toHaveLength(4)
    expect(getInvitationImagesForScreenType('date_selection')).toHaveLength(3)
    expect(getInvitationImagesForScreenType('activity_selection')).toHaveLength(3)
    expect(getInvitationImagesForScreenType('final')).toHaveLength(4)
  })

  it('recognizes default keys and enforces screen compatibility', () => {
    expect(isInvitationImageKey('invitation-default')).toBe(true)
    expect(isInvitationImageKey('unknown-image')).toBe(false)
    expect(isInvitationImageCompatible('invitation-default', 'invitation')).toBe(true)
    expect(isInvitationImageCompatible('invitation-default', 'final')).toBe(false)
    expect(getInvitationImageByKey('final-default')).toMatchObject({
      label: 'План готов',
      screenType: 'final',
    })
  })

  it('filters several active builder screen types without changing library order', () => {
    const images = getInvitationImagesForScreens(['invitation', 'acceptance'])

    expect(images).toHaveLength(8)
    expect(images[0]?.key).toBe('invitation-default')
    expect(images[4]?.key).toBe('acceptance-default')
    expect(images.every(image => (
      image.screenType === 'invitation' || image.screenType === 'acceptance'
    ))).toBe(true)
  })

  it('resolves public paths against root and custom Nuxt base URLs', () => {
    expect(resolveInvitationImageUrl('/images/example.svg')).toBe('/images/example.svg')
    expect(resolveInvitationImageUrl('/images/example.svg', '/date-planner/')).toBe(
      '/date-planner/images/example.svg',
    )
    expect(resolveInvitationImageUrl('images/example.svg', '/date-planner')).toBe(
      '/date-planner/images/example.svg',
    )
  })
})
