import { GlobalThemeOverrides } from 'naive-ui'

export type ThemeType = 'purple'

export const themeOptions = [
  { label: '暗夜紫韵 (Purple)', key: 'purple' }
]

// 暗夜紫韵 (Purple) - 霓虹/深邃
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
    cardColor: 'transparent',
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
    thColor: 'transparent',
    tdColor: 'transparent',
    tdColorHover: 'rgba(187, 134, 252, 0.1)',
    thColorModal: 'transparent',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(187, 134, 252, 0.1)',
    thColorPopover: 'transparent',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(187, 134, 252, 0.1)'
  }
}
