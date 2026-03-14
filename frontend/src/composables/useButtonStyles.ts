import type { ButtonProps } from 'naive-ui'

export interface ButtonConfig {
  type?: ButtonProps['type']
  secondary?: boolean
  quaternary?: boolean
  ghost?: boolean
  size?: ButtonProps['size']
  circle?: boolean
}

export const ButtonStyles = {
  // 主要按钮 - 主题色底色 + 白色文字 + 主题色边框
  primary: {
    type: 'primary' as const,
    size: 'medium' as const
  },
  // 次要按钮 - 主题色底色 + 白色文字 + 主题色边框
  secondary: {
    type: 'primary' as const,
    size: 'medium' as const
  },
  // 警告按钮 - 警告色底色 + 白色文字 + 警告色边框
  warning: {
    type: 'warning' as const,
    size: 'medium' as const
  },
  // 危险按钮 - 错误色底色 + 白色文字 + 错误色边框
  danger: {
    type: 'error' as const,
    size: 'medium' as const
  },
  // 幽灵按钮 - 透明底色 + 主题色文字 + 主题色边框
  ghost: {
    type: 'primary' as const,
    ghost: true,
    size: 'medium' as const
  },
  // 图标按钮 - 透明底色 + 主题色文字 + 主题色边框
  icon: {
    type: 'primary' as const,
    ghost: true,
    circle: true,
    size: 'small' as const
  },
  // 危险图标按钮 - 透明底色 + 错误色文字 + 错误色边框
  iconDanger: {
    type: 'error' as const,
    ghost: true,
    circle: true,
    size: 'small' as const
  },
  // 主色图标按钮 - 透明底色 + 主题色文字 + 主题色边框
  iconPrimary: {
    type: 'primary' as const,
    ghost: true,
    circle: true,
    size: 'small' as const
  },
  // 文字按钮 - 透明底色 + 主题色文字（无边框）
  text: {
    type: 'primary' as const,
    quaternary: true,
    size: 'small' as const
  },
  // 对话框取消按钮 - 主题色底色 + 黑色文字 + 主题色边框
  dialogCancel: {
    type: 'primary' as const,
    size: 'medium' as const
  },
  // 对话框确认按钮 - 主题色底色 + 白色文字 + 主题色边框
  dialogConfirm: {
    type: 'primary' as const,
    size: 'medium' as const
  },
  // 对话框危险按钮 - 错误色底色 + 白色文字 + 错误色边框
  dialogDanger: {
    type: 'error' as const,
    size: 'medium' as const
  }
} as const

export type ButtonStyleKey = keyof typeof ButtonStyles

export function getButtonStyle(key: ButtonStyleKey): ButtonConfig {
  return ButtonStyles[key]
}

export const PopconfirmTexts = {
  confirm: '确定',
  cancel: '取消',
  delete: '确定删除？',
  deleteProfile: '确定删除此策略吗？',
  deleteRule: '确定删除此规则吗？',
  deleteTemplate: '确定删除此模板吗？',
  deleteSubject: '确定删除此条目吗？',
  deleteFeed: '确定删除此订阅源吗？',
  deleteClient: '确定删除此客户端吗？'
} as const
