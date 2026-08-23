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

  // 记住用户在非 ACG 主题时的明暗偏好，切离 ACG 时恢复
  const savedDarkMode = ref<boolean | null>(null)

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
    // 切离 ACG 时恢复用户之前的明暗偏好
    if (glassTheme.value === 'acg' && theme !== 'acg') {
      if (savedDarkMode.value !== null) {
        isDarkMode.value = savedDarkMode.value
        localStorage.setItem('theme_mode', savedDarkMode.value ? 'dark' : 'light')
        savedDarkMode.value = null
      }
    }

    // 切到 ACG 时保存当前偏好并强制 dark
    if (theme === 'acg' && glassTheme.value !== 'acg') {
      savedDarkMode.value = isDarkMode.value
      if (!isDarkMode.value) {
        isDarkMode.value = true
        localStorage.setItem('theme_mode', 'dark')
      }
    }

    glassTheme.value = theme
    localStorage.setItem('glass_theme', theme)
  }

  // 初始化：如果启动时已经是 ACG 主题但不是 dark，强制切到 dark
  if (isACGForcedDark() && !isDarkMode.value) {
    isDarkMode.value = true
    localStorage.setItem('theme_mode', 'dark')
  }

  return { isDarkMode, glassTheme, toggleDarkMode, setDarkMode, toggleGlassTheme, setGlassTheme }
})
