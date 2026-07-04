import { ref, computed } from 'vue'
import { appearanceApi, type AppearanceConfig, type AppearanceInstanceOverrides } from '../api/appearance'
import { currentThemeConfig } from './themeStore'

// 默认外观配置
const defaultConfig: AppearanceConfig = {
  global: {
    enabled: false,
    background_image: '',
    background_blur: 0,
    background_overlay_opacity: 0.6,
    layout_opacity: 0.9,
  },
  modal: {
    enabled: false,
    background_image: '',
    background_blur: 0,
    background_opacity: 1,
    background_overlay_opacity: 0,
    border_color: '#3B82F6',
    border_width: 1,
    border_radius: 14,
  },
  card: {
    enabled: false,
    background_image: '',
    background_opacity: 1,
    background_overlay_opacity: 0,
    border_radius: 14,
    blur: 0,
  },
  tabs: {
    enabled: false,
    nav_blur: 0,
    nav_opacity: 1,
    tab_active_bg: '#3b82f6',
    tab_active_text_color: '#ffffff',
  },
  input: {
    enabled: false,
    bg_opacity: 1,
    border_radius: 8,
    height: 56,
    blur: 0,
  },
  search: {
    enabled: false,
    bg_opacity: 1,
    border_radius: 22,
    height: 44,
    blur: 0,
  },
  list: {
    enabled: false,
    bg_opacity: 1,
    border_radius: 8,
    blur: 0,
  },
  // 实例级覆盖：key 对应组件的 appearance-key
  // 默认为空对象，未列出的组件走全局默认
  instances: {},
}

export const appearanceConfig = ref<AppearanceConfig>(JSON.parse(JSON.stringify(defaultConfig)))
export const appearanceLoaded = ref(false)

