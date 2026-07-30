/**
 * Vuetify 插件配置
 *
 * 设计规范：Apple Liquid Glass — 流动玻璃设计语言
 * - 深色渐变背景，多层玻璃面板半透明 + 高斯模糊 + 饱和度增强
 * - 青色 #4ecdc4 为核心辅助色（霓虹描边）
 * - 品红 #ff2d92 为渐变填充色
 * - 紫色 #a855f7 为主强调色
 * - 图标：全部使用 MDI (@mdi/js)
 */
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

import 'vuetify/styles'

// 亮色主题 — 极简实色
const lightTheme = {
  dark: false,
  colors: {
    background: '#F5F5FA',  // 页面背景
    surface: '#FFFFFF',      // 卡片/面板背景
    'surface-variant': '#F8F8FC',
    'on-surface-variant': '#64748B',
    primary: '#a855f7',
    'primary-darken-1': '#9333EA',
    secondary: '#6b7280',
    'secondary-darken-1': '#4b5563',
    accent: '#4ecdc4',
    error: '#ef4444',
    info: '#1565C0',
    success: '#1B8134',
    warning: '#E65100',
  },
}

// 暗色主题 — 极简实色（background 与 surface 统一，消除色差）
const darkTheme = {
  dark: true,
  colors: {
    background: '#1a1a3e',  // 页面背景（与导航栏/顶栏/TAB栏统一）
    surface: '#1a1a3e',      // 卡片/面板背景
    'surface-variant': '#141432',
    'on-surface-variant': '#BFC2CE',
    primary: '#a855f7',
    'primary-darken-1': '#9333EA',
    secondary: '#9ca3af',
    'secondary-darken-1': '#6b7280',
    accent: '#4ecdc4',
    error: '#ff6b6b',
    info: '#4ecdc4',
    success: '#4caf50',
    warning: '#FFB74D',
  },
}

export default createVuetify({
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
  theme: {
    defaultTheme: localStorage.getItem('theme_mode') === 'light' ? 'light' : 'dark',
    themes: {
      light: lightTheme,
      dark: darkTheme,
    },
  },
  defaults: {
    VCard: {
      rounded: 'xl',
    },
    VBtn: {
      rounded: 'xl',
      variant: 'tonal',
      density: 'default',
    },
    VChip: {
      rounded: 'lg',
      label: true,
    },
    VTextField: {
      variant: 'outlined',
      density: 'compact',
      rounded: 'xl',
      hideDetails: 'auto',
    },
    VSelect: {
      variant: 'outlined',
      density: 'compact',
      rounded: 'xl',
      hideDetails: 'auto',
    },
    VTextarea: {
      variant: 'outlined',
      density: 'compact',
      rounded: 'xl',
      hideDetails: 'auto',
    },
    VAutocomplete: {
      variant: 'outlined',
      density: 'compact',
      rounded: 'xl',
      hideDetails: 'auto',
    },
    VCombobox: {
      variant: 'outlined',
      density: 'compact',
      rounded: 'xl',
      hideDetails: 'auto',
    },
  },
})
