import { ref, computed, watch } from 'vue'
import { themeConfigs, themeOverridesMap, ThemeType } from '../themes'

export const currentThemeType = ref<ThemeType>((localStorage.getItem('apm_theme_type') as ThemeType) || 'purple')

watch(currentThemeType, (val) => localStorage.setItem('apm_theme_type', val))

export const themeOverrides = computed(() => {
  return themeOverridesMap[currentThemeType.value]
})

export const logoColor = computed(() => {
  return themeConfigs[currentThemeType.value].logoColor
})

export const currentThemeConfig = computed(() => {
  return themeConfigs[currentThemeType.value]
})

export const docsTheme = computed(() => {
  return themeConfigs[currentThemeType.value].docsTheme
})

// Update CSS variables
const updateCssVariables = () => {
  if (typeof document === 'undefined') return
  
  const root = document.documentElement
  const config = themeConfigs[currentThemeType.value]
  const theme = themeOverridesMap[currentThemeType.value]
  const common = theme.common!
  
  // 同步底层视觉底座 - 统一背景色变量
  root.style.setProperty('--app-unified-bg', config.bgPrimary)
  root.style.setProperty('--app-bg-color', 'var(--app-unified-bg)')
  root.style.setProperty('--sidebar-bg-color', 'var(--app-unified-bg)')
  
  // 统一质感变量
  root.style.setProperty('--app-surface-card', `rgba(${config.surfaceColor}, 0.22)`)
  root.style.setProperty('--app-surface-inner', `rgba(${config.surfaceColor}, 0.12)`)
  root.style.setProperty('--app-border-light', `rgba(${config.surfaceColor}, 0.25)`)
  root.style.setProperty('--app-modal-bg', config.modalBg)
  root.style.setProperty('--app-dropdown-bg', config.dropdownBg)
  root.style.setProperty('--card-border-radius', '14px')
  root.style.setProperty('--button-border-radius', '10px')
  root.style.setProperty('--font-family-base', 'Inter, sans-serif')
  
  // 更新主题相关的颜色变量
  root.style.setProperty('--text-primary', common.textColor1 || '#ffffff')
  root.style.setProperty('--text-secondary', common.textColor2 || 'rgba(255, 255, 255, 0.9)')
  root.style.setProperty('--text-tertiary', common.textColor3 || 'rgba(255, 255, 255, 0.7)')
  root.style.setProperty('--text-muted', 'rgba(255, 255, 255, 0.5)')
  root.style.setProperty('--text-disabled', 'rgba(255, 255, 255, 0.3)')
  root.style.setProperty('--text-hint', 'rgba(255, 255, 255, 0.4)')
  
  root.style.setProperty('--bg-primary', config.bgPrimary)
  root.style.setProperty('--bg-secondary', config.bgSecondary)
  root.style.setProperty('--bg-tertiary', config.bgTertiary)
  root.style.setProperty('--bg-elevated', `rgba(${config.surfaceColor}, 0.12)`)
  root.style.setProperty('--bg-surface', `rgba(${config.surfaceColor}, 0.12)`)
  root.style.setProperty('--bg-surface-hover', `rgba(${config.surfaceColor}, 0.18)`)
  root.style.setProperty('--bg-surface-active', `rgba(${config.surfaceColor}, 0.25)`)
  root.style.setProperty('--bg-overlay', 'rgba(0, 0, 0, 0.6)')
  
  root.style.setProperty('--border-light', `rgba(${config.surfaceColor}, 0.25)`)
  root.style.setProperty('--border-medium', `rgba(${config.surfaceColor}, 0.35)`)
  root.style.setProperty('--border-heavy', `rgba(${config.surfaceColor}, 0.45)`)
  root.style.setProperty('--border-dashed', `rgba(${config.surfaceColor}, 0.3)`)
  
  root.style.setProperty('--color-success', common.successColor || '#81c784')
  root.style.setProperty('--color-warning', common.warningColor || '#ffb74d')
  root.style.setProperty('--color-error', common.errorColor || '#cf6679')
  root.style.setProperty('--color-info', common.infoColor || '#03dac6')
  
  root.style.setProperty('--color-success-bg', 'rgba(129, 199, 132, 0.1)')
  root.style.setProperty('--color-warning-bg', 'rgba(255, 183, 77, 0.1)')
  root.style.setProperty('--color-error-bg', 'rgba(207, 102, 121, 0.1)')
  root.style.setProperty('--color-info-bg', 'rgba(3, 218, 198, 0.1)')
  
  root.style.setProperty('--code-bg', `rgba(${config.surfaceColor}, 0.12)`)
  
  root.style.setProperty('--opacity-disabled', '0.3')
  root.style.setProperty('--opacity-muted', '0.5')
  root.style.setProperty('--opacity-secondary', '0.7')
  root.style.setProperty('--opacity-tertiary', '0.85')
  root.style.setProperty('--opacity-primary', '0.95')
  root.style.setProperty('--opacity-full', '1')
  
  root.style.setProperty('--shadow-light', 'rgba(0, 0, 0, 0.1)')
  root.style.setProperty('--shadow-medium', 'rgba(0, 0, 0, 0.3)')
  root.style.setProperty('--shadow-heavy', 'rgba(0, 0, 0, 0.5)')
  root.style.setProperty('--shadow-xheavy', 'rgba(0, 0, 0, 0.6)')
  
  root.style.setProperty('--border-light-alpha', '0.05')
  root.style.setProperty('--border-medium-alpha', '0.1')
  root.style.setProperty('--border-heavy-alpha', '0.2')
}

// Initial call and watch
updateCssVariables()
watch(currentThemeType, updateCssVariables)