/** 将配置应用到 CSS 变量，同时更新响应式 appearanceConfig */
export function applyAppearanceToCss(config: AppearanceConfig) {
  // 同步更新响应式引用，让依赖 appearanceConfig.value 的 computed 能响应
  appearanceConfig.value = JSON.parse(JSON.stringify(config))
  const root = document.documentElement

  // === 全局背景 ===
  const globalBg = config.global
  if (globalBg.enabled && globalBg.background_image) {
    root.style.setProperty('--app-global-bg-image', `url(/api/appearance/image/${globalBg.background_image})`)
    root.style.setProperty('--app-global-bg-blur', globalBg.background_blur > 0 ? `blur(${globalBg.background_blur}px)` : 'none')
    root.style.setProperty('--app-global-bg-overlay-opacity', String(globalBg.background_overlay_opacity))
    root.style.setProperty('--app-layout-opacity', `${Math.round(globalBg.layout_opacity * 100)}%`)
    root.setAttribute('data-global-bg', 'on')
  } else {
    root.style.setProperty('--app-global-bg-image', 'none')
    root.style.setProperty('--app-global-bg-blur', 'none')
    root.style.setProperty('--app-global-bg-overlay-opacity', '0.6')
    // 未启用全局背景时，布局不透明（100% = 不透明，与侧边栏逻辑一致）
    root.style.setProperty('--app-layout-opacity', '100%')
    root.removeAttribute('data-global-bg')
  }

  // === 弹框外观 ===
  const modal = config.modal
  if (modal.enabled) {
    if (modal.background_image) {
      root.style.setProperty('--app-modal-bg-image', `url(/api/appearance/image/${modal.background_image})`)
      root.setAttribute('data-modal-bg', 'on')
    } else {
      root.style.setProperty('--app-modal-bg-image', 'none')
      root.removeAttribute('data-modal-bg')
    }
    root.style.setProperty('--app-modal-blur', modal.background_blur > 0 ? `blur(${modal.background_blur}px)` : 'none')
    // 预计算百分比，避免 calc() 在 color-mix() 内的兼容性问题
    root.style.setProperty('--app-modal-bg-opacity-pct', `${Math.round(modal.background_opacity * 100)}%`)
    root.style.setProperty('--app-modal-bg-opacity', String(modal.background_opacity))
    root.style.setProperty('--app-modal-bg-overlay-opacity', String(modal.background_overlay_opacity))
    root.style.setProperty('--app-modal-border-color', modal.border_color)
    root.style.setProperty('--app-modal-border-width', `${modal.border_width}px`)
    root.style.setProperty('--app-modal-border-radius', `${modal.border_radius}px`)
  } else {
    root.style.setProperty('--app-modal-bg-image', 'none')
    root.style.setProperty('--app-modal-blur', 'none')
    root.style.setProperty('--app-modal-bg-opacity-pct', '100%')
    root.style.setProperty('--app-modal-bg-opacity', '1')
    root.style.setProperty('--app-modal-bg-overlay-opacity', '0')
    root.style.setProperty('--app-modal-border-color', '#3B82F6')
    root.style.setProperty('--app-modal-border-width', '1px')
    root.style.setProperty('--app-modal-border-radius', '14px')
    root.removeAttribute('data-modal-bg')
  }

  // === 卡片外观 ===
  const card = config.card
  if (card.enabled) {
    if (card.background_image) {
      root.style.setProperty('--app-card-bg-image', `url(/api/appearance/image/${card.background_image})`)
      root.setAttribute('data-card-bg', 'on')
    } else {
      root.style.setProperty('--app-card-bg-image', 'none')
      root.removeAttribute('data-card-bg')
    }
    root.style.setProperty('--app-card-bg-opacity', `${Math.round(card.background_opacity * 100)}%`)
    root.style.setProperty('--app-card-bg-transparent-pct', `${Math.round((1 - card.background_opacity) * 100)}%`)
    root.style.setProperty('--app-card-bg-overlay-opacity', String(card.background_overlay_opacity))
    root.style.setProperty('--card-border-radius', `${card.border_radius}px`)
    root.style.setProperty('--app-card-blur', card.blur > 0 ? `blur(${card.blur}px)` : 'none')
  } else {
    root.style.setProperty('--app-card-bg-image', 'none')
    root.style.setProperty('--app-card-bg-opacity', '100%')
    root.style.setProperty('--app-card-bg-transparent-pct', '0%')
    root.style.setProperty('--app-card-bg-overlay-opacity', '0')
    root.style.setProperty('--card-border-radius', '14px')
    root.style.setProperty('--app-card-blur', 'none')
    root.removeAttribute('data-card-bg')
  }

  // === 标签页外观 ===
  const tabs = config.tabs
  if (tabs.enabled) {
    root.style.setProperty('--tabs-nav-blur', tabs.nav_blur > 0 ? `blur(${tabs.nav_blur}px)` : 'none')
    // 预计算透明度百分比，避免 calc() 在 color-mix() 里的兼容性问题
    const transparentPct = Math.round((1 - tabs.nav_opacity) * 100)
    root.style.setProperty('--tabs-nav-bg-transparent-pct', `${transparentPct}%`)
    root.style.setProperty('--tabs-tab-active-bg', tabs.tab_active_bg)
    root.style.setProperty('--tabs-tab-active-text-color', tabs.tab_active_text_color)
  } else {
    root.style.setProperty('--tabs-nav-blur', 'none')
    root.style.setProperty('--tabs-nav-bg-transparent-pct', '0%')
    root.style.setProperty('--tabs-tab-active-bg', '#3b82f6')
    root.style.setProperty('--tabs-tab-active-text-color', '#ffffff')
  }

  // === 输入框外观 ===
  const input = config.input
  if (input.enabled) {
    const inputTransparentPct = Math.round((1 - input.bg_opacity) * 100)
    root.style.setProperty('--input-bg-opacity', `${Math.round(input.bg_opacity * 100)}%`)
    root.style.setProperty('--input-bg-transparent-pct', `${inputTransparentPct}%`)
    root.style.setProperty('--input-border-radius', `${input.border_radius}px`)
    root.style.setProperty('--input-height', `${input.height}px`)
    root.style.setProperty('--input-blur', input.blur > 0 ? `blur(${input.blur}px)` : 'none')
  } else {
    root.style.setProperty('--input-bg-opacity', '100%')
    root.style.setProperty('--input-bg-transparent-pct', '0%')
    root.style.setProperty('--input-border-radius', '8px')
    root.style.setProperty('--input-height', '56px')
    root.style.setProperty('--input-blur', 'none')
  }

  // === 搜索框外观 ===
  const search = config.search
  if (search.enabled) {
    const searchTransparentPct = Math.round((1 - search.bg_opacity) * 100)
    root.style.setProperty('--search-input-bg-opacity', `${Math.round(search.bg_opacity * 100)}%`)
    root.style.setProperty('--search-input-bg-transparent-pct', `${searchTransparentPct}%`)
    root.style.setProperty('--search-input-bg-transparent-pct-hover', `${Math.min(100, Math.round(searchTransparentPct * 0.85))}%`)
    root.style.setProperty('--search-input-bg-transparent-pct-focus', `${Math.min(100, Math.round(searchTransparentPct * 0.92))}%`)
    root.style.setProperty('--search-input-border-radius', `${search.border_radius}px`)
    root.style.setProperty('--search-input-height', `${search.height}px`)
    root.style.setProperty('--search-input-blur', search.blur > 0 ? `blur(${search.blur}px)` : 'none')
  } else {
    root.style.setProperty('--search-input-bg-opacity', '100%')
    root.style.setProperty('--search-input-bg-transparent-pct', '0%')
    root.style.setProperty('--search-input-bg-transparent-pct-hover', '0%')
    root.style.setProperty('--search-input-bg-transparent-pct-focus', '0%')
    root.style.setProperty('--search-input-border-radius', '22px')
    root.style.setProperty('--search-input-height', '44px')
    root.style.setProperty('--search-input-blur', 'none')
  }

  // === 列表外观 ===
  const list = config.list
  if (list.enabled) {
    const listTransparentPct = Math.round((1 - list.bg_opacity) * 100)
    root.style.setProperty('--list-bg-transparent-pct', `${listTransparentPct}%`)
    root.style.setProperty('--list-border-radius', `${list.border_radius}px`)
    root.style.setProperty('--list-blur', list.blur > 0 ? `blur(${list.blur}px)` : 'none')
  } else {
    root.style.setProperty('--list-bg-transparent-pct', '0%')
    root.style.setProperty('--list-border-radius', '8px')
    root.style.setProperty('--list-blur', 'none')
  }

  // === 实例级覆盖 ===
  applyInstanceOverrides(config)
}

