import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  PUBLIC_INVITATION_META_DESCRIPTION,
  PUBLIC_INVITATION_META_TITLE,
  PUBLIC_INVITATION_SOCIAL_IMAGE_PATH,
  buildPublicInvitationSeoMetadata,
} from '../utils/seo'

describe('DPL-703 safe public invitation metadata', () => {
  it('builds canonical and image URLs without carrying query or fragment data', () => {
    const metadata = buildPublicInvitationSeoMetadata(
      new URL(
        'https://planner.example/invite/current?utm_source=chat#token=secret-management-value',
      ),
      'd9428888-122b-11e1-b85c-61cd3cbb3210',
    )

    expect(metadata.canonicalUrl).toBe(
      'https://planner.example/invite/d9428888-122b-11e1-b85c-61cd3cbb3210',
    )
    expect(metadata.imageUrl).toBe(
      `https://planner.example${PUBLIC_INVITATION_SOCIAL_IMAGE_PATH}`,
    )
    expect(JSON.stringify(metadata)).not.toContain('utm_source')
    expect(JSON.stringify(metadata)).not.toContain('token=')
    expect(metadata).toMatchObject({
      description: PUBLIC_INVITATION_META_DESCRIPTION,
      imageHeight: 630,
      imageWidth: 1200,
      title: PUBLIC_INVITATION_META_TITLE,
    })
  })

  it('encodes unexpected route values instead of inserting them into metadata as a path', () => {
    const metadata = buildPublicInvitationSeoMetadata(
      new URL('https://planner.example/invite/current'),
      '../manage/example?token=secret',
    )

    expect(metadata.canonicalUrl).toBe(
      'https://planner.example/invite/..%2Fmanage%2Fexample%3Ftoken%3Dsecret',
    )
  })

  it('keeps recipient content out of server-rendered social metadata', () => {
    const page = readFileSync(
      new URL('../app/pages/invite/[id].vue', import.meta.url),
      'utf8',
    )
    const seoBlock = page.slice(
      page.indexOf('useSeoMeta({'),
      page.indexOf('function applyPersistedPlanSelection'),
    )

    expect(page).toContain(
      'const invitationSeo = computed(() => buildPublicInvitationSeoMetadata(',
    )
    expect(seoBlock).toContain("robots: 'noindex, nofollow'")
    expect(seoBlock).toContain("twitterCard: 'summary_large_image'")
    expect(seoBlock).toContain("{ rel: 'canonical', href: invitationSeo.value.canonicalUrl }")
    expect(seoBlock).not.toContain('invitation.value')
    expect(seoBlock).not.toContain('author_name')
    expect(seoBlock).not.toContain('recipient_name')
    expect(seoBlock).not.toContain('message')
  })

  it('ships a 1200 by 630 PNG preview from the public directory', () => {
    const png = readFileSync(
      new URL('../public/images/social/invitation-preview.png', import.meta.url),
    )

    expect(png.subarray(1, 4).toString('ascii')).toBe('PNG')
    expect(png.readUInt32BE(16)).toBe(1200)
    expect(png.readUInt32BE(20)).toBe(630)
  })
})
