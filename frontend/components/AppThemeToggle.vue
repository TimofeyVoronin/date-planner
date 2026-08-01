<script setup lang="ts">
import { computed } from 'vue'
import { useColorTheme } from '../composables/useColorTheme'

const { theme, toggleTheme } = useColorTheme()
const isDark = computed(() => theme.value === 'dark')
const actionLabel = computed(() => (
  isDark.value ? 'Включить светлую тему' : 'Включить тёмную тему'
))
</script>

<template>
  <button
    class="app-theme-toggle"
    type="button"
    role="switch"
    aria-label="Тёмная тема"
    :aria-checked="isDark"
    :title="actionLabel"
    @click="toggleTheme"
  >
    <span class="app-theme-toggle__icon" aria-hidden="true">
      {{ isDark ? '☾' : '☀' }}
    </span>
    <span class="app-theme-toggle__label">
      {{ isDark ? 'Тёмная' : 'Светлая' }}
    </span>
  </button>
</template>
