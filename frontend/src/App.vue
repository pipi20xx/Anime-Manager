<script setup lang="ts">
import { watch, onMounted } from 'vue'
import { useTheme } from 'vuetify'
import { useThemeStore, useSystemStore } from '@/stores'

const theme = useTheme()
const themeStore = useThemeStore()
const systemStore = useSystemStore()

// 同步深色/浅色主题（Vuetify 内部）
function applyTheme(isDark: boolean) {
  const themeName = isDark ? 'dark' : 'light'
  if (typeof theme.change === 'function') {
    theme.change(themeName)
  } else {
    theme.global.name.value = themeName
  }
}

// 在 <html> 上同步 dark/light class —— 给 CSS 变量用
// Vuetify 的 .v-theme--dark 只在 .v-application 上，body 读不到
function applyDarkClass(isDark: boolean) {
  const html = document.documentElement
  html.classList.toggle('glass-dark', isDark)
  html.classList.toggle('glass-light', !isDark)
}

// 同步玻璃主题 class 到 <html>
function applyGlassTheme(glassTheme: string) {
  const html = document.documentElement
  html.classList.remove('glass-theme-acg', 'glass-theme-liquid')
  html.classList.add(`glass-theme-${glassTheme}`)
}

applyTheme(themeStore.isDarkMode)
applyDarkClass(themeStore.isDarkMode)
applyGlassTheme(themeStore.glassTheme)

watch(() => themeStore.isDarkMode, (val) => {
  applyTheme(val)
  applyDarkClass(val)
})

watch(() => themeStore.glassTheme, (val) => {
  applyGlassTheme(val)
})

// 启动 WebSocket 连接
onMounted(() => {
  if (systemStore.isLoggedIn) {
    systemStore.connect()
  }
})
</script>

<template>
  <router-view />
</template>
