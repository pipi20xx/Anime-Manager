import { GlobalThemeOverrides } from 'naive-ui'

export type ThemeType = 'purple'
export type ThemeMode = 'dark' | 'light'

export interface ThemeConfig {
  name: string
  primaryColor: string
  primaryColorHover: string
  primaryColorPressed: string
  primaryColorSuppl: string
  logoColor: string
  bgPrimary: string
  bgSecondary: string
  bgTertiary: string
  surfaceColor: string
  modalBg: string
  dropdownBg: string
  docsTheme: string
}

// Color mix opacity levels
export const colorMixOpacity = {
  subtle: '96%',    // Very light tint
  light: '90%',     // Light tint
  medium: '85%',    // Medium tint
  strong: '70%',    // Strong tint
  half: '50%'       // Half transparent
} as const

// Generate color-mix CSS variable value
export function generateColorMix(color: string, opacity: string): string {
  return `color-mix(in srgb, ${color}, transparent ${opacity})`
}

// 暗色模式背景色
const darkBgColors = {
  bgPrimary: '#1e1e2e',
  bgSecondary: '#242429',
  bgTertiary: '#2e2e33',
  surfaceColor: '255, 255, 255',
  modalBg: 'rgba(30, 30, 46, 0.95)',
  dropdownBg: 'rgba(30, 30, 46, 0.98)'
}

// 亮色模式背景色
const lightBgColors = {
  bgPrimary: '#ffffff',
  bgSecondary: '#f5f5f5',
  bgTertiary: '#eeeeee',
  surfaceColor: '0, 0, 0',
  modalBg: 'rgba(255, 255, 255, 0.98)',
  dropdownBg: 'rgba(255, 255, 255, 0.98)'
}

// 电光蓝主题配置（暗色）
const purpleDarkConfig: ThemeConfig = {
  name: '暗夜蓝韵',
  primaryColor: '#3B82F6',
  primaryColorHover: '#60A5FA',
  primaryColorPressed: '#2563EB',
  primaryColorSuppl: '#1D4ED8',
  logoColor: '#3B82F6',
  bgPrimary: darkBgColors.bgPrimary,
  bgSecondary: darkBgColors.bgSecondary,
  bgTertiary: darkBgColors.bgTertiary,
  surfaceColor: darkBgColors.surfaceColor,
  modalBg: darkBgColors.modalBg,
  dropdownBg: darkBgColors.dropdownBg,
  docsTheme: 'blue'
}

// 电光蓝主题配置（亮色）
const purpleLightConfig: ThemeConfig = {
  name: '白昼蓝韵',
  primaryColor: '#3B82F6',
  primaryColorHover: '#60A5FA',
  primaryColorPressed: '#2563EB',
  primaryColorSuppl: '#1D4ED8',
  logoColor: '#3B82F6',
  bgPrimary: lightBgColors.bgPrimary,
  bgSecondary: lightBgColors.bgSecondary,
  bgTertiary: lightBgColors.bgTertiary,
  surfaceColor: lightBgColors.surfaceColor,
  modalBg: lightBgColors.modalBg,
  dropdownBg: lightBgColors.dropdownBg,
  docsTheme: 'blue'
}

export const themeConfigs: Record<ThemeMode, ThemeConfig> = {
  dark: purpleDarkConfig,
  light: purpleLightConfig
}

