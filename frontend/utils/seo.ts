export const PUBLIC_INVITATION_META_TITLE = 'Тебе пришло личное приглашение — Date Planner'
export const PUBLIC_INVITATION_META_DESCRIPTION = (
  'Открой персональное приглашение и выбери удобный вариант встречи.'
)
export const PUBLIC_INVITATION_SOCIAL_IMAGE_PATH = (
  '/images/social/invitation-preview.png'
)

export type PublicInvitationSeoMetadata = {
  canonicalUrl: string
  description: string
  imageAlt: string
  imageHeight: number
  imageUrl: string
  imageWidth: number
  title: string
}

function buildAbsoluteUrl(origin: string, path: string): string {
  return new URL(path, origin).toString()
}

export function buildPublicInvitationSeoMetadata(
  requestUrl: URL,
  invitationId: string,
): PublicInvitationSeoMetadata {
  const canonicalPath = `/invite/${encodeURIComponent(invitationId)}`

  return {
    canonicalUrl: buildAbsoluteUrl(requestUrl.origin, canonicalPath),
    description: PUBLIC_INVITATION_META_DESCRIPTION,
    imageAlt: 'Конверт с сердцем и подпись Date Planner',
    imageHeight: 630,
    imageUrl: buildAbsoluteUrl(requestUrl.origin, PUBLIC_INVITATION_SOCIAL_IMAGE_PATH),
    imageWidth: 1200,
    title: PUBLIC_INVITATION_META_TITLE,
  }
}
