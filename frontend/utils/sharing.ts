export type InvitationSharePayload = {
  text: string
  title: string
  url: string
}

export type NativeShareNavigator = {
  share?: (data: ShareData) => Promise<void>
}

export type NativeShareOutcome = 'cancelled' | 'failed' | 'shared' | 'unsupported'

function normalizeShareName(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

function isAbortError(error: unknown): boolean {
  if (typeof error !== 'object' || error === null || !('name' in error)) {
    return false
  }

  return (error as { name?: unknown }).name === 'AbortError'
}

export function buildInvitationSharePayload(
  authorName: string,
  recipientName: string,
  publicUrl: string,
): InvitationSharePayload {
  const normalizedAuthorName = normalizeShareName(authorName)
  const normalizedRecipientName = normalizeShareName(recipientName)

  return {
    title: 'Личное приглашение 💌',
    text: `${normalizedRecipientName}, для тебя приглашение от ${normalizedAuthorName} 💌`,
    url: publicUrl,
  }
}

export function buildTelegramShareUrl(payload: InvitationSharePayload): string {
  const shareUrl = new URL('https://t.me/share/url')

  shareUrl.searchParams.set('url', payload.url)
  shareUrl.searchParams.set('text', payload.text)

  return shareUrl.toString()
}

export function buildWhatsAppShareUrl(payload: InvitationSharePayload): string {
  const shareUrl = new URL('https://wa.me/')

  shareUrl.searchParams.set('text', `${payload.text}\n${payload.url}`)

  return shareUrl.toString()
}

export function supportsNativeShare(
  navigatorValue: NativeShareNavigator | undefined,
): boolean {
  return typeof navigatorValue?.share === 'function'
}

export async function shareInvitationNatively(
  payload: InvitationSharePayload,
  navigatorValue: NativeShareNavigator | undefined,
): Promise<NativeShareOutcome> {
  const share = navigatorValue?.share

  if (!share) {
    return 'unsupported'
  }

  try {
    await share.call(navigatorValue, payload)
    return 'shared'
  }
  catch (error: unknown) {
    return isAbortError(error) ? 'cancelled' : 'failed'
  }
}
