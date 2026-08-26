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

  /** ACG 主题强制 dark 模式 */
  const isACGForcedDark = () => glassTheme.value === 'acg'

  function toggleDarkMode() {
    // ACG 主题下禁止切换到 light
    if (isACGForcedDark() && isDarkMode.value) return
    isDarkMode.value = !isDarkMode.value
    localStorage.setItem('theme_mode', isDarkMode.value ? 'dark' : 'light')
  }

  function setDarkMode(isDark: boolean) {
    // ACG 主题下禁止设置 light
    if (isACGForcedDark() && !isDark) return
    isDarkMode.value = isDark
    localStorage.setItem('theme_mode', isDark ? 'dark' : 'light')
  }

  function toggleGlassTheme() {
    const idx = THEME_ORDER.indexOf(glassTheme.value)
    setGlassTheme(THEME_ORDER[(idx + 1) % THEME_ORDER.length])
  }

  function setGlassTheme(theme: GlassTheme) {
    // 切到 ACG 时强制 dark
    if (theme === 'acg' && !isDarkMode.value) {
      isDarkMode.value = true
      localStorage.setItem('theme_mode', 'dark')
    }

    glassTheme.value = theme
    localStorage.setItem('glass_theme', theme)
  }

  /**
   * 同时设置主题风格和明暗模式 —— 供主题菜单一次性选择组合主题。
   * ACG 主题会自动强制 dark。
   */
  function setTheme(theme: GlassTheme, isDark: boolean) {
    const effectiveDark = theme === 'acg' ? true : isDark
    isDarkMode.value = effectiveDark
    glassTheme.value = theme
    localStorage.setItem('theme_mode', effectiveDark ? 'dark' : 'light')
    localStorage.setItem('glass_theme', theme)
  }

  // 初始化：如果启动时已经是 ACG 主题但不是 dark，强制切到 dark
  if (isACGForcedDark() && !isDarkMode.value) {
    isDarkMode.value = true
    localStorage.setItem('theme_mode', 'dark')
  }

  return { isDarkMode, glassTheme, toggleDarkMode, setDarkMode, toggleGlassTheme, setGlassTheme, setTheme }
})