// ============= 实例级 scoped CSS 注入 =============
// 通过 <style id="app-instance-overrides"> 动态注入 scoped CSS 变量与伪元素规则，
// 让每个声明了 appearanceKey 的组件可以独立覆盖全局默认外观
const INSTANCE_STYLE_ID = 'app-instance-overrides'

function getOrCreateInstanceStyleEl(): HTMLStyleElement {
  let el = document.getElementById(INSTANCE_STYLE_ID) as HTMLStyleElement | null
  if (!el) {
    el = document.createElement('style')
    el.id = INSTANCE_STYLE_ID
    document.head.appendChild(el)
  }
  return el
}

/** 把单个 instance 的覆盖配置转换为 CSS 声明字符串数组 */
function buildInstanceDecls(overrides: AppearanceInstanceOverrides): string[] {
  const decls: string[] = []

  // Modal
  if (overrides.modal) {
    const m = overrides.modal
    if (m.background_image !== undefined) {
      decls.push(`--app-modal-bg-image: ${m.background_image ? `url(/api/appearance/image/${m.background_image})` : 'none'};`)
    }
    if (m.background_blur !== undefined) {
      decls.push(`--app-modal-blur: ${m.background_blur > 0 ? `blur(${m.background_blur}px)` : 'none'};`)
    }
    if (m.background_opacity !== undefined) {
      decls.push(`--app-modal-bg-opacity-pct: ${Math.round(m.background_opacity * 100)}%;`)
      decls.push(`--app-modal-bg-opacity: ${m.background_opacity};`)
    }
    if (m.background_overlay_opacity !== undefined) {
      decls.push(`--app-modal-bg-overlay-opacity: ${m.background_overlay_opacity};`)
    }
    if (m.border_color !== undefined) {
      decls.push(`--app-modal-border-color: ${m.border_color};`)
    }
    if (m.border_width !== undefined) {
      decls.push(`--app-modal-border-width: ${m.border_width}px;`)
    }
    if (m.border_radius !== undefined) {
      decls.push(`--app-modal-border-radius: ${m.border_radius}px;`)
    }
  }

  // Card
  if (overrides.card) {
    const c = overrides.card
    if (c.background_image !== undefined) {
      decls.push(`--app-card-bg-image: ${c.background_image ? `url(/api/appearance/image/${c.background_image})` : 'none'};`)
    }
    if (c.background_opacity !== undefined) {
      decls.push(`--app-card-bg-opacity: ${Math.round(c.background_opacity * 100)}%;`)
      decls.push(`--app-card-bg-transparent-pct: ${Math.round((1 - c.background_opacity) * 100)}%;`)
    }
    if (c.background_overlay_opacity !== undefined) {
      decls.push(`--app-card-bg-overlay-opacity: ${c.background_overlay_opacity};`)
    }
    if (c.border_radius !== undefined) {
      decls.push(`--card-border-radius: ${c.border_radius}px;`)
    }
    if (c.blur !== undefined) {
      decls.push(`--app-card-blur: ${c.blur > 0 ? `blur(${c.blur}px)` : 'none'};`)
    }
  }

  // Tabs
  if (overrides.tabs) {
    const t = overrides.tabs
    if (t.nav_blur !== undefined) {
      decls.push(`--tabs-nav-blur: ${t.nav_blur > 0 ? `blur(${t.nav_blur}px)` : 'none'};`)
    }
    if (t.nav_opacity !== undefined) {
      decls.push(`--tabs-nav-bg-transparent-pct: ${Math.round((1 - t.nav_opacity) * 100)}%;`)
    }
    if (t.tab_active_bg !== undefined) {
      decls.push(`--tabs-tab-active-bg: ${t.tab_active_bg};`)
    }
    if (t.tab_active_text_color !== undefined) {
      decls.push(`--tabs-tab-active-text-color: ${t.tab_active_text_color};`)
    }
  }

  // Input
  if (overrides.input) {
    const i = overrides.input
    if (i.bg_opacity !== undefined) {
      decls.push(`--input-bg-opacity: ${Math.round(i.bg_opacity * 100)}%;`)
      decls.push(`--input-bg-transparent-pct: ${Math.round((1 - i.bg_opacity) * 100)}%;`)
    }
    if (i.border_radius !== undefined) {
      decls.push(`--input-border-radius: ${i.border_radius}px;`)
    }
    if (i.height !== undefined) {
      decls.push(`--input-height: ${i.height}px;`)
    }
    if (i.blur !== undefined) {
      decls.push(`--input-blur: ${i.blur > 0 ? `blur(${i.blur}px)` : 'none'};`)
    }
  }

  // Search
  if (overrides.search) {
    const s = overrides.search
    if (s.bg_opacity !== undefined) {
      const pct = Math.round((1 - s.bg_opacity) * 100)
      decls.push(`--search-input-bg-opacity: ${Math.round(s.bg_opacity * 100)}%;`)
      decls.push(`--search-input-bg-transparent-pct: ${pct}%;`)
      decls.push(`--search-input-bg-transparent-pct-hover: ${Math.min(100, Math.round(pct * 0.85))}%;`)
      decls.push(`--search-input-bg-transparent-pct-focus: ${Math.min(100, Math.round(pct * 0.92))}%;`)
    }
    if (s.border_radius !== undefined) {
      decls.push(`--search-input-border-radius: ${s.border_radius}px;`)
    }
    if (s.height !== undefined) {
      decls.push(`--search-input-height: ${s.height}px;`)
    }
    if (s.blur !== undefined) {
      decls.push(`--search-input-blur: ${s.blur > 0 ? `blur(${s.blur}px)` : 'none'};`)
    }
  }

  // List
  if (overrides.list) {
    const l = overrides.list
    if (l.bg_opacity !== undefined) {
      decls.push(`--list-bg-transparent-pct: ${Math.round((1 - l.bg_opacity) * 100)}%;`)
    }
    if (l.border_radius !== undefined) {
      decls.push(`--list-border-radius: ${l.border_radius}px;`)
    }
    if (l.blur !== undefined) {
      decls.push(`--list-blur: ${l.blur > 0 ? `blur(${l.blur}px)` : 'none'};`)
    }
  }

  return decls
}

