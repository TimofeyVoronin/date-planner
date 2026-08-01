import { onMounted, onUnmounted, readonly } from 'vue'
import {
  APP_THEME_COLORS,
  APP_THEME_STORAGE_KEY,
  getOppositeAppTheme,
  isAppTheme,
  resolveAppTheme,
  type AppTheme,
} from '../utils/theme'

function applyThemeToDocument(theme: AppTheme): void {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme

  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  themeColor?.setAttribute('content', APP_THEME_COLORS[theme])
}

export function useColorTheme() {
  const theme = useState<AppTheme>('app-color-theme', () => 'light')
  const hasExplicitPreference = useState(
    'app-color-theme-has-explicit-preference',
    () => false,
  )
  let colorSchemeQuery: MediaQueryList | null = null

  function setTheme(nextTheme: AppTheme): void {
    theme.value = nextTheme
    applyThemeToDocument(nextTheme)
  }

  function handleSystemThemeChange(event: MediaQueryListEvent): void {
    if (!hasExplicitPreference.value) {
      setTheme(event.matches ? 'dark' : 'light')
    }
  }

  function toggleTheme(): void {
    const nextTheme = getOppositeAppTheme(theme.value)

    hasExplicitPreference.value = true
    try {
      window.localStorage.setItem(APP_THEME_STORAGE_KEY, nextTheme)
    }
    catch {
      // Storage can be unavailable in privacy modes; the current page still changes theme.
    }
    setTheme(nextTheme)
  }

  onMounted(() => {
    colorSchemeQuery = window.matchMedia('(prefers-color-scheme: dark)')

    let storedTheme: AppTheme | null = null
    try {
      const storedValue = window.localStorage.getItem(APP_THEME_STORAGE_KEY)
      storedTheme = isAppTheme(storedValue) ? storedValue : null
    }
    catch {
      // Fall back to the operating-system preference when storage is unavailable.
    }

    hasExplicitPreference.value = storedTheme !== null
    setTheme(resolveAppTheme(storedTheme, colorSchemeQuery.matches))
    colorSchemeQuery.addEventListener('change', handleSystemThemeChange)
  })

  onUnmounted(() => {
    colorSchemeQuery?.removeEventListener('change', handleSystemThemeChange)
  })

  return {
    theme: readonly(theme),
    toggleTheme,
  }
}