const createThemeOverrides = (config: ThemeConfig, isDark: boolean): GlobalThemeOverrides => {
  const textColorBase = isDark ? '#e0e0e0' : '#333333'
  const textColor1 = isDark ? '#ffffff' : '#1a1a1a'
  const textColor2 = isDark ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.75)'
  const textColor3 = isDark ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.55)'
  const borderColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
  const menuHoverBg = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)'
  const switchBorderColor = isDark ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)'
  const switchBorderColorActive = isDark ? 'rgba(255, 255, 255, 0.4)' : 'rgba(0, 0, 0, 0.4)'
  const tableColor = isDark ? '#1e1e2e' : '#ffffff'
  const tagTextSuccess = isDark ? '#69f0ae' : '#2e7d32'
  const tagTextWarning = isDark ? '#ffd54f' : '#ed6c02'
  const tagTextError = isDark ? '#ff8a80' : '#d32f2f'
  const tagTextInfo = isDark ? '#82b1ff' : '#0288d1'

  return {
    common: {
      primaryColor: config.primaryColor,
      primaryColorHover: config.primaryColorHover,
      primaryColorPressed: config.primaryColorPressed,
      primaryColorSuppl: config.primaryColorSuppl,
      infoColor: '#3B82F6',
      warningColor: '#F59E0B',
      errorColor: '#EF4444',
      successColor: '#10B981',
      borderRadius: '16px',
      cardColor: 'transparent',
      modalColor: config.bgPrimary,
      popoverColor: config.bgPrimary,
      bodyColor: config.bgPrimary,
      textColorBase: textColorBase,
      textColor1: textColor1,
      textColor2: textColor2,
      textColor3: textColor3
    },
    Card: { 
      borderRadius: '20px', 
      borderColor: borderColor, 
      color: config.bgPrimary 
    },
    Button: {
      borderRadiusMedium: '16px',
      fontWeight: '500',
      fontWeightSmall: '500',
      fontWeightMedium: '500',
      fontWeightLarge: '500',
      colorPrimary: config.primaryColor,
      colorPrimaryHover: config.primaryColorHover,
      colorPrimaryPressed: config.primaryColorPressed,
      textColorPrimary: '#ffffff',
      textColorPrimaryHover: '#ffffff',
      textColorPrimaryPressed: '#ffffff',
      borderColorPrimary: config.primaryColor,
      borderColorPrimaryHover: config.primaryColorHover,
      borderColorPrimaryPressed: config.primaryColorPressed,
      borderPrimary: `1px solid ${config.primaryColor}`,
      color: config.primaryColor,
      colorHover: config.primaryColorHover,
      colorPressed: config.primaryColorPressed,
      textColor: '#ffffff',
      textColorHover: '#ffffff',
      textColorPressed: '#ffffff',
      borderColor: config.primaryColor,
      borderColorHover: config.primaryColorHover,
      borderColorPressed: config.primaryColorPressed,
      border: `1px solid ${config.primaryColor}`,
      textColorText: config.primaryColor,
      textColorTextHover: config.primaryColorHover,
      textColorTextPressed: config.primaryColorPressed,
      textColorGhost: config.primaryColor,
      textColorGhostHover: config.primaryColorHover,
      textColorGhostPressed: config.primaryColorPressed,
      colorQuaternary: 'transparent',
      colorQuaternaryHover: generateColorMix(config.primaryColor, '90%'),
      colorQuaternaryPressed: generateColorMix(config.primaryColor, '85%'),
      textColorQuaternary: config.primaryColor,
      textColorQuaternaryHover: config.primaryColorHover,
      textColorQuaternaryPressed: config.primaryColorPressed
    },
    Input: { borderRadius: '10px' },
    Select: { 
      borderRadius: '10px',
      peers: {
        InternalSelectMenu: {
          color: config.dropdownBg
        }
      }
    },
    Dropdown: {
      peers: {
        InternalDropdownMenu: {
          color: config.dropdownBg
        }
      }
    },
    Tag: {
      borderRadius: '6px',
      colorSuccess: 'rgba(16, 185, 129, 0.15)',
      colorSuccessHover: 'rgba(16, 185, 129, 0.25)',
      colorSuccessPressed: 'rgba(16, 185, 129, 0.3)',
      textColorSuccess: '#10B981',
      borderSuccess: `1px solid rgba(16, 185, 129, 0.4)`,
      colorWarning: 'rgba(245, 158, 11, 0.15)',
      colorWarningHover: 'rgba(245, 158, 11, 0.25)',
      colorWarningPressed: 'rgba(245, 158, 11, 0.3)',
      textColorWarning: '#F59E0B',
      borderWarning: `1px solid rgba(245, 158, 11, 0.4)`,
      colorError: 'rgba(239, 68, 68, 0.15)',
      colorErrorHover: 'rgba(239, 68, 68, 0.25)',
      colorErrorPressed: 'rgba(239, 68, 68, 0.3)',
      textColorError: '#EF4444',
      borderError: `1px solid rgba(239, 68, 68, 0.4)`,
      colorInfo: 'rgba(59, 130, 246, 0.15)',
      colorInfoHover: 'rgba(59, 130, 246, 0.25)',
      colorInfoPressed: 'rgba(59, 130, 246, 0.3)',
      textColorInfo: '#3B82F6',
      borderInfo: `1px solid rgba(59, 130, 246, 0.4)`
    },
    Popconfirm: {
      color: config.modalBg,
      boxShadow: isDark ? '0 8px 32px rgba(0, 0, 0, 0.3)' : '0 8px 32px rgba(0, 0, 0, 0.15)',
      arrowColor: config.modalBg,
      peers: {
        Button: {
          fontWeight: '500',
          fontWeightSmall: '500',
          fontWeightMedium: '500',
          fontWeightLarge: '500',
          colorPrimary: config.primaryColor,
          colorPrimaryHover: config.primaryColorHover,
          colorPrimaryPressed: config.primaryColorPressed,
          textColorPrimary: '#ffffff',
          textColorPrimaryHover: '#ffffff',
          textColorPrimaryPressed: '#ffffff',
          borderColorPrimary: config.primaryColor,
          borderColorPrimaryHover: config.primaryColorHover,
          borderColorPrimaryPressed: config.primaryColorPressed,
          borderPrimary: `1px solid ${config.primaryColor}`,
          color: config.primaryColor,
          colorHover: config.primaryColorHover,
          colorPressed: config.primaryColorPressed,
          textColor: '#ffffff',
          textColorHover: '#ffffff',
          textColorPressed: '#ffffff',
          borderColor: config.primaryColor,
          borderColorHover: config.primaryColorHover,
          borderColorPressed: config.primaryColorPressed,
          border: `1px solid ${config.primaryColor}`,
          colorGhost: 'transparent',
          colorGhostHover: generateColorMix(config.primaryColor, '90%'),
          colorGhostPressed: generateColorMix(config.primaryColor, '85%'),
          textColorGhost: config.primaryColor,
          textColorGhostHover: config.primaryColorHover,
          textColorGhostPressed: config.primaryColorPressed,
          borderColorGhost: config.primaryColor,
          borderColorGhostHover: config.primaryColorHover,
          borderColorGhostPressed: config.primaryColorPressed,
          colorQuaternary: 'transparent',
          colorQuaternaryHover: generateColorMix(config.primaryColor, '90%'),
          colorQuaternaryPressed: generateColorMix(config.primaryColor, '85%'),
          textColorQuaternary: config.primaryColor,
          textColorQuaternaryHover: config.primaryColorHover,
          textColorQuaternaryPressed: config.primaryColorPressed
        }
      }
    },
    Popover: {
      // 气泡背景色 - 使用深色背景确保在白天/夜晚模式下都清晰可见
      color: isDark ? 'rgba(0, 0, 0, 0.85)' : 'rgba(0, 0, 0, 0.85)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
      arrowColor: isDark ? 'rgba(0, 0, 0, 0.85)' : 'rgba(0, 0, 0, 0.85)'
    },
    Message: {
      color: config.modalBg,
      textColor: textColor1,
      iconColor: config.primaryColor,
      boxShadow: isDark ? '0 8px 32px rgba(0, 0, 0, 0.3)' : '0 8px 32px rgba(0, 0, 0, 0.15)'
    },
    Notification: {
      color: config.modalBg,
      textColor: textColor1,
      boxShadow: isDark ? '0 8px 32px rgba(0, 0, 0, 0.3)' : '0 8px 32px rgba(0, 0, 0, 0.15)'
    },
    Dialog: {
      color: config.modalBg,
      textColor: textColor1,
      boxShadow: isDark ? '0 8px 32px rgba(0, 0, 0, 0.3)' : '0 8px 32px rgba(0, 0, 0, 0.15)',
      peers: {
        Button: {
          fontWeight: '500',
          fontWeightSmall: '500',
          fontWeightMedium: '500',
          fontWeightLarge: '500',
          colorPrimary: config.primaryColor,
          colorPrimaryHover: config.primaryColorHover,
          colorPrimaryPressed: config.primaryColorPressed,
          textColorPrimary: '#ffffff',
          textColorPrimaryHover: '#ffffff',
          textColorPrimaryPressed: '#ffffff',
          borderColorPrimary: config.primaryColor,
          borderColorPrimaryHover: config.primaryColorHover,
          borderColorPrimaryPressed: config.primaryColorPressed,
          borderPrimary: `1px solid ${config.primaryColor}`,
          color: config.primaryColor,
          colorHover: config.primaryColorHover,
          colorPressed: config.primaryColorPressed,
          textColor: '#ffffff',
          textColorHover: '#ffffff',
          textColorPressed: '#ffffff',
          borderColor: config.primaryColor,
          borderColorHover: config.primaryColorHover,
          borderColorPressed: config.primaryColorPressed,
          border: `1px solid ${config.primaryColor}`,
          colorGhost: 'transparent',
          colorGhostHover: generateColorMix(config.primaryColor, '90%'),
          colorGhostPressed: generateColorMix(config.primaryColor, '85%'),
          textColorGhost: config.primaryColor,
          textColorGhostHover: config.primaryColorHover,
          textColorGhostPressed: config.primaryColorPressed,
          borderColorGhost: config.primaryColor,
          borderColorGhostHover: config.primaryColorHover,
          borderColorGhostPressed: config.primaryColorPressed
        }
      }
    },
    LayoutSider: {
      color: config.bgPrimary,
      borderColor: borderColor,
      toggleBarColor: config.bgPrimary,
      toggleBarColorHover: menuHoverBg,
      toggleIconColor: textColor2,
      toggleIconColorHover: textColor1
    },
    DataTable: {
      thColor: tableColor,
      tdColor: tableColor,
      tdColorHover: tableColor,
      thColorModal: tableColor,
      tdColorModal: tableColor,
      tdColorHoverModal: tableColor,
      thColorPopover: tableColor,
      tdColorPopover: tableColor,
      tdColorHoverPopover: tableColor,
      borderColor: borderColor,
      borderColorModal: borderColor,
      borderColorPopover: borderColor
    },
    Switch: {
      width: '44px',
      widthMedium: '44px',
      widthLarge: '52px',
      height: '22px',
      heightMedium: '22px',
      heightLarge: '26px',
      railColor: config.bgTertiary,
      railColorActive: '#3B82F6',
      buttonColor: '#ffffff',
      buttonColorActive: '#ffffff',
      textColor: textColor2,
      railBorderColor: '#3B82F6',
      railBorderColorActive: '#3B82F6',
      boxShadow: isDark ? '0 2px 4px rgba(0, 0, 0, 0.3)' : '0 2px 4px rgba(0, 0, 0, 0.15)',
      railBorderRadius: '11px',
      buttonBorderRadius: '50%'
    },
    // Radio 组件样式配置
    Radio: {
      // 按钮样式 Radio
      buttonColor: config.bgTertiary,
      buttonColorActive: config.primaryColor,
      buttonTextColor: textColor2,
      buttonTextColorActive: '#ffffff',
      buttonBorderColor: borderColor,
      buttonBorderColorActive: config.primaryColor,
      buttonBorderRadius: '6px'
    },
    Menu: {
      itemColorActive: '#3B82F6',
      itemColorActiveHover: '#60A5FA',
      itemColorActiveCollapsed: '#3B82F6',
      itemTextColorActive: '#ffffff',
      itemTextColorActiveHover: '#ffffff',
      itemIconColorActive: '#ffffff',
      itemIconColorActiveHover: '#ffffff',
      itemColor: 'transparent',
      itemColorHover: menuHoverBg,
      itemTextColor: textColor2,
      itemTextColorHover: textColor1,
      itemIconColor: textColor3,
      itemIconColorHover: textColor2,
      itemColorActiveSub: '#3B82F6',
      itemColorActiveSubHover: '#60A5FA',
      itemTextColorActiveSub: '#ffffff',
      itemTextColorActiveSubHover: '#ffffff',
      borderRadius: '8px',
      borderColor: 'transparent',
      borderColorHorizontal: 'transparent'
    },
    // Tabs 组件样式配置
    Tabs: {
      // Tab 文字颜色
      tabTextColor: textColor2,
      tabTextColorActive: '#ffffff',
      tabTextColorHover: textColor1,
      // Tab 底部边框颜色
      tabBorderColor: borderColor,
      // 激活状态的底部边框
      tabBorderColorActive: config.primaryColor,
      // 背景色
      color: 'transparent',
      // 分割模式：轨道背景色
      colorSegment: config.bgTertiary,
      // 分割模式下激活项的背景（使用紫色主题色）
      colorSegmentActive: config.primaryColor,
      // 标签栏背景
      barColor: config.primaryColor
    },
    // Tooltip 组件样式配置
    Tooltip: {
      // 气泡背景色 - 使用深色背景确保在白天/夜晚模式下都清晰可见
      color: isDark ? 'rgba(0, 0, 0, 0.85)' : 'rgba(0, 0, 0, 0.85)',
      // 文字颜色 - 固定白色
      textColor: '#ffffff',
      // 边框颜色
      borderColor: 'transparent',
      // 圆角
      borderRadius: '6px',
      // 内边距
      padding: '8px 12px',
      // 字体大小
      fontSize: '13px'
    }
  }
}

export const themeOverridesMap: Record<ThemeMode, GlobalThemeOverrides> = {
  dark: createThemeOverrides(themeConfigs.dark, true),
  light: createThemeOverrides(themeConfigs.light, false)
}

export const purpleOverrides = themeOverridesMap.dark
