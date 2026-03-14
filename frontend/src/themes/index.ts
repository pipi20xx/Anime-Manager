import { GlobalThemeOverrides } from 'naive-ui'

export type ThemeType = 'purple' | 'green' | 'blue' | 'red'

export const themeOptions = [
  { label: '暗夜紫韵 (Purple)', key: 'purple' },
  { label: '森林绿意 (Green)', key: 'green' },
  { label: '海洋蓝调 (Blue)', key: 'blue' },
  { label: '烈焰红妆 (Red)', key: 'red' }
]

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

// 统一的灰色系背景色 - 与主题色分离
const grayBgColors = {
  bgPrimary: '#1a1a1f',      // 最深背景
  bgSecondary: '#242429',    // 次级背景
  bgTertiary: '#2e2e33',     // 三级背景
  surfaceColor: '255, 255, 255',  // 表面色（用于半透明叠加）
  modalBg: 'rgba(30, 30, 35, 0.95)',     // 弹窗背景
  dropdownBg: 'rgba(26, 26, 31, 0.98)'   // 下拉菜单背景
}

export const themeConfigs: Record<ThemeType, ThemeConfig> = {
  purple: {
    name: '暗夜紫韵',
    primaryColor: '#bb86fc',
    primaryColorHover: '#d1a8ff',
    primaryColorPressed: '#995df0',
    primaryColorSuppl: '#7c4dff',
    logoColor: '#bb86fc',
    bgPrimary: grayBgColors.bgPrimary,
    bgSecondary: grayBgColors.bgSecondary,
    bgTertiary: grayBgColors.bgTertiary,
    surfaceColor: grayBgColors.surfaceColor,
    modalBg: grayBgColors.modalBg,
    dropdownBg: grayBgColors.dropdownBg,
    docsTheme: 'purple'
  },
  green: {
    name: '森林绿意',
    primaryColor: '#81c784',
    primaryColorHover: '#a5d6a7',
    primaryColorPressed: '#66bb6a',
    primaryColorSuppl: '#4caf50',
    logoColor: '#81c784',
    bgPrimary: grayBgColors.bgPrimary,
    bgSecondary: grayBgColors.bgSecondary,
    bgTertiary: grayBgColors.bgTertiary,
    surfaceColor: grayBgColors.surfaceColor,
    modalBg: grayBgColors.modalBg,
    dropdownBg: grayBgColors.dropdownBg,
    docsTheme: 'green'
  },
  blue: {
    name: '海洋蓝调',
    primaryColor: '#64b5f6',
    primaryColorHover: '#90caf9',
    primaryColorPressed: '#42a5f5',
    primaryColorSuppl: '#2196f3',
    logoColor: '#64b5f6',
    bgPrimary: grayBgColors.bgPrimary,
    bgSecondary: grayBgColors.bgSecondary,
    bgTertiary: grayBgColors.bgTertiary,
    surfaceColor: grayBgColors.surfaceColor,
    modalBg: grayBgColors.modalBg,
    dropdownBg: grayBgColors.dropdownBg,
    docsTheme: 'blue'
  },
  red: {
    name: '烈焰红妆',
    primaryColor: '#e57373',
    primaryColorHover: '#ef9a9a',
    primaryColorPressed: '#ef5350',
    primaryColorSuppl: '#f44336',
    logoColor: '#e57373',
    bgPrimary: grayBgColors.bgPrimary,
    bgSecondary: grayBgColors.bgSecondary,
    bgTertiary: grayBgColors.bgTertiary,
    surfaceColor: grayBgColors.surfaceColor,
    modalBg: grayBgColors.modalBg,
    dropdownBg: grayBgColors.dropdownBg,
    docsTheme: 'red'
  }
}

