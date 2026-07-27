<script setup lang="ts">
import { watch, onMounted } from 'vue'
import { useTheme } from 'vuetify'
import { useThemeStore, useSystemStore } from '@/stores'

const theme = useTheme()
const themeStore = useThemeStore()
const systemStore = useSystemStore()

// 同步主题
function applyTheme(isDark: boolean) {
  const themeName = isDark ? 'dark' : 'light'
  if (typeof theme.change === 'function') {
    theme.change(themeName)
  } else {
    theme.global.name.value = themeName
  }
}

applyTheme(themeStore.isDarkMode)

watch(() => themeStore.isDarkMode, (val) => {
  applyTheme(val)
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