/** 为设置了 modal 背景图的 instance 输出背景图层伪元素规则（与 global.css 等价但作用域为 instance） */
function buildModalBgLayerRules(key: string): string {
  return `/* instance "${key}" 的 modal 背景图层 */
[data-app-instance="${key}"].n-modal,
[data-app-instance="${key}"] .n-modal {
  background: transparent !important;
  position: relative;
  overflow: hidden;
}
[data-app-instance="${key}"].n-modal::before,
[data-app-instance="${key}"] .n-modal::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 0, 0, var(--app-modal-bg-overlay-opacity, 0)), rgba(0, 0, 0, var(--app-modal-bg-overlay-opacity, 0))),
    var(--app-modal-bg-image);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: 0;
  pointer-events: none;
  /* 关键：覆盖 global.css 中 :root:not([data-modal-bg="on"]) ... .n-modal::before { display: none } */
  display: block !important;
}
[data-app-instance="${key}"].n-modal::after,
[data-app-instance="${key}"] .n-modal::after {
  content: '';
  position: absolute;
  inset: 0;
  backdrop-filter: var(--app-modal-blur, none);
  -webkit-backdrop-filter: var(--app-modal-blur, none);
  background: color-mix(in srgb, var(--app-modal-bg) var(--app-modal-bg-opacity-pct, 100%), transparent);
  z-index: 0;
  pointer-events: none;
  display: block !important;
}
[data-app-instance="${key}"].n-modal > *,
[data-app-instance="${key}"] .n-modal > * {
  position: relative;
  z-index: 1;
}`
}

