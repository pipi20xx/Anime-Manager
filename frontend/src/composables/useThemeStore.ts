import { defineStore } from 'pinia'
import { ref } from 'vue'

export type GlassTheme = 'acg' | 'liquid'

export const useThemeStore = defineStore('theme', () => {
  const isDarkMode = ref(localStorage.getItem('theme_mode') === 'light' ? false : true)

  // 玻璃主题：'acg' = 二次元壁纸毛玻璃，'liquid' = 液态玻璃（默认）
  const glassTheme = ref<GlassTheme>(
    (localStorage.getItem('glass_theme') as GlassTheme) || 'liquid'
  )

  function toggleDarkMode() {
    isDarkMode.value = !isDarkMode.value
    localStorage.setItem('theme_mode', isDarkMode.value ? 'dark' : 'light')
  }

  function setDarkMode(isDark: boolean) {
    isDarkMode.value = isDark
    localStorage.setItem('theme_mode', isDark ? 'dark' : 'light')
  }

  function toggleGlassTheme() {
    glassTheme.value = glassTheme.value === 'acg' ? 'liquid' : 'acg'
    localStorage.setItem('glass_theme', glassTheme.value)
  }

  function setGlassTheme(theme: GlassTheme) {
    glassTheme.value = theme
    localStorage.setItem('glass_theme', theme)
  }

  return { isDarkMode, glassTheme, toggleDarkMode, setDarkMode, toggleGlassTheme, setGlassTheme }
})
