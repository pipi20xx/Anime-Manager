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
  Select: { 
    borderRadius: '10px',
    peers: {
      InternalSelectMenu: {
        color: 'var(--app-dropdown-bg)'
      }
    }
  },
  Dropdown: {
    peers: {
      InternalDropdownMenu: {
        color: 'var(--app-dropdown-bg)'
      }
    }
  },
  Tag: { borderRadius: '6px' },
  Popconfirm: {
    color: 'var(--app-modal-bg)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    arrowColor: 'var(--app-modal-bg)'
  },
  Popover: {
    color: 'var(--app-modal-bg)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    arrowColor: 'var(--app-modal-bg)'
  },
  LayoutSider: {
    color: 'var(--app-surface-card)',
    borderColor: 'var(--app-border-light)',
    toggleBarColor: 'var(--app-surface-card)',
    toggleBarColorHover: 'var(--bg-surface-hover)',
    toggleIconColor: 'var(--n-text-color-2)',
    toggleIconColorHover: 'var(--n-text-color-1)'
  },
  DataTable: {
    thColor: 'transparent',
    tdColor: 'transparent',
    tdColorHover: 'rgba(187, 134, 252, 0.1)',
    thColorModal: 'transparent',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(187, 134, 252, 0.1)',
    thColorPopover: 'transparent',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(187, 134, 252, 0.1)',
    borderColor: 'rgba(187, 134, 252, 0.35)',
    borderColorModal: 'rgba(187, 134, 252, 0.35)',
    borderColorPopover: 'rgba(187, 134, 252, 0.35)'
  }
}