const createThemeOverrides = (config: ThemeConfig): GlobalThemeOverrides => ({
  common: {
    primaryColor: config.primaryColor,
    primaryColorHover: config.primaryColorHover,
    primaryColorPressed: config.primaryColorPressed,
    primaryColorSuppl: config.primaryColorSuppl,
    infoColor: '#03dac6',
    warningColor: '#ffb74d',
    errorColor: '#cf6679',
    successColor: '#81c784',
    borderRadius: '16px',
    cardColor: 'transparent',
    modalColor: config.bgPrimary,
    popoverColor: config.bgPrimary,
    bodyColor: config.bgPrimary,
    textColorBase: '#e0e0e0'
  },
  Card: { borderRadius: '20px', borderColor: 'rgba(255, 255, 255, 0.08)' },
  Button: {
    borderRadiusMedium: '16px',
    fontWeight: '500',
    fontWeightSmall: '500',
    fontWeightMedium: '500',
    fontWeightLarge: '500',
    // 主要按钮 - 主题色底色 + 黑色文字 + 主题色边框
    colorPrimary: config.primaryColor,
    colorPrimaryHover: config.primaryColorHover,
    colorPrimaryPressed: config.primaryColorPressed,
    textColorPrimary: '#000000',
    textColorPrimaryHover: '#000000',
    textColorPrimaryPressed: '#000000',
    borderColorPrimary: config.primaryColor,
    borderColorPrimaryHover: config.primaryColorHover,
    borderColorPrimaryPressed: config.primaryColorPressed,
    borderPrimary: `1px solid ${config.primaryColor}`,
    // 默认按钮 - 主题色底色 + 黑色文字 + 主题色边框
    color: config.primaryColor,
    colorHover: config.primaryColorHover,
    colorPressed: config.primaryColorPressed,
    textColor: '#000000',
    textColorHover: '#000000',
    textColorPressed: '#000000',
    borderColor: config.primaryColor,
    borderColorHover: config.primaryColorHover,
    borderColorPressed: config.primaryColorPressed,
    border: `1px solid ${config.primaryColor}`,
    // 文字按钮(text type)颜色配置 - 透明底 + 黑色文字
    textColorText: '#000000',
    textColorTextHover: '#000000',
    textColorTextPressed: '#000000',
    // 幽灵按钮(ghost)颜色配置 - 透明底 + 黑色文字 + 主题色边框
    textColorGhost: '#000000',
    textColorGhostHover: '#000000',
    textColorGhostPressed: '#000000',
    // Quaternary 按钮颜色配置 - 透明底 + 黑色文字
    colorQuaternary: 'transparent',
    colorQuaternaryHover: generateColorMix(config.primaryColor, '90%'),
    colorQuaternaryPressed: generateColorMix(config.primaryColor, '85%'),
    textColorQuaternary: '#000000',
    textColorQuaternaryHover: '#000000',
    textColorQuaternaryPressed: '#000000'
  },
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
  Tag: {
    borderRadius: '6px',
    // Success 标签 - 使用更亮的绿色提高对比度
    colorSuccess: 'rgba(76, 175, 80, 0.15)',
    colorSuccessHover: 'rgba(76, 175, 80, 0.25)',
    colorSuccessPressed: 'rgba(76, 175, 80, 0.3)',
    textColorSuccess: '#69f0ae',
    borderSuccess: '1px solid rgba(76, 175, 80, 0.5)',
    // Warning 标签 - 使用更亮的橙色提高对比度
    colorWarning: 'rgba(255, 152, 0, 0.15)',
    colorWarningHover: 'rgba(255, 152, 0, 0.25)',
    colorWarningPressed: 'rgba(255, 152, 0, 0.3)',
    textColorWarning: '#ffd54f',
    borderWarning: '1px solid rgba(255, 152, 0, 0.5)',
    // Error 标签 - 使用更亮的红色提高对比度
    colorError: 'rgba(244, 67, 54, 0.15)',
    colorErrorHover: 'rgba(244, 67, 54, 0.25)',
    colorErrorPressed: 'rgba(244, 67, 54, 0.3)',
    textColorError: '#ff8a80',
    borderError: '1px solid rgba(244, 67, 54, 0.5)',
    // Info 标签 - 使用更亮的蓝色提高对比度
    colorInfo: 'rgba(33, 150, 243, 0.15)',
    colorInfoHover: 'rgba(33, 150, 243, 0.25)',
    colorInfoPressed: 'rgba(33, 150, 243, 0.3)',
    textColorInfo: '#82b1ff',
    borderInfo: '1px solid rgba(33, 150, 243, 0.5)'
  },
  Popconfirm: {
    color: 'var(--app-modal-bg)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    arrowColor: 'var(--app-modal-bg)',
    peers: {
      Button: {
        fontWeight: '500',
        fontWeightSmall: '500',
        fontWeightMedium: '500',
        fontWeightLarge: '500',
        // 主要按钮 - 主题色底色 + 黑色文字 + 主题色边框
        colorPrimary: config.primaryColor,
        colorPrimaryHover: config.primaryColorHover,
        colorPrimaryPressed: config.primaryColorPressed,
        textColorPrimary: '#000000',
        textColorPrimaryHover: '#000000',
        textColorPrimaryPressed: '#000000',
        borderColorPrimary: config.primaryColor,
        borderColorPrimaryHover: config.primaryColorHover,
        borderColorPrimaryPressed: config.primaryColorPressed,
        borderPrimary: `1px solid ${config.primaryColor}`,
        // 默认按钮 - 主题色底色 + 黑色文字 + 主题色边框
        color: config.primaryColor,
        colorHover: config.primaryColorHover,
        colorPressed: config.primaryColorPressed,
        textColor: '#000000',
        textColorHover: '#000000',
        textColorPressed: '#000000',
        borderColor: config.primaryColor,
        borderColorHover: config.primaryColorHover,
        borderColorPressed: config.primaryColorPressed,
        border: `1px solid ${config.primaryColor}`,
        // Ghost 按钮 - 透明底色 + 黑色文字 + 主题色边框
        colorGhost: 'transparent',
        colorGhostHover: generateColorMix(config.primaryColor, '90%'),
        colorGhostPressed: generateColorMix(config.primaryColor, '85%'),
        textColorGhost: '#000000',
        textColorGhostHover: '#000000',
        textColorGhostPressed: '#000000',
        borderColorGhost: config.primaryColor,
        borderColorGhostHover: config.primaryColorHover,
        borderColorGhostPressed: config.primaryColorPressed,
        // Quaternary 按钮 - 透明底色 + 黑色文字
        colorQuaternary: 'transparent',
        colorQuaternaryHover: generateColorMix(config.primaryColor, '90%'),
        colorQuaternaryPressed: generateColorMix(config.primaryColor, '85%'),
        textColorQuaternary: '#000000',
        textColorQuaternaryHover: '#000000',
        textColorQuaternaryPressed: '#000000'
      }
    }
  },
  Popover: {
    color: 'var(--app-modal-bg)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    arrowColor: 'var(--app-modal-bg)'
  },
  Message: {
    color: 'var(--app-modal-bg)',
    textColor: 'var(--text-primary)',
    iconColor: config.primaryColor,
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
  },
  Notification: {
    color: 'var(--app-modal-bg)',
    textColor: 'var(--text-primary)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
  },
  Dialog: {
    color: 'var(--app-modal-bg)',
    textColor: 'var(--text-primary)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    peers: {
      Button: {
        fontWeight: '500',
        fontWeightSmall: '500',
        fontWeightMedium: '500',
        fontWeightLarge: '500',
        // 确认按钮 - 主题色底色 + 黑色文字 + 主题色边框
        colorPrimary: config.primaryColor,
        colorPrimaryHover: config.primaryColorHover,
        colorPrimaryPressed: config.primaryColorPressed,
        textColorPrimary: '#000000',
        textColorPrimaryHover: '#000000',
        textColorPrimaryPressed: '#000000',
        borderColorPrimary: config.primaryColor,
        borderColorPrimaryHover: config.primaryColorHover,
        borderColorPrimaryPressed: config.primaryColorPressed,
        borderPrimary: `1px solid ${config.primaryColor}`,
        // 默认按钮 - 主题色底色 + 黑色文字 + 主题色边框
        color: config.primaryColor,
        colorHover: config.primaryColorHover,
        colorPressed: config.primaryColorPressed,
        textColor: '#000000',
        textColorHover: '#000000',
        textColorPressed: '#000000',
        borderColor: config.primaryColor,
        borderColorHover: config.primaryColorHover,
        borderColorPressed: config.primaryColorPressed,
        border: `1px solid ${config.primaryColor}`,
        // Ghost 按钮 - 透明底色 + 黑色文字 + 主题色边框
        colorGhost: 'transparent',
        colorGhostHover: generateColorMix(config.primaryColor, '90%'),
        colorGhostPressed: generateColorMix(config.primaryColor, '85%'),
        textColorGhost: '#000000',
        textColorGhostHover: '#000000',
        textColorGhostPressed: '#000000',
        borderColorGhost: config.primaryColor,
        borderColorGhostHover: config.primaryColorHover,
        borderColorGhostPressed: config.primaryColorPressed
      }
    }
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
    tdColorHover: 'rgba(255, 255, 255, 0.05)',
    thColorModal: 'transparent',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'rgba(255, 255, 255, 0.05)',
    thColorPopover: 'transparent',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'rgba(255, 255, 255, 0.05)',
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderColorModal: 'rgba(255, 255, 255, 0.1)',
    borderColorPopover: 'rgba(255, 255, 255, 0.1)'
  },
  // Switch 开关组件统一样式配置
  Switch: {
    // 基础尺寸
    width: '44px',
    widthMedium: '44px',
    widthLarge: '52px',
    height: '22px',
    heightMedium: '22px',
    heightLarge: '26px',
    // 轨道颜色 - 关闭时灰色背景，打开时主题色
    railColor: 'var(--bg-tertiary)',
    railColorActive: config.primaryColor,
    // 按钮颜色
    buttonColor: 'var(--text-primary)',
    buttonColorActive: 'var(--text-primary)',
    // 文字颜色
    textColor: 'var(--text-secondary)',
    // 边框 - 使用白色（关闭和打开状态都可见）
    railBorderColor: 'rgba(255, 255, 255, 0.3)',
    railBorderColorActive: 'rgba(255, 255, 255, 0.4)',
    // 边框和阴影
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
    // 圆角
    railBorderRadius: '11px',
    buttonBorderRadius: '50%'
  }
})

export const themeOverridesMap: Record<ThemeType, GlobalThemeOverrides> = {
  purple: createThemeOverrides(themeConfigs.purple),
  green: createThemeOverrides(themeConfigs.green),
  blue: createThemeOverrides(themeConfigs.blue),
  red: createThemeOverrides(themeConfigs.red)
}

export const purpleOverrides = themeOverridesMap.purple
