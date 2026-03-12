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
  root.style.setProperty('--app-bg-color', current === 'round' ? '#2a0f18' : (current === 'purple' ? '#1a0528' : '#0a1a14'))
  root.style.setProperty('--sidebar-bg-color', current === 'round' ? '#3a1e28' : (current === 'purple' ? '#280a38' : '#0e2a1e'))
  
  // 统一质感变量
  if (current === 'round') {
    root.style.setProperty('--app-surface-card', 'rgba(255, 255, 255, 0.08)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.2)') 
    root.style.setProperty('--app-border-light', 'rgba(255, 156, 179, 0.2)') 
    root.style.setProperty('--card-border-radius', '24px')
    root.style.setProperty('--button-border-radius', '20px')
    root.style.setProperty('--font-family-base', '"Quicksand", "Nunito", sans-serif')
    
    // 更新主题相关的颜色变量
    root.style.setProperty('--text-primary', common.textColor1 || '#ffffff')
    root.style.setProperty('--text-secondary', common.textColor2 || 'rgba(255, 255, 255, 0.9)')
    root.style.setProperty('--text-tertiary', common.textColor3 || 'rgba(255, 255, 255, 0.7)')
    root.style.setProperty('--text-muted', 'rgba(255, 255, 255, 0.5)')
    root.style.setProperty('--text-disabled', 'rgba(255, 255, 255, 0.3)')
    root.style.setProperty('--text-hint', 'rgba(255, 255, 255, 0.4)')
    
    root.style.setProperty('--bg-primary', '#2a0f18')
    root.style.setProperty('--bg-secondary', '#3a1e28')
    root.style.setProperty('--bg-tertiary', '#4a2e38')
    root.style.setProperty('--bg-elevated', 'rgba(255, 156, 179, 0.08)')
    root.style.setProperty('--bg-surface', 'rgba(255, 255, 255, 0.08)')
    root.style.setProperty('--bg-surface-hover', 'rgba(255, 255, 255, 0.12)')
    root.style.setProperty('--bg-surface-active', 'rgba(255, 255, 255, 0.16)')
    root.style.setProperty('--bg-overlay', 'rgba(0, 0, 0, 0.6)')
    
    root.style.setProperty('--border-light', 'rgba(255, 156, 179, 0.2)')
    root.style.setProperty('--border-medium', 'rgba(255, 156, 179, 0.3)')
    root.style.setProperty('--border-heavy', 'rgba(255, 156, 179, 0.4)')
    root.style.setProperty('--border-dashed', 'rgba(255, 156, 179, 0.25)')
    
    root.style.setProperty('--color-success', common.successColor || '#a0d911')
    root.style.setProperty('--color-warning', common.warningColor || '#f2c97d')
    root.style.setProperty('--color-error', common.errorColor || '#e88080')
    root.style.setProperty('--color-info', common.infoColor || '#70c0e8')
    
    root.style.setProperty('--color-success-bg', 'rgba(160, 217, 17, 0.1)')
    root.style.setProperty('--color-warning-bg', 'rgba(242, 201, 125, 0.1)')
    root.style.setProperty('--color-error-bg', 'rgba(232, 128, 128, 0.1)')
    root.style.setProperty('--color-info-bg', 'rgba(112, 192, 232, 0.1)')
    
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
    
  } else if (current === 'purple') {
    root.style.setProperty('--app-surface-card', 'rgba(187, 134, 252, 0.06)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.4)')
    root.style.setProperty('--app-border-light', 'rgba(187, 134, 252, 0.25)')
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
    
    root.style.setProperty('--bg-primary', '#1a0528')
    root.style.setProperty('--bg-secondary', '#280a38')
    root.style.setProperty('--bg-tertiary', '#380f48')
    root.style.setProperty('--bg-elevated', 'rgba(187, 134, 252, 0.06)')
    root.style.setProperty('--bg-surface', 'rgba(187, 134, 252, 0.06)')
    root.style.setProperty('--bg-surface-hover', 'rgba(187, 134, 252, 0.1)')
    root.style.setProperty('--bg-surface-active', 'rgba(187, 134, 252, 0.15)')
    root.style.setProperty('--bg-overlay', 'rgba(0, 0, 0, 0.6)')
    
    root.style.setProperty('--border-light', 'rgba(187, 134, 252, 0.25)')
    root.style.setProperty('--border-medium', 'rgba(187, 134, 252, 0.35)')
    root.style.setProperty('--border-heavy', 'rgba(187, 134, 252, 0.45)')
    root.style.setProperty('--border-dashed', 'rgba(187, 134, 252, 0.3)')
    
    root.style.setProperty('--color-success', common.successColor || '#81c784')
    root.style.setProperty('--color-warning', common.warningColor || '#ffb74d')
    root.style.setProperty('--color-error', common.errorColor || '#cf6679')
    root.style.setProperty('--color-info', common.infoColor || '#03dac6')
    
    root.style.setProperty('--color-success-bg', 'rgba(129, 199, 132, 0.1)')
    root.style.setProperty('--color-warning-bg', 'rgba(255, 183, 77, 0.1)')
    root.style.setProperty('--color-error-bg', 'rgba(207, 102, 121, 0.1)')
    root.style.setProperty('--color-info-bg', 'rgba(3, 218, 198, 0.1)')
    
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
    
  } else {
    root.style.setProperty('--app-surface-card', 'rgba(255, 255, 255, 0.06)')
    root.style.setProperty('--app-surface-inner', 'rgba(0, 0, 0, 0.3)')
    root.style.setProperty('--app-border-light', 'rgba(255, 255, 255, 0.12)')
    root.style.setProperty('--card-border-radius', '10px')
    root.style.setProperty('--button-border-radius', '6px')
    root.style.setProperty('--font-family-base', 'Inter, sans-serif')
    
    // 更新主题相关的颜色变量
    root.style.setProperty('--text-primary', common.textColor1 || '#ffffff')
    root.style.setProperty('--text-secondary', common.textColor2 || 'rgba(255, 255, 255, 0.9)')
    root.style.setProperty('--text-tertiary', common.textColor3 || 'rgba(255, 255, 255, 0.7)')
    root.style.setProperty('--text-muted', 'rgba(255, 255, 255, 0.5)')
    root.style.setProperty('--text-disabled', 'rgba(255, 255, 255, 0.3)')
    root.style.setProperty('--text-hint', 'rgba(255, 255, 255, 0.4)')
    
    root.style.setProperty('--bg-primary', '#0a1a14')
    root.style.setProperty('--bg-secondary', '#0e2a1e')
    root.style.setProperty('--bg-tertiary', '#1e3a2e')
    root.style.setProperty('--bg-elevated', 'rgba(99, 226, 183, 0.06)')
    root.style.setProperty('--bg-surface', 'rgba(255, 255, 255, 0.06)')
    root.style.setProperty('--bg-surface-hover', 'rgba(255, 255, 255, 0.1)')
    root.style.setProperty('--bg-surface-active', 'rgba(255, 255, 255, 0.15)')
    root.style.setProperty('--bg-overlay', 'rgba(0, 0, 0, 0.6)')
    
    root.style.setProperty('--border-light', 'rgba(255, 255, 255, 0.12)')
    root.style.setProperty('--border-medium', 'rgba(255, 255, 255, 0.2)')
    root.style.setProperty('--border-heavy', 'rgba(255, 255, 255, 0.3)')
    root.style.setProperty('--border-dashed', 'rgba(255, 255, 255, 0.15)')
    
    root.style.setProperty('--color-success', common.successColor || '#a0d911')
    root.style.setProperty('--color-warning', common.warningColor || '#f2c97d')
    root.style.setProperty('--color-error', common.errorColor || '#e88080')
    root.style.setProperty('--color-info', common.infoColor || '#70c0e8')
    
    root.style.setProperty('--color-success-bg', 'rgba(160, 217, 17, 0.1)')
    root.style.setProperty('--color-warning-bg', 'rgba(242, 201, 125, 0.1)')
    root.style.setProperty('--color-error-bg', 'rgba(232, 128, 128, 0.1)')
    root.style.setProperty('--color-info-bg', 'rgba(112, 192, 232, 0.1)')
    
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
}

// Initial call and watch
updateCssVariables()
watch(currentThemeType, updateCssVariables)
