/**
 * 可单独自定义外观的组件 key 清单
 *
 * 使用规则：
 * - 每个需要"单独自定义外观"的弹框/卡片/输入框等组件，都在此声明一个唯一 key
 * - 在使用 AppGlassModal 等容器时通过 appearance-key="xxx" 传入
 * - 配置 UI 会从此清单读取可选项展示给用户
 *
 * 新增自定义组件时只需：
 *   1. 在此文件 APPEARANCE_KEYS 中添加一条
 *   2. 在使用处添加 appearance-key="xxx" prop
 */
export const APPEARANCE_KEYS = {
  // ===== 弹框类 =====
  'feed-edit-modal': {
    label: 'RSS 订阅源（添加/编辑）',
    description: '添加或编辑 RSS 订阅源的弹框表单',
    categories: ['modal', 'input']
  },
  'rss-rule-modal': {
    label: '匹配规则（添加/编辑）',
    description: '添加或编辑 RSS 下载匹配规则的弹框表单',
    categories: ['modal', 'input']
  },
} as const

export type AppearanceKey = keyof typeof APPEARANCE_KEYS

export interface AppearanceKeyMeta {
  label: string
  description: string
  /** 该组件支持自定义的分区（modal/card/input/search/list/tabs） */
  categories: ReadonlyArray<string>
}

/** 获取所有 key 的下拉选项 */
export const appearanceKeyOptions = Object.entries(APPEARANCE_KEYS).map(([value, meta]) => ({
  label: meta.label,
  value,
}))

/** 根据 key 获取元信息 */
export function getAppearanceKeyMeta(key: string): AppearanceKeyMeta | undefined {
  return (APPEARANCE_KEYS as Record<string, AppearanceKeyMeta>)[key]
}
