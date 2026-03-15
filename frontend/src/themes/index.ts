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

// 紫色主题配置（暗色）
const purpleDarkConfig: ThemeConfig = {
  name: '暗夜紫韵',
  primaryColor: '#bb86fc',
  primaryColorHover: '#d1a8ff',
  primaryColorPressed: '#995df0',
  primaryColorSuppl: '#7c4dff',
  logoColor: '#bb86fc',
  bgPrimary: darkBgColors.bgPrimary,
  bgSecondary: darkBgColors.bgSecondary,
  bgTertiary: darkBgColors.bgTertiary,
  surfaceColor: darkBgColors.surfaceColor,
  modalBg: darkBgColors.modalBg,
  dropdownBg: darkBgColors.dropdownBg,
  docsTheme: 'purple'
}

// 紫色主题配置（亮色）
const purpleLightConfig: ThemeConfig = {
  name: '白昼紫韵',
  primaryColor: '#7c4dff',
  primaryColorHover: '#9965ff',
  primaryColorPressed: '#5c3dd4',
  primaryColorSuppl: '#bb86fc',
  logoColor: '#7c4dff',
  bgPrimary: lightBgColors.bgPrimary,
  bgSecondary: lightBgColors.bgSecondary,
  bgTertiary: lightBgColors.bgTertiary,
  surfaceColor: lightBgColors.surfaceColor,
  modalBg: lightBgColors.modalBg,
  dropdownBg: lightBgColors.dropdownBg,
  docsTheme: 'purple'
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
      infoColor: isDark ? '#03dac6' : '#0288d1',
      warningColor: isDark ? '#ffb74d' : '#ed6c02',
      errorColor: isDark ? '#cf6679' : '#d32f2f',
      successColor: isDark ? '#81c784' : '#2e7d32',
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
      colorSuccess: isDark ? 'rgba(76, 175, 80, 0.15)' : 'rgba(76, 175, 80, 0.1)',
      colorSuccessHover: isDark ? 'rgba(76, 175, 80, 0.25)' : 'rgba(76, 175, 80, 0.2)',
      colorSuccessPressed: isDark ? 'rgba(76, 175, 80, 0.3)' : 'rgba(76, 175, 80, 0.25)',
      textColorSuccess: tagTextSuccess,
      borderSuccess: `1px solid ${isDark ? 'rgba(76, 175, 80, 0.5)' : 'rgba(76, 175, 80, 0.4)'}`,
      colorWarning: isDark ? 'rgba(255, 152, 0, 0.15)' : 'rgba(255, 152, 0, 0.1)',
      colorWarningHover: isDark ? 'rgba(255, 152, 0, 0.25)' : 'rgba(255, 152, 0, 0.2)',
      colorWarningPressed: isDark ? 'rgba(255, 152, 0, 0.3)' : 'rgba(255, 152, 0, 0.25)',
      textColorWarning: tagTextWarning,
      borderWarning: `1px solid ${isDark ? 'rgba(255, 152, 0, 0.5)' : 'rgba(255, 152, 0, 0.4)'}`,
      colorError: isDark ? 'rgba(244, 67, 54, 0.15)' : 'rgba(244, 67, 54, 0.1)',
      colorErrorHover: isDark ? 'rgba(244, 67, 54, 0.25)' : 'rgba(244, 67, 54, 0.2)',
      colorErrorPressed: isDark ? 'rgba(244, 67, 54, 0.3)' : 'rgba(244, 67, 54, 0.25)',
      textColorError: tagTextError,
      borderError: `1px solid ${isDark ? 'rgba(244, 67, 54, 0.5)' : 'rgba(244, 67, 54, 0.4)'}`,
      colorInfo: isDark ? 'rgba(33, 150, 243, 0.15)' : 'rgba(33, 150, 243, 0.1)',
      colorInfoHover: isDark ? 'rgba(33, 150, 243, 0.25)' : 'rgba(33, 150, 243, 0.2)',
      colorInfoPressed: isDark ? 'rgba(33, 150, 243, 0.3)' : 'rgba(33, 150, 243, 0.25)',
      textColorInfo: tagTextInfo,
      borderInfo: `1px solid ${isDark ? 'rgba(33, 150, 243, 0.5)' : 'rgba(33, 150, 243, 0.4)'}`
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
      // 开启状态轨道颜色固定为深紫色，不随白天/夜晚模式变化
      railColorActive: '#7c4dff',
      // 按钮颜色固定为白色，不受白天/夜晚模式影响
      buttonColor: '#ffffff',
      buttonColorActive: '#ffffff',
      textColor: textColor2,
      // 边框颜色固定为紫色，不随白天/夜晚模式变化
      railBorderColor: '#7c4dff',
      railBorderColorActive: '#7c4dff',
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
      itemColorActive: '#7c4dff',
      itemColorActiveHover: '#9965ff',
      itemColorActiveCollapsed: '#7c4dff',
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
      itemColorActiveSub: '#7c4dff',
      itemColorActiveSubHover: '#9965ff',
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
