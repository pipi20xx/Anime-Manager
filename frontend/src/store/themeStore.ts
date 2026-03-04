import { ref, computed, watch } from 'vue'
import { modernOverrides, roundOverrides, purpleOverrides, ThemeType } from '../themes'

export const currentThemeType = ref<ThemeType>((localStorage.getItem('apm_theme_type') as ThemeType) || 'modern')

watch(currentThemeType, (val) => localStorage.setItem('apm_theme_type', val))

export const themeOverrides = computed(() => {
  const current = currentThemeType.value
  switch (current) {
    case 'round': return roundOverrides
    case 'purple': return purpleOverrides
    default: return modernOverrides
  }
})

export const logoColor = computed(() => {
  switch (currentThemeType.value) {
    case 'round': return '#ff9cb3'
    case 'purple': return '#bb86fc'
    default: return '#63e2b7'
  }
})

// Update CSS variables
const updateCssVariables = () => {
  if (typeof document === 'undefined') return
  
  const current = currentThemeType.value
  const root = document.documentElement
  const theme = current === 'round' ? roundOverrides : (current === 'purple' ? purpleOverrides : modernOverrides)
  const common = theme.common!
  
  // 同步底层视觉底座
  root.style.setProperty('--app-bg-color', common.bodyColor!)
  root.style.setProperty('--sidebar-bg-color', common.cardColor!)
  
  // 统一质感变量
  if (current === 'round') {
    root.style.setProperty('--app-surface-card', 'rgba(255, 255, 255, 0.08)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.2)') 
    root.style.setProperty('--app-border-light', 'rgba(255, 156, 179, 0.2)') 
    root.style.setProperty('--card-border-radius', '24px')
    root.style.setProperty('--button-border-radius', '20px')
    root.style.setProperty('--font-family-base', '"Quicksand", "Nunito", sans-serif')
  } else if (current === 'purple') {
    root.style.setProperty('--app-surface-card', 'rgba(187, 134, 252, 0.06)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.4)')
    root.style.setProperty('--app-border-light', 'rgba(187, 134, 252, 0.25)')
    root.style.setProperty('--card-border-radius', '14px')
    root.style.setProperty('--button-border-radius', '10px')
    root.style.setProperty('--font-family-base', 'Inter, sans-serif')
  } else {
    root.style.setProperty('--app-surface-card', 'rgba(255, 255, 255, 0.06)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.3)')
    root.style.setProperty('--app-border-light', 'rgba(255, 255, 255, 0.12)')
    root.style.setProperty('--card-border-radius', '10px')
    root.style.setProperty('--button-border-radius', '6px')
    root.style.setProperty('--font-family-base', 'Inter, sans-serif')
  }
}

// Initial call and watch
updateCssVariables()
watch(currentThemeType, updateCssVariables)
