/**
 * Vuetify 插件配置
 *
 * 默认主题：经典实色（classic）
 * - 亮色：纯白底 + 紫色主强调色 #a855f7
 * - 暗色：纯黑底 #121212 + 紫色主强调色 #a855f7
 * - ACG / 液态玻璃主题通过 CSS 覆盖实现
 * - 图标：全部使用 MDI (@mdi/js)
 */
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

import 'vuetify/styles'

// 亮色主题 — 经典实色
const lightTheme = {
  dark: false,
  colors: {
    background: '#FFFFFF',  // 页面背景
    surface: '#FFFFFF',      // 卡片/面板背景
    'surface-variant': '#F5F5F5',
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

// 暗色主题 — 经典实色（纯黑底）
// 规则：强调色（primary/secondary/accent/error/info/success/warning）
//       与 light 完全一致，只改 background/surface 明暗值
const darkTheme = {
  dark: true,
  colors: {
    background: '#121212',  // 页面背景（纯黑）
    surface: '#1E1E1E',      // 卡片/面板背景
    'surface-variant': '#2C2C2C',
    'on-surface-variant': '#BFC2CE',
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
