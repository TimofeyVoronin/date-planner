export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  modules: ['@nuxt/eslint'],
  css: ['~/assets/css/main.css'],
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
        { name: 'theme-color', content: '#fff3f6' },
      ],
    },
  },
  typescript: {
    strict: true,
  },
})
