import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  APP_THEME_COLORS,
  APP_THEME_STORAGE_KEY,
  getOppositeAppTheme,
  isAppTheme,
  resolveAppTheme,
} from '../utils/theme'

function hexToRgb(value: string): [number, number, number] {
  const shortMatch = /^#([\da-f])([\da-f])([\da-f])$/i.exec(value)
  const normalizedValue = shortMatch
    ? `#${shortMatch[1]}${shortMatch[1]}${shortMatch[2]}${shortMatch[2]}${shortMatch[3]}${shortMatch[3]}`
    : value
  const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(normalizedValue)
  if (!match) {
    throw new Error(`Expected a six-digit hex color, received ${value}.`)
  }

  return [
    Number.parseInt(match[1] ?? '', 16),
    Number.parseInt(match[2] ?? '', 16),
    Number.parseInt(match[3] ?? '', 16),
  ]
}

function relativeLuminance(value: string): number {
  const channels = hexToRgb(value).map((channel) => {
    const normalized = channel / 255

    return normalized <= .04045
      ? normalized / 12.92
      : ((normalized + .055) / 1.055) ** 2.4
  })

  return (
    .2126 * (channels[0] ?? 0)
    + .7152 * (channels[1] ?? 0)
    + .0722 * (channels[2] ?? 0)
  )
}

function contrastRatio(first: string, second: string): number {
  const firstLuminance = relativeLuminance(first)
  const secondLuminance = relativeLuminance(second)
  const lighter = Math.max(firstLuminance, secondLuminance)
  const darker = Math.min(firstLuminance, secondLuminance)

  return (lighter + .05) / (darker + .05)
}

function themeToken(source: string, selector: string, token: string): string {
  const selectorStart = source.indexOf(`${selector} {`)
  if (selectorStart === -1) {
    throw new Error(`Missing ${selector} theme block.`)
  }

  const blockEnd = source.indexOf('\n}', selectorStart)
  const block = source.slice(selectorStart, blockEnd)
  const match = new RegExp(`--theme-${token}:\\s*(#[\\da-f]{6}|#[\\da-f]{3});`, 'i')
    .exec(block)
  if (!match?.[1]) {
    throw new Error(`Missing hex token --theme-${token} in ${selector}.`)
  }

  return match[1]
}

describe('application theme helpers', () => {
  it('uses a persisted valid theme before the operating-system preference', () => {
    expect(resolveAppTheme('light', true)).toBe('light')
    expect(resolveAppTheme('dark', false)).toBe('dark')
  })

  it('falls back to the operating-system preference for missing or invalid storage', () => {
    expect(resolveAppTheme(null, true)).toBe('dark')
    expect(resolveAppTheme('sepia', false)).toBe('light')
  })

  it('recognizes and toggles only the two supported themes', () => {
    expect(APP_THEME_STORAGE_KEY).toBe('date-planner-theme')
    expect(isAppTheme('light')).toBe(true)
    expect(isAppTheme('dark')).toBe(true)
    expect(isAppTheme('auto')).toBe(false)
    expect(getOppositeAppTheme('light')).toBe('dark')
    expect(getOppositeAppTheme('dark')).toBe('light')
    expect(APP_THEME_COLORS).toEqual({
      dark: '#171116',
      light: '#fff3f6',
    })
  })
})

describe('application theme integration', () => {
  const themeCss = readFileSync(
    new URL('../app/assets/css/theme.css', import.meta.url),
    'utf8',
  )
  const nuxtConfig = readFileSync(new URL('../nuxt.config.ts', import.meta.url), 'utf8')
  const app = readFileSync(new URL('../app/app.vue', import.meta.url), 'utf8')
  const colorThemeComposable = readFileSync(
    new URL('../composables/useColorTheme.ts', import.meta.url),
    'utf8',
  )
  const themeToggle = readFileSync(
    new URL('../components/AppThemeToggle.vue', import.meta.url),
    'utf8',
  )

  it('provides an early system fallback and an explicit dark-theme override', () => {
    expect(themeCss).toContain('@media (prefers-color-scheme: dark)')
    expect(themeCss).toContain(':root:not([data-theme])')
    expect(themeCss).toContain(":root[data-theme='dark']")
    expect(themeCss).toContain('color-scheme: dark')
  })

  it('loads theme styles and initializes browser chrome before the app mounts', () => {
    expect(nuxtConfig).toContain("'~/assets/css/theme.css'")
    expect(nuxtConfig).toContain("{ name: 'color-scheme', content: 'light dark' }")
    expect(nuxtConfig).toContain("window.localStorage.getItem('date-planner-theme')")
    expect(nuxtConfig).toContain("window.matchMedia('(prefers-color-scheme: dark)')")
    expect(nuxtConfig).toContain("tagPosition: 'bodyOpen'")
  })

  it('renders one global accessible toggle and persists manual choices', () => {
    expect(app.match(/<AppThemeToggle/g)).toHaveLength(1)
    expect(themeToggle).toContain('role="switch"')
    expect(themeToggle).toContain('aria-label="Тёмная тема"')
    expect(themeToggle).toContain(':aria-checked="isDark"')
    expect(themeToggle).not.toContain('aria-pressed')
    expect(colorThemeComposable).toContain('window.localStorage.setItem')
    expect(colorThemeComposable).toContain("addEventListener('change'")
    expect(colorThemeComposable).toContain("removeEventListener('change'")
  })

  it('themes the main surfaces, form controls, and semantic statuses', () => {
    expect(themeCss).toContain('html .invitation-card,')
    expect(themeCss).toContain('html .manage-card,')
    expect(themeCss).toContain('html .builder-stage,')
    expect(themeCss).toContain('html .form-field input,')
    expect(themeCss).toContain('html .builder-mobile-preview__screen-switcher button')
    expect(themeCss).toContain('html .plan-confirmation__summary .plan-summary-details > div')
    expect(themeCss).toContain('html .public-waiting-card,')
    expect(themeCss).toContain('html .public-declined-card,')
    expect(themeCss).toContain('html .response-save-status--saved,')
    expect(themeCss).toContain('html .form-status--error,')
  })

  it.each([
    [':root', 'text', 'page'],
    [':root', 'text-muted', 'surface'],
    [':root', 'placeholder', 'input'],
    [':root', 'focus', 'page'],
    [":root[data-theme='dark']", 'text', 'page'],
    [":root[data-theme='dark']", 'text-muted', 'surface'],
    [":root[data-theme='dark']", 'placeholder', 'input'],
    [":root[data-theme='dark']", 'focus', 'page'],
  ])(
    'keeps theme contrast at or above 4.5:1 for %s --theme-%s',
    (selector, foregroundToken, backgroundToken) => {
      const foreground = themeToken(themeCss, selector, foregroundToken)
      const background = themeToken(themeCss, selector, backgroundToken)

      expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5)
    },
  )
})