/** 为设置了 card 背景图的 instance 输出卡片背景图层伪元素规则 */
function buildCardBgLayerRules(key: string): string {
  return `/* instance "${key}" 的 card 背景图层 */
[data-app-instance="${key}"] .n-card,
[data-app-instance="${key}"].n-card {
  position: relative;
  overflow: hidden;
}
[data-app-instance="${key}"] .n-card::before,
[data-app-instance="${key}"].n-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 0, 0, var(--app-card-bg-overlay-opacity, 0)), rgba(0, 0, 0, var(--app-card-bg-overlay-opacity, 0))),
    var(--app-card-bg-image);
  background-size: cover;
  background-position: center;
  z-index: 0;
  pointer-events: none;
  opacity: var(--app-card-bg-opacity, 1);
}`
}

/** 把实例级覆盖配置注入到 <style id="app-instance-overrides"> 标签 */
function applyInstanceOverrides(config: AppearanceConfig) {
  const styleEl = getOrCreateInstanceStyleEl()
  const instances = config.instances

  if (!instances || Object.keys(instances).length === 0) {
    styleEl.textContent = ''
    return
  }

  const rules: string[] = []

  for (const [key, overrides] of Object.entries(instances)) {
    // 1. 变量声明块（仅输出明确设置的字段，未设置的字段自动继承 :root）
    const decls = buildInstanceDecls(overrides)
    if (decls.length > 0) {
      rules.push(`[data-app-instance="${key}"] {\n  ${decls.join('\n  ')}\n}`)
    }

    // 2. 如果设置了 modal 背景图，需要触发背景图层显示
    //    （global.css 的 :root[data-modal-bg="on"] 规则只对全局生效，instance scope 需要单独注入等价规则）
    if (overrides.modal?.background_image) {
      rules.push(buildModalBgLayerRules(key))
    }

    // 3. 如果设置了 card 背景图，类似处理
    if (overrides.card?.background_image) {
      rules.push(buildCardBgLayerRules(key))
    }
  }

  styleEl.textContent = rules.join('\n\n')
}

