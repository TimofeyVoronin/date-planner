import { describe, expect, it } from 'vitest'
import {
  buildInvitationSharePayload,
  buildTelegramShareUrl,
  buildWhatsAppShareUrl,
  shareInvitationNatively,
  supportsNativeShare,
  type NativeShareNavigator,
} from '../utils/sharing'

const publicUrl = 'https://dates.example/invite/d9428888-122b-11e1-b85c-61cd3cbb3210'
const payload = buildInvitationSharePayload('  Алиса  ', ' Борис ', publicUrl)

describe('DPL-702 invitation sharing', () => {
  it('builds a personal share payload containing only the public URL', () => {
    expect(payload).toEqual({
      title: 'Личное приглашение 💌',
      text: 'Борис, для тебя приглашение от Алиса 💌',
      url: publicUrl,
    })
    expect(JSON.stringify(payload)).not.toContain('token=')
    expect(JSON.stringify(payload)).not.toContain('/manage/')
  })

  it('builds the official Telegram share URL with separate text and link parameters', () => {
    const telegramUrl = new URL(buildTelegramShareUrl(payload))

    expect(telegramUrl.origin).toBe('https://t.me')
    expect(telegramUrl.pathname).toBe('/share/url')
    expect(telegramUrl.searchParams.get('url')).toBe(publicUrl)
    expect(telegramUrl.searchParams.get('text')).toBe(payload.text)
  })

  it('builds a WhatsApp message containing the invitation text and public URL', () => {
    const whatsAppUrl = new URL(buildWhatsAppShareUrl(payload))

    expect(whatsAppUrl.origin).toBe('https://wa.me')
    expect(whatsAppUrl.pathname).toBe('/')
    expect(whatsAppUrl.searchParams.get('text')).toBe(`${payload.text}\n${publicUrl}`)
  })

  it('detects native sharing without making it a required path', () => {
    expect(supportsNativeShare(undefined)).toBe(false)
    expect(supportsNativeShare({})).toBe(false)
    expect(supportsNativeShare({ share: async () => undefined })).toBe(true)
  })

  it('passes the exact safe payload to the native share API', async () => {
    let receivedPayload: ShareData | undefined
    const navigatorValue: NativeShareNavigator = {
      share: async (data) => {
        receivedPayload = data
      },
    }

    await expect(shareInvitationNatively(payload, navigatorValue)).resolves.toBe('shared')
    expect(receivedPayload).toEqual(payload)
  })

  it('treats closing the native share sheet as cancellation rather than an error', async () => {
    const navigatorValue: NativeShareNavigator = {
      share: async () => {
        throw { name: 'AbortError' }
      },
    }

    await expect(shareInvitationNatively(payload, navigatorValue)).resolves.toBe('cancelled')
  })

  it('returns explicit fallback outcomes for unavailable or failed native sharing', async () => {
    await expect(shareInvitationNatively(payload, undefined)).resolves.toBe('unsupported')
    await expect(shareInvitationNatively(payload, {
      share: async () => {
        throw new Error('Share unavailable')
      },
    })).resolves.toBe('failed')
  })
})
