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
  primary: {
    type: 'primary' as const,
    size: 'small' as const
  },
  secondary: {
    secondary: true,
    size: 'small' as const
  },
  warning: {
    type: 'warning' as const,
    secondary: true,
    size: 'small' as const
  },
  danger: {
    type: 'error' as const,
    secondary: true,
    size: 'small' as const
  },
  ghost: {
    type: 'primary' as const,
    ghost: true,
    size: 'small' as const
  },
  icon: {
    quaternary: true,
    circle: true,
    size: 'small' as const
  },
  iconDanger: {
    quaternary: true,
    circle: true,
    type: 'error' as const,
    size: 'small' as const
  },
  text: {
    quaternary: true,
    size: 'small' as const
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