/** hex 转 rgba */
function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** DataTable 主题覆盖 - 跟随「卡片外观」+「列表外观」设置
 * 注意：直接绑定到 <n-data-table :theme-overrides="...">，
 * 不需要外层 DataTable 键（那种结构是给 n-config-provider 用的）
 *
 * 字段名注意：
 * - card 配置用 `background_opacity`
 * - list 配置用 `bg_opacity`
 */
export const dataTableThemeOverrides = computed(() => {
  const cardCfg = appearanceConfig.value.card
  const listCfg = appearanceConfig.value.list
  const bgPrimary = currentThemeConfig.value?.bgPrimary || '#1e1e2e'
  const innerBg = currentThemeConfig.value?.bgSecondary || '#2a2a3e'

  // 表格容器背景跟随卡片外观（card 用 background_opacity）
  const tableBgAlpha = cardCfg.enabled ? cardCfg.background_opacity : 1
  // 行背景跟随列表外观（list 用 bg_opacity）
  const rowBgAlpha = listCfg.enabled ? listCfg.bg_opacity : 1
  const rowHoverAlpha = listCfg.enabled ? Math.min(1, listCfg.bg_opacity + 0.08) : 1

  return {
    borderRadius: cardCfg.enabled ? `${cardCfg.border_radius}px` : undefined,
    thColor: hexToRgba(innerBg, tableBgAlpha),
    thColorHover: hexToRgba(innerBg, Math.min(1, tableBgAlpha + 0.05)),
    thColorModal: hexToRgba(innerBg, tableBgAlpha),
    thColorHoverModal: hexToRgba(innerBg, Math.min(1, tableBgAlpha + 0.05)),
    thColorPopover: hexToRgba(innerBg, tableBgAlpha),
    thColorHoverPopover: hexToRgba(innerBg, Math.min(1, tableBgAlpha + 0.05)),
    tdColor: hexToRgba(bgPrimary, rowBgAlpha),
    tdColorHover: hexToRgba(bgPrimary, rowHoverAlpha),
    tdColorModal: hexToRgba(bgPrimary, rowBgAlpha),
    tdColorHoverModal: hexToRgba(bgPrimary, rowHoverAlpha),
    tdColorPopover: hexToRgba(bgPrimary, rowBgAlpha),
    tdColorHoverPopover: hexToRgba(bgPrimary, rowHoverAlpha),
    borderColor: 'var(--app-border-light)',
    thTextColor: 'var(--text-primary)',
    tdTextColor: 'var(--text-primary)',
    thFontWeight: '600',
  }
})

/** 从后端加载配置并应用 */
export async function loadAppearanceConfig() {
  try {
    const res = await appearanceApi.getConfig()
    const merged = deepMerge(JSON.parse(JSON.stringify(defaultConfig)), res.data || {})
    appearanceConfig.value = merged
    applyAppearanceToCss(merged)
    appearanceLoaded.value = true
  } catch (e) {
    console.warn('外观配置加载失败，使用默认值', e)
    applyAppearanceToCss(defaultConfig)
    appearanceLoaded.value = true
  }
}

/** 保存配置到后端并应用 */
export async function saveAppearanceConfig(config: Partial<AppearanceConfig>) {
  const res = await appearanceApi.updateConfig(config)
  if (res.data.success) {
    appearanceConfig.value = res.data.appearance
    applyAppearanceToCss(res.data.appearance)
  }
  return res.data
}

/** 重置为默认配置 */
export async function resetAppearanceConfig() {
  const res = await appearanceApi.updateConfig(defaultConfig)
  if (res.data.success) {
    appearanceConfig.value = JSON.parse(JSON.stringify(defaultConfig))
    applyAppearanceToCss(defaultConfig)
  }
  return res.data
}

/** 深度合并 */
function deepMerge(base: any, override: any): any {
  const result = { ...base }
  for (const key of Object.keys(override)) {
    if (key in result && typeof result[key] === 'object' && result[key] !== null && typeof override[key] === 'object' && override[key] !== null) {
      result[key] = deepMerge(result[key], override[key])
    } else {
      result[key] = override[key]
    }
  }
  return result
}
