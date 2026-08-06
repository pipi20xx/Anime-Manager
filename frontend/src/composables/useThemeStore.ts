import { defineStore } from 'pinia'
import { ref } from 'vue'

export type GlassTheme = 'classic' | 'acg' | 'liquid'

/** 主题循环顺序 */
const THEME_ORDER: GlassTheme[] = ['classic', 'liquid', 'acg']

export const useThemeStore = defineStore('theme', () => {
  const isDarkMode = ref(localStorage.getItem('theme_mode') === 'light' ? false : true)

  // 玻璃主题：'classic' = 经典实色（默认），'liquid' = 液态玻璃，'acg' = 二次元壁纸毛玻璃
  const glassTheme = ref<GlassTheme>(
    (localStorage.getItem('glass_theme') as GlassTheme) || 'classic'
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
    const idx = THEME_ORDER.indexOf(glassTheme.value)
    glassTheme.value = THEME_ORDER[(idx + 1) % THEME_ORDER.length]
    localStorage.setItem('glass_theme', glassTheme.value)
  }

  function setGlassTheme(theme: GlassTheme) {
    glassTheme.value = theme
    localStorage.setItem('glass_theme', theme)
  }

  return { isDarkMode, glassTheme, toggleDarkMode, setDarkMode, toggleGlassTheme, setGlassTheme }
})
