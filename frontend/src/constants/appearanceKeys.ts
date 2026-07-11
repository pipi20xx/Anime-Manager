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
 *
 * 注意：desktop 和 mobile 版本的同一个弹框共用同一个 key，
 *       这样用户配置一次即可同时生效于两端。
 */

export interface AppearanceKeyMeta {
  /** 显示名称 */
  label: string
  /** 详细描述 */
  description: string
  /** 所属页面（用于分组显示） */
  page: string
  /** 该组件支持自定义的分区（modal/card/input/search/list/tabs） */
  categories: ReadonlyArray<string>
}

export const APPEARANCE_KEYS = {
  // ===== 订阅与下载 =====
  'feed-edit-modal': {
    label: '新增订阅源 → 添加/编辑 RSS 订阅源',
    description: '添加或编辑 RSS 订阅源的弹框表单',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'subscription-edit-modal': {
    label: '添加新订阅 → 新建/编辑订阅',
    description: '新建或编辑番剧订阅的弹框表单',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'subscription-detail-modal': {
    label: '查看推送记录 → 订阅推送记录详情',
    description: '查看番剧订阅推送记录详情的弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'subscription-help-modal': {
    label: '打开 → 订阅过滤项填写指南',
    description: '订阅过滤项填写帮助说明弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'subscription-template-modal': {
    label: '订阅预设管理 → 订阅预设模板管理',
    description: '管理订阅预设模板，可新增或编辑订阅预设的弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'bangumi-quick-subscribe-modal': {
    label: 'Bangumi 一键订阅',
    description: 'Bangumi 番剧一键订阅弹框，快速同步全周放送列表',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'aggregated-feed-items-modal': {
    label: '订阅源详情',
    description: '聚合查看所有 RSS 源条目的弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'rss-detect-manager-modal': {
    label: '自动RSS订阅管理 → 自动 RSS 订阅管理',
    description: '管理 RSS 自动订阅探测任务，可添加或编辑探测任务的弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'rss-detect-modal': {
    label: '打开 → RSS 探测自动订阅',
    description: '填入 RSS 链接自动识别番剧并创建订阅的弹框',
    page: '订阅与下载',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 规则与匹配 =====
  'rss-rule-modal': {
    label: '创建新规则 → 添加/编辑匹配规则',
    description: '添加或编辑 RSS 下载匹配规则的弹框表单',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'rule-edit-modal': {
    label: '创建重命名规则 → 创建新规则/编辑重命名规则',
    description: '创建或编辑重命名规则的弹框表单',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'priority-rule-modal': {
    label: '洗版规则 → 洗版规则管理',
    description: '编辑优先级基础规则与洗版策略的弹框表单',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'rule-preview-modal': {
    label: '预览匹配 → 匹配结果预览',
    description: '预览规则匹配结果的弹框',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'aggregated-rule-history-modal': {
    label: '下载记录',
    description: '聚合查看所有规则下载记录的弹框',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'classifier-edit-modal': {
    label: '添加新分类规则 → 添加/编辑分类规则',
    description: '添加或编辑文件分类规则的弹框表单',
    page: '规则与匹配',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 任务管理 =====
  'task-edit-modal': {
    label: '创建整理任务 → 创建新整理任务/编辑任务配置',
    description: '创建或编辑整理任务的弹框表单',
    page: '任务管理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'strm-task-modal': {
    label: '新建任务 → 新建/编辑 STRM 任务',
    description: '新建或编辑 STRM 任务配置的弹框表单',
    page: '任务管理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'task-history-modal': {
    label: '查看日志 → 任务日志',
    description: '查看任务执行日志的弹框',
    page: '任务管理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'execution-log-modal': {
    label: '预览并手动执行 → 整理任务预览/正式执行日志',
    description: '查看整理任务预览或正式执行日志的弹框',
    page: '任务管理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'log-console-modal': {
    label: '打开实时控制台 → 实时系统日志',
    description: '实时查看系统日志输出的控制台弹框，也可查看历史日志',
    page: '任务管理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 文件整理 =====
  'manual-organize-modal': {
    label: '整理当前目录 → 手动整理当前目录（临时任务）',
    description: '手动整理当前目录文件的弹框表单（临时任务）',
    page: '文件整理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'file-picker-modal': {
    label: '打开 → 选择文件或目录',
    description: '选择文件或目录的弹框',
    page: '文件整理',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== TMDB / 识别 =====
  'tmdb-full-data-modal': {
    label: '手动新增 → 修正/新增元数据',
    description: '修正或手动新增 TMDB 元数据的弹框表单',
    page: 'TMDB / 识别',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'recognition-modal': {
    label: '单文件识别',
    description: '单文件番剧识别结果弹框',
    page: 'TMDB / 识别',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 日历 / 缓存 =====
  'calendar-modal': {
    label: '管理追踪 → 追踪管理',
    description: '番剧追踪管理弹框',
    page: '日历 / 缓存',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'cache-modal': {
    label: '手动新增 → 新增/编辑缓存记录',
    description: '新增或编辑缓存记录的弹框表单',
    page: '日历 / 缓存',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 下载客户端 / 健康检查 =====
  'client-edit-modal': {
    label: '添加客户端 → 添加/编辑下载器',
    description: '添加或编辑下载器（客户端）的弹框表单',
    page: '下载客户端',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'health-check-manager-modal': {
    label: '添加配置 → 健康检查配置',
    description: '下载客户端健康检查配置弹框',
    page: '下载客户端',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 用户映射 =====
  'user-mapping-modal': {
    label: '添加映射 → 添加/编辑映射',
    description: '添加或编辑用户映射关系的弹框表单',
    page: '用户映射',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 外部控制 =====
  'external-control-modal': {
    label: '打开 → API 外部控制中心',
    description: 'API 外部控制命令管理弹框',
    page: '外部控制',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== Jackett =====
  'jackett-fill-modal': {
    label: '搜寻补全缺失集数 → 搜寻补全',
    description: 'Jackett 索引搜寻补全弹框',
    page: 'Jackett',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 系统设置 =====
  'settings-guide-modal': {
    label: '点击图片 → 图片预览',
    description: '设置向导中预览图片的弹框',
    page: '系统设置',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'service-status-modal': {
    label: '查看队列 → 队列内容',
    description: '查看服务队列内容的弹框',
    page: '系统设置',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },
  'account-modal': {
    label: 'TOTP 动态验证码 → 设置双重身份验证',
    description: '设置账号双重身份验证的弹框',
    page: '系统设置',
    categories: ['modal', 'input', 'search', 'tabs', 'card', 'list', 'button']
  },

  // ===== 卡片 =====
  'strm-task-card': {
    label: '虚拟 STRM 库 → STRM 任务卡片',
    description: '虚拟 STRM 库页面中的任务列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'organize-rule-card': {
    label: '整理与重命名 → 规则管理 → 整理规则卡片',
    description: '整理与重命名页面「规则管理」中的规则列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'organize-task-card': {
    label: '整理与重命名 → 整理任务 → 整理任务卡片',
    description: '整理与重命名页面「整理任务」中的任务列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'subscription-card': {
    label: '订阅管理 → 追剧订阅卡片',
    description: '订阅管理页面中的番剧订阅列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'feed-card': {
    label: '订阅与下载 → 订阅源 → 订阅源卡片',
    description: '订阅与下载页面「订阅源」中的 RSS 订阅源列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'rss-rule-card': {
    label: '订阅与下载 → 下载规则 → 下载规则卡片',
    description: '订阅与下载页面「下载规则」中的 RSS 匹配规则列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'client-card': {
    label: '系统设置 → 下载客户端卡片',
    description: '系统设置页面中的下载客户端配置卡片',
    page: '卡片',
    categories: ['card']
  },
  'priority-profile-card': {
    label: '洗版规则弹框 → 洗版策略卡片',
    description: '洗版规则弹框「洗版策略」中的策略配置卡片',
    page: '卡片',
    categories: ['card']
  },
  'priority-rule-card': {
    label: '洗版规则弹框 → 基础规则卡片',
    description: '洗版规则弹框「基础规则」中的规则列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'track-card': {
    label: '日历 → 追踪番剧卡片',
    description: '日历页面中选中日期的番剧追踪卡片',
    page: '卡片',
    categories: ['card']
  },
  'table-card': {
    label: '数据维护 → 数据库表卡片',
    description: '数据维护页面中的数据库表信息卡片',
    page: '卡片',
    categories: ['card']
  },
  'organize-history-card': {
    label: '整理历史 → 整理历史卡片',
    description: '整理历史页面中的整理记录列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'task-history-card': {
    label: '任务中心 → 任务卡片',
    description: '任务中心页面中的任务列表卡片',
    page: '卡片',
    categories: ['card']
  },
  'secondary-rule-card': {
    label: '数据中心 → 二级分类规则 → 二级分类规则卡片',
    description: '数据中心页面「二级分类规则」中的规则配置卡片',
    page: '卡片',
    categories: ['card']
  },
  'maintenance-card': {
    label: '数据中心 → 维护中心 → 维护中心卡片',
    description: '数据中心页面「维护中心」中的数据库维护卡片',
    page: '卡片',
    categories: ['card']
  },
  'tmdb-data-card': {
    label: '数据中心 → 元数据资产 → 元数据资产卡片',
    description: '数据中心页面「元数据资产」中的数据表格和卡片',
    page: '卡片',
    categories: ['card', 'list']
  },
  'mapping-card': {
    label: '数据中心 → ID映射管理 → ID映射管理卡片',
    description: '数据中心页面「ID映射管理」中的统计卡片和数据表格',
    page: '卡片',
    categories: ['card', 'list', 'search', 'tabs']
  },
} as const

export type AppearanceKey = keyof typeof APPEARANCE_KEYS

/** 获取所有 key 的下拉选项（扁平，未分组） */
export const appearanceKeyOptions = Object.entries(APPEARANCE_KEYS).map(([value, meta]) => ({
  label: meta.label,
  value,
}))

/** 获取按 page 分组的下拉选项（用于 n-select 的分组显示） */
export const appearanceKeyGroupedOptions = (() => {
  const groups: Record<string, { label: string; value: string }[]> = {}
  for (const [value, meta] of Object.entries(APPEARANCE_KEYS)) {
    if (!groups[meta.page]) groups[meta.page] = []
    groups[meta.page].push({ label: meta.label, value })
  }
  return Object.entries(groups).map(([page, items]) => ({
    type: 'group' as const,
    label: page,
    key: page,
    children: items,
  }))
})()

/** 根据 key 获取元信息 */
export function getAppearanceKeyMeta(key: string): AppearanceKeyMeta | undefined {
  return (APPEARANCE_KEYS as Record<string, AppearanceKeyMeta>)[key]
}

// ============================================================
// 可自定义页面（页面级背景 + 组件覆盖 + 页面内弹框/卡片自定义）
// ============================================================

export interface CustomizablePageMeta {
  /** 显示名称 */
  label: string
  /** 详细描述 */
  description: string
  /** 对应的 Vue Router 路由名称 */
  routeName: string
}

/**
 * 可自定义页面清单
 *
 * 每个页面对应一个路由，可以在外观设置中为其设置：
 * 1. 独立的背景图与遮罩效果（覆盖全局背景）
 * 2. 页面级组件覆盖（输入框/搜索框/标签页/列表/按钮/卡片/文字样式）
 * 3. 管理该页面下所有弹框和卡片的单独自定义
 */
export const CUSTOMIZABLE_PAGES = {
  'subscription':      { label: '订阅与下载',     description: 'RSS 订阅与下载管理页面',               routeName: 'Subscription' },
  'organizer':         { label: '整理重命名',     description: '整理重命名、规则管理、任务配置页面',   routeName: 'Organizer' },
  'organize-history':  { label: '整理历史',       description: '整理历史记录页面',                     routeName: 'OrganizeHistory' },
  'tasks':             { label: '任务中心',       description: '任务管理与日志页面',                   routeName: 'TaskHistory' },
  'strm':              { label: '虚拟 STRM 库',   description: 'STRM 虚拟库管理页面',                  routeName: 'StrmGenerator' },
  'calendar':          { label: '追剧日历',       description: '番剧追剧日历页面',                     routeName: 'Calendar' },
  'database':          { label: '系统数据中心',   description: '数据中心（元数据/二级分类/ID映射/维护）', routeName: 'Database' },
  'external-control':  { label: '外部控制',       description: 'API 外部控制页面',                     routeName: 'ExternalControl' },
  'jackett-search':    { label: 'Jackett 搜索',   description: 'Jackett 索引搜索页面',                 routeName: 'JackettSearch' },
  'settings':          { label: '系统设置',       description: '系统设置页面（含下载客户端等）',       routeName: 'Settings' },
  'file-browser':      { label: '文件浏览',       description: '文件浏览与单文件识别页面',             routeName: 'FileBrowser' },
  'usage-guide':       { label: '规则说明',       description: '使用指南与规则说明页面',               routeName: 'UsageGuide' },
  'home':              { label: '识别调试台',     description: '番剧识别调试页面',                     routeName: 'Home' },
  'appearance':        { label: '外观设置',       description: '外观自定义设置页面',                   routeName: 'Appearance' },
  'explore':           { label: '探索',           description: 'TMDB 推荐/发现/搜索页面',              routeName: 'Explore' },
  'tmdb-detail':       { label: 'TMDB 详情',     description: 'TMDB 卡片详情页面',                    routeName: 'TmdbDetail' },
  'bangumi-detail':    { label: 'Bangumi 详情',  description: 'Bangumi 卡片详情页面',                 routeName: 'BangumiDetail' },
  'tmdb-person-detail':{ label: 'TMDB 人物详情', description: 'TMDB 人物详情页面',                    routeName: 'TmdbPersonDetail' },
} as const

export type CustomizablePageKey = keyof typeof CUSTOMIZABLE_PAGES

/**
 * 外观 key → 可自定义页面 key 的多对多映射
 *
 * 一个弹框/卡片可以同时属于多个页面（如 task-history-modal 同时在
 * 任务中心和整理页面使用）。
 *
 * 映射依据：通过搜索代码中 appearance-key / data-app-instance 属性
 * 的实际使用位置确定。
 */
const APPEARANCE_KEY_PAGE_MAP: Record<string, CustomizablePageKey[]> = {
  // ===== 订阅与下载（SubscriptionViewDesktop + SubscriptionManager） =====
  'feed-edit-modal':              ['subscription'],
  'rss-rule-modal':               ['subscription'],
  'aggregated-feed-items-modal':  ['subscription'],
  'aggregated-rule-history-modal':['subscription'],
  'rule-preview-modal':           ['subscription'],
  'subscription-edit-modal':      ['subscription'],
  'subscription-detail-modal':    ['subscription'],
  'subscription-help-modal':      ['subscription'],
  'subscription-template-modal':  ['subscription'],
  'bangumi-quick-subscribe-modal':['subscription'],
  'priority-rule-modal':          ['subscription'],
  'rss-detect-manager-modal':     ['subscription'],
  'rss-detect-modal':             ['subscription'],
  'jackett-fill-modal':           ['subscription'],
  'subscription-card':            ['subscription'],
  'feed-card':                    ['subscription'],
  'rss-rule-card':                ['subscription'],
  'priority-profile-card':        ['subscription'],
  'priority-rule-card':           ['subscription'],

  // ===== 整理与重命名（OrganizerViewDesktop） =====
  'rule-edit-modal':              ['organizer'],
  'task-edit-modal':              ['organizer'],
  'execution-log-modal':          ['organizer', 'file-browser'],
  'task-history-modal':           ['organizer', 'tasks'],
  'file-picker-modal':            ['organizer', 'strm'],
  'organize-rule-card':           ['organizer'],
  'organize-task-card':           ['organizer'],

  // ===== 整理历史（OrganizeHistoryDesktop） =====
  'organize-history-card':        ['organize-history'],

  // ===== 任务中心（TaskHistoryViewDesktop） =====
  'task-history-card':            ['tasks'],

  // ===== 虚拟 STRM 库（StrmGeneratorViewDesktop） =====
  'strm-task-modal':              ['strm'],
  'strm-task-card':               ['strm'],

  // ===== 追剧日历（CalendarViewDesktop） =====
  'calendar-modal':               ['calendar'],
  'track-card':                   ['calendar'],

  // ===== 系统数据中心（DatabaseViewDesktop，含子 tab：缓存管理/元数据等） =====
  'cache-modal':                  ['database'],

  // ===== 文件浏览（FileBrowserViewDesktop） =====
  'manual-organize-modal':        ['file-browser'],
  'recognition-modal':            ['file-browser'],

  // ===== 系统数据中心（DatabaseViewDesktop，含子 tab） =====
  'tmdb-full-data-modal':         ['database'],
  'tmdb-data-card':               ['database'],
  'classifier-edit-modal':        ['database'],
  'secondary-rule-card':          ['database'],
  'user-mapping-modal':           ['database'],
  'mapping-card':                 ['database'],
  'maintenance-card':             ['database'],

  // ===== 外部控制（ExternalControlDesktop） =====
  'external-control-modal':       ['external-control'],

  // ===== 系统设置（SettingsViewDesktop + 子 tab） =====
  'client-edit-modal':            ['settings'],
  'health-check-manager-modal':   ['settings'],
  'service-status-modal':         ['settings'],
  'account-modal':                ['settings'],
  'client-card':                  ['settings'],

  // ===== 规则说明（UsageGuideDesktop → SettingsGuide） =====
  'settings-guide-modal':         ['usage-guide'],

  // ===== 全局组件（MainLayout，不绑定特定页面） =====
  'log-console-modal':            [],
}

/** 获取外观 key 所属的所有可自定义页面 key（支持多页面） */
export function getAppearanceKeyPageKeys(key: string): CustomizablePageKey[] {
  return APPEARANCE_KEY_PAGE_MAP[key] || []
}

/** 获取外观 key 所属的第一个可自定义页面 key（向后兼容） */
export function getAppearanceKeyPageKey(key: string): CustomizablePageKey | undefined {
  return APPEARANCE_KEY_PAGE_MAP[key]?.[0]
}

/** 获取指定页面下的所有外观 key（弹框 + 卡片） */
export function getAppearanceKeysByPageKey(pageKey: string): string[] {
  return Object.entries(APPEARANCE_KEY_PAGE_MAP)
    .filter(([, pks]) => pks.includes(pageKey as CustomizablePageKey))
    .map(([key]) => key)
}

/** 获取可自定义页面的下拉选项 */
export const customizablePageOptions = Object.entries(CUSTOMIZABLE_PAGES).map(([value, meta]) => ({
  label: meta.label,
  value,
}))

/** 根据路由名称获取可自定义页面 key */
export function getPageKeyByRouteName(routeName: string): CustomizablePageKey | undefined {
  for (const [key, meta] of Object.entries(CUSTOMIZABLE_PAGES)) {
    if (meta.routeName === routeName) return key as CustomizablePageKey
  }
  return undefined
}
