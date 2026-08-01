export const APP_THEME_STORAGE_KEY = 'date-planner-theme'

export const APP_THEME_COLORS = {
  dark: '#171116',
  light: '#fff3f6',
} as const

export type AppTheme = keyof typeof APP_THEME_COLORS

export function isAppTheme(value: unknown): value is AppTheme {
  return value === 'light' || value === 'dark'
}

export function resolveAppTheme(
  storedTheme: unknown,
  systemPrefersDark: boolean,
): AppTheme {
  if (isAppTheme(storedTheme)) {
    return storedTheme
  }

  return systemPrefersDark ? 'dark' : 'light'
}

export function getOppositeAppTheme(theme: AppTheme): AppTheme {
  return theme === 'dark' ? 'light' : 'dark'
}
