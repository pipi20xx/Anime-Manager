import { GlobalThemeOverrides } from 'naive-ui'

export type ThemeType = 'modern' | 'round' | 'purple'

export const themeOptions = [
  { label: '现代极客 (Modern)', key: 'modern' },
  { label: '圆润糖果 (Soft)', key: 'round' },
  { label: '暗夜紫韵 (Purple)', key: 'purple' }
]

// 1. 现代极客 (Modern) - 科技感/清新
export const modernOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#63e2b7',
    primaryColorHover: '#7fe7c4',
    primaryColorPressed: '#50ce9e',
    primaryColorSuppl: '#2a947d',
    infoColor: '#70c0e8',
    warningColor: '#f2c97d',
    errorColor: '#e88080',
    successColor: '#a0d911',
    borderRadius: '6px',
    cardColor: '#1e1e24',
    modalColor: '#25252b',
    popoverColor: '#25252b',
    textColorBase: '#ffffff',
    textColor1: '#ffffff',
    textColor2: 'rgba(255, 255, 255, 0.9)',
    textColor3: 'rgba(255, 255, 255, 0.7)',
    bodyColor: '#0a1a14',
    fontSize: '14px'
  },
  Card: { borderRadius: '10px' },
  Button: { borderRadiusMedium: '6px', fontWeight: '600' },
  Input: { borderRadius: '6px' },
  Select: { borderRadius: '6px' },
  Tag: { borderRadius: '4px' },
  DataTable: {
    thColor: 'rgba(255, 255, 255, 0.06)',
    tdColor: 'transparent',
    tdColorHover: 'rgba(255, 255, 255, 0.08)',
    thColorModal: 'rgba(255, 255, 255, 0.06)',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(255, 255, 255, 0.08)',
    thColorPopover: 'rgba(255, 255, 255, 0.06)',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(255, 255, 255, 0.08)'
  }
}

// 2. 圆润糖果 (Soft) - 可爱/动漫风
export const roundOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#ff9cb3', // 樱花粉
    primaryColorHover: '#ffc1d0',
    primaryColorPressed: '#f06292',
    primaryColorSuppl: '#ff80ab',
    infoColor: '#81d4fa',
    warningColor: '#ffe082',
    errorColor: '#ef9a9a',
    successColor: '#c5e1a5',
    borderRadius: '16px',
    cardColor: '#2b262d',
    modalColor: '#322c35',
    popoverColor: '#322c35',
    bodyColor: '#2a0f18',
    fontFamily: '"Quicksand", "Varela Round", "Nunito", system-ui, sans-serif',
    fontSize: '14px'
  },
  Card: { borderRadius: '24px', borderColor: 'rgba(255, 156, 179, 0.15)' },
  Button: { borderRadiusMedium: '50px', fontWeight: '700' },
  Input: { borderRadius: '20px' },
  Select: { borderRadius: '20px' },
  Tag: { borderRadius: '50px' },
  Message: { borderRadius: '16px' },
  Dialog: { borderRadius: '24px' },
  DataTable: {
    thColor: 'rgba(255, 255, 255, 0.08)',
    tdColor: 'transparent',
    tdColorHover: 'rgba(255, 255, 255, 0.12)',
    thColorModal: 'rgba(255, 255, 255, 0.08)',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(255, 255, 255, 0.12)',
    thColorPopover: 'rgba(255, 255, 255, 0.08)',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(255, 255, 255, 0.12)'
  }
}

// 3. 暗夜紫韵 (Purple) - 霓虹/深邃
export const purpleOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#bb86fc', // 霓虹紫
    primaryColorHover: '#d1a8ff',
    primaryColorPressed: '#995df0',
    primaryColorSuppl: '#7c4dff',
    infoColor: '#03dac6',
    warningColor: '#ffb74d',
    errorColor: '#cf6679',
    successColor: '#81c784',
    borderRadius: '10px',
    cardColor: '#120818',
    modalColor: '#180a20',
    popoverColor: '#180a20',
    bodyColor: '#1a0528',
    textColorBase: '#e0e0e0'
  },
  Card: { borderRadius: '14px', borderColor: 'rgba(187, 134, 252, 0.15)' },
  Button: { borderRadiusMedium: '10px', fontWeight: '600' },
  Input: { borderRadius: '10px' },
  Select: { borderRadius: '10px' },
  Tag: { borderRadius: '6px' },
  DataTable: {
    thColor: 'rgba(187, 134, 252, 0.06)',
    tdColor: 'transparent',
    tdColorHover: 'rgba(187, 134, 252, 0.1)',
    thColorModal: 'rgba(187, 134, 252, 0.06)',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(187, 134, 252, 0.1)',
    thColorPopover: 'rgba(187, 134, 252, 0.06)',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(187, 134, 252, 0.1)'
  }
}
