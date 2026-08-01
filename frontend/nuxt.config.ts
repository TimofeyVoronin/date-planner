const personalPageHeaders = {
  'cache-control': 'private, no-store',
  'referrer-policy': 'no-referrer',
  'x-frame-options': 'DENY',
  'x-robots-tag': 'noindex, nofollow',
}

const themeInitializer = `(function () {
  try {
    var storedTheme = window.localStorage.getItem('date-planner-theme')
    var systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    var theme = storedTheme === 'dark' || (storedTheme !== 'light' && systemPrefersDark)
      ? 'dark'
      : 'light'
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    var themeColor = document.querySelector('meta[name="theme-color"]')
    if (themeColor) {
      themeColor.setAttribute('content', theme === 'dark' ? '#171116' : '#fff3f6')
    }
  }
  catch (error) {
    // CSS keeps the operating-system preference as a no-JavaScript fallback.
  }
})()`

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  modules: ['@nuxt/eslint'],
  css: [
    '~/assets/css/main.css',
    '~/assets/css/theme.css',
  ],
  devtools: { enabled: true },
  runtimeConfig: {
    public: {
      apiBaseUrl: 'http://localhost:8000',
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'ru' },
      title: 'Date Planner — приглашение на свидание',
      meta: [
        { name: 'description', content: 'Создай тёплое персональное приглашение на свидание за пару минут.' },
        { name: 'color-scheme', content: 'light dark' },
        { name: 'theme-color', content: '#fff3f6' },
      ],
      script: [
        {
          key: 'date-planner-theme-initializer',
          innerHTML: themeInitializer,
          tagPosition: 'bodyOpen',
        },
      ],
    },
  },
  routeRules: {
    '/invite/**': { headers: personalPageHeaders },
    '/manage/**': { headers: personalPageHeaders },
  },
  typescript: {
    strict: true,
  },
})
