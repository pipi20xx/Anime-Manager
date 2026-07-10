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
    tab_height: 40,
    tab_gap: 4,
    tab_padding: 16,
    tab_border_radius: 8,
    tab_font_size: 14,
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
    border_radius: 8,
    height: 56,
    blur: 0,
  },
  list: {
    enabled: false,
    bg_opacity: 1,
    border_radius: 8,
    blur: 0,
  },
  button: {
    enabled: false,
    border_radius: 8,
    height_medium: 32,
    height_small: 32,
    height_tiny: 32,
    text_color: '#3B82F6',
    text_bg_hover: 'rgba(59, 130, 246, 0.1)',
    text_bg_pressed: 'rgba(59, 130, 246, 0.15)',
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
    root.style.setProperty('--tabs-tab-height', `${tabs.tab_height}px`)
    root.style.setProperty('--tabs-tab-gap', `${tabs.tab_gap}px`)
    root.style.setProperty('--tabs-tab-padding', `${tabs.tab_padding}px`)
    root.style.setProperty('--tabs-tab-border-radius', `${tabs.tab_border_radius}px`)
    root.style.setProperty('--tabs-tab-font-size', `${tabs.tab_font_size}px`)
  } else {
    root.style.setProperty('--tabs-nav-blur', 'none')
    root.style.setProperty('--tabs-nav-bg-transparent-pct', '0%')
    root.style.setProperty('--tabs-tab-active-bg', '#3b82f6')
    root.style.setProperty('--tabs-tab-active-text-color', '#ffffff')
    root.style.setProperty('--tabs-tab-height', '40px')
    root.style.setProperty('--tabs-tab-gap', '4px')
    root.style.setProperty('--tabs-tab-padding', '16px')
    root.style.setProperty('--tabs-tab-border-radius', '8px')
    root.style.setProperty('--tabs-tab-font-size', '14px')
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
    // 搜索框关闭时跟随输入框的圆角和高度
    root.style.setProperty('--search-input-border-radius', 'var(--input-border-radius)')
    root.style.setProperty('--search-input-height', 'var(--input-height)')
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

  // === 按钮外观 ===
  const button = config.button
  if (button.enabled) {
    root.style.setProperty('--btn-border-radius', `${button.border_radius}px`)
    root.style.setProperty('--btn-height-medium', `${button.height_medium}px`)
    root.style.setProperty('--btn-height-small', `${button.height_small}px`)
    root.style.setProperty('--btn-height-tiny', `${button.height_tiny}px`)
    root.style.setProperty('--btn-text-color', button.text_color)
    root.style.setProperty('--btn-text-bg-hover', button.text_bg_hover)
    root.style.setProperty('--btn-text-bg-pressed', button.text_bg_pressed)
  } else {
    root.style.setProperty('--btn-border-radius', '8px')
    root.style.setProperty('--btn-height-medium', '32px')
    root.style.setProperty('--btn-height-small', '32px')
    root.style.setProperty('--btn-height-tiny', '32px')
    root.style.setProperty('--btn-text-color', 'var(--n-primary-color)')
    root.style.setProperty('--btn-text-bg-hover', 'rgba(59, 130, 246, 0.1)')
    root.style.setProperty('--btn-text-bg-pressed', 'rgba(59, 130, 246, 0.15)')
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
    // 实例级边框样式（border_color/border_width/border_style 为实例级专用字段）
    if (c.border_color !== undefined) {
      decls.push(`--app-card-border-color: ${c.border_color};`)
    }
    if (c.border_width !== undefined) {
      decls.push(`--app-card-border-width: ${c.border_width}px;`)
    }
    if (c.border_style !== undefined) {
      decls.push(`--app-card-border-style: ${c.border_style};`)
    }
    if (c.background_opacity !== undefined) {
      // 与全局公式保持一致——控制卡片底色层（::after）的不透明度：
      //   background_opacity = 1（100%）→ 底色不透明（遮住背景图片）
      //   background_opacity = 0（0%）  → 底色透明（透出背景图片）
      decls.push(`--app-card-bg-opacity: ${Math.round(c.background_opacity * 100)}%;`)
      decls.push(`--app-card-bg-transparent-pct: ${Math.round((1 - c.background_opacity) * 100)}%;`)
      // 关键：在实例级重算 --app-surface-card-mixed
      // 该变量在 :root 处定义，会随 :root 的 --app-card-bg-transparent-pct 计算后被继承为静态值，
      // 无法跟随实例级覆盖重算。此处重新声明，让实例内所有使用它的元素（.n-card、.path-info .v、code 等）
      // 都能正确跟随实例级背景不透明度。
      decls.push(`--app-surface-card-mixed: color-mix(in srgb, var(--app-surface-card), transparent var(--app-card-bg-transparent-pct, 0%));`)
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
    if (t.tab_height !== undefined) {
      decls.push(`--tabs-tab-height: ${t.tab_height}px;`)
    }
    if (t.tab_gap !== undefined) {
      decls.push(`--tabs-tab-gap: ${t.tab_gap}px;`)
    }
    if (t.tab_padding !== undefined) {
      decls.push(`--tabs-tab-padding: ${t.tab_padding}px;`)
    }
    if (t.tab_border_radius !== undefined) {
      decls.push(`--tabs-tab-border-radius: ${t.tab_border_radius}px;`)
    }
    if (t.tab_font_size !== undefined) {
      decls.push(`--tabs-tab-font-size: ${t.tab_font_size}px;`)
    }
    // 实例级边框样式
    if (t.border_color !== undefined) {
      decls.push(`--tabs-nav-border-color: ${t.border_color};`)
    }
    if (t.border_width !== undefined) {
      decls.push(`--tabs-nav-border-width: ${t.border_width}px;`)
    }
    if (t.border_style !== undefined) {
      decls.push(`--tabs-nav-border-style: ${t.border_style};`)
    }
    // 关键：重新声明组合变量 --tabs-nav-border
    // 该变量在 :root 处定义为 width + style + color 的组合，
    // 浏览器在 :root 解析后得到静态字符串并继承给所有后代。
    // 当实例级覆盖了 border-color/width/style 后，已解析的 --tabs-nav-border 不会重算，
    // 必须在此重新声明才能让 .n-tabs-nav 的 border 跟随实例级配置。
    if (t.border_color !== undefined || t.border_width !== undefined || t.border_style !== undefined) {
      decls.push(`--tabs-nav-border: var(--tabs-nav-border-width) var(--tabs-nav-border-style) var(--tabs-nav-border-color);`)
    }
  }

  // Input
  if (overrides.input) {
    const i = overrides.input
    if (i.bg_opacity !== undefined) {
      decls.push(`--input-bg-opacity: ${Math.round(i.bg_opacity * 100)}%;`)
      decls.push(`--input-bg-transparent-pct: ${Math.round((1 - i.bg_opacity) * 100)}%;`)
      // 关键：在实例级重算 --input-label-bg
      // 该变量在 :root 处定义，会随 :root 的 --input-bg-opacity 计算后被继承为静态值，
      // 无法跟随实例级覆盖重算。此处重新声明，让输入框标签浮动时的底色能正确跟随实例级透明度。
      decls.push(`--input-label-bg: color-mix(in srgb, var(--input-bg) var(--input-bg-opacity, 100%), transparent);`)
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
    // 实例级边框样式
    if (i.border_color !== undefined) {
      decls.push(`--input-border-color: ${i.border_color};`)
    }
    if (i.border_width !== undefined) {
      decls.push(`--input-border-width: ${i.border_width}px;`)
    }
    if (i.border_style !== undefined) {
      decls.push(`--input-border-style: ${i.border_style};`)
    }
    // 关键：重新声明组合变量 --input-border
    // 该变量在 :root 处定义为 width + style + color 的组合，
    // 浏览器在 :root 解析后得到静态字符串并继承给所有后代。
    // 当实例级覆盖了 border-color/width/style 后，已解析的 --input-border 不会重算，
    // 必须在此重新声明才能让 AppTextField / AppSelectField / AppTimeField 的 border 跟随实例级配置。
    if (i.border_color !== undefined || i.border_width !== undefined || i.border_style !== undefined) {
      decls.push(`--input-border: var(--input-border-width) var(--input-border-style) var(--input-border-color);`)
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
    // 实例级边框样式
    if (s.border_color !== undefined) {
      decls.push(`--search-input-border-color: ${s.border_color};`)
    }
    if (s.border_width !== undefined) {
      decls.push(`--search-input-border-width: ${s.border_width}px;`)
    }
    if (s.border_style !== undefined) {
      decls.push(`--search-input-border-style: ${s.border_style};`)
    }
    // 关键：重新声明组合变量 --search-input-border
    // 该变量在 :root 处定义为 width + style + color 的组合，
    // 浏览器在 :root 解析后得到静态字符串并继承给所有后代。
    // 当实例级覆盖了 border-color/width/style 后，已解析的 --search-input-border 不会重算，
    // 必须在此重新声明才能让 AppSearchField 的 border 跟随实例级配置。
    if (s.border_color !== undefined || s.border_width !== undefined || s.border_style !== undefined) {
      decls.push(`--search-input-border: var(--search-input-border-width) var(--search-input-border-style) var(--search-input-border-color);`)
    }
  }

  // List
  if (overrides.list) {
    const l = overrides.list
    if (l.bg_opacity !== undefined) {
      decls.push(`--list-bg-transparent-pct: ${Math.round((1 - l.bg_opacity) * 100)}%;`)
      // 关键：在实例级重算 --app-surface-list-mixed
      // 该变量在 :root 处定义，会随 :root 的 --list-bg-transparent-pct 计算后被继承为静态值，
      // 无法跟随实例级覆盖重算。此处重新声明，让实例内所有使用它的元素（.n-data-table-td 等）
      // 都能正确跟随实例级列表背景不透明度。
      decls.push(`--app-surface-list-mixed: color-mix(in srgb, var(--app-surface-card), transparent var(--list-bg-transparent-pct, 0%));`)
    }
    if (l.border_radius !== undefined) {
      decls.push(`--list-border-radius: ${l.border_radius}px;`)
    }
    if (l.blur !== undefined) {
      decls.push(`--list-blur: ${l.blur > 0 ? `blur(${l.blur}px)` : 'none'};`)
    }
    // 实例级边框样式
    if (l.border_color !== undefined) {
      decls.push(`--list-border-color: ${l.border_color};`)
    }
    if (l.border_width !== undefined) {
      decls.push(`--list-border-width: ${l.border_width}px;`)
    }
    if (l.border_style !== undefined) {
      decls.push(`--list-border-style: ${l.border_style};`)
    }
  }

  // Button (实例级)
  if (overrides.button) {
    const b = overrides.button
    if (b.border_radius !== undefined) {
      decls.push(`--btn-border-radius: ${b.border_radius}px;`)
    }
    if (b.height_medium !== undefined) {
      decls.push(`--btn-height-medium: ${b.height_medium}px;`)
    }
    if (b.height_small !== undefined) {
      decls.push(`--btn-height-small: ${b.height_small}px;`)
    }
    if (b.height_tiny !== undefined) {
      decls.push(`--btn-height-tiny: ${b.height_tiny}px;`)
    }
    if (b.text_color !== undefined) {
      decls.push(`--btn-text-color: ${b.text_color};`)
    }
    if (b.text_bg_hover !== undefined) {
      decls.push(`--btn-text-bg-hover: ${b.text_bg_hover};`)
    }
    if (b.text_bg_pressed !== undefined) {
      decls.push(`--btn-text-bg-pressed: ${b.text_bg_pressed};`)
    }
  }

  // Text (实例级专用)
  if (overrides.text) {
    const t = overrides.text
    if (t.color !== undefined) {
      decls.push(`--app-instance-text-color: ${t.color};`)
    }
    if (t.secondary_color !== undefined) {
      decls.push(`--app-instance-text-secondary-color: ${t.secondary_color};`)
    }
    if (t.tertiary_color !== undefined) {
      decls.push(`--app-instance-text-tertiary-color: ${t.tertiary_color};`)
    }
    if (t.tint_color !== undefined) {
      decls.push(`--app-instance-text-tint-color: ${t.tint_color};`)
    }
    if (t.input_color !== undefined) {
      decls.push(`--app-instance-text-input-color: ${t.input_color};`)
    }
    if (t.shadow !== undefined) {
      decls.push(`--app-instance-text-shadow: ${t.shadow};`)
    }
    if (t.secondary_shadow !== undefined) {
      decls.push(`--app-instance-text-secondary-shadow: ${t.secondary_shadow};`)
    }
    if (t.tertiary_shadow !== undefined) {
      decls.push(`--app-instance-text-tertiary-shadow: ${t.tertiary_shadow};`)
    }
    if (t.tint_shadow !== undefined) {
      decls.push(`--app-instance-text-tint-shadow: ${t.tint_shadow};`)
    }
    if (t.input_shadow !== undefined) {
      decls.push(`--app-instance-text-input-shadow: ${t.input_shadow};`)
    }
    if (t.font_weight !== undefined) {
      decls.push(`--app-instance-text-font-weight: ${t.font_weight};`)
    }
    if (t.font_size !== undefined) {
      decls.push(`--app-instance-text-font-size: ${t.font_size}px;`)
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
  return `/* instance "${key}" 的 card 背景图层（有背景图） */
[data-app-instance="${key}"] .n-card,
[data-app-instance="${key}"].n-card {
  /* 底色移到 ::after，此处置空，避免双层背景 */
  background: transparent !important;
  /* 模糊交给 ::after，避免与底色层重复模糊 */
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  position: relative;
  overflow: hidden;
}
[data-app-instance="${key}"] .n-card::before,
[data-app-instance="${key}"].n-card::before {
  /* 图片层：始终完全显示，不透明度由上层底色(::after)控制 */
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 0, 0, var(--app-card-bg-overlay-opacity, 0)), rgba(0, 0, 0, var(--app-card-bg-overlay-opacity, 0))),
    var(--app-card-bg-image);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  z-index: 0;
  pointer-events: none;
  /* 关键：覆盖 global.css 中可能存在的 :root:not([data-card-bg="on"]) .n-card::before { display: none } */
  display: block !important;
}
[data-app-instance="${key}"] .n-card::after,
[data-app-instance="${key}"].n-card::after {
  /* 底色层：盖在图片之上，用 color-mix 控制不透明度（与 modal 一致）
     --app-card-bg-opacity = 100% → 底色不透明（遮住图片）
     --app-card-bg-opacity = 0%   → 底色透明（透出图片） */
  content: '';
  position: absolute;
  inset: 0;
  backdrop-filter: var(--app-card-blur, none);
  -webkit-backdrop-filter: var(--app-card-blur, none);
  background: color-mix(in srgb, var(--app-surface-card) var(--app-card-bg-opacity, 100%), transparent);
  z-index: 0;
  pointer-events: none;
  display: block !important;
}
[data-app-instance="${key}"] .n-card > *,
[data-app-instance="${key}"].n-card > * {
  /* 关键：把卡片内容（header/content/footer/action）抬到伪元素之上，否则会被背景图遮住 */
  position: relative;
  z-index: 1;
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

    // 3. 如果设置了 card 背景图，注入完整双伪元素背景图层
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

/** DataTable 主题覆盖 - 表头/行背景由全局 CSS（var(--app-surface-card-mixed) / var(--app-surface-list-mixed)) 控制，
 * 这里只保留边框、文字、圆角等无法通过 CSS 变量覆盖的属性。
 */
export const dataTableThemeOverrides = computed(() => {
  const cardCfg = appearanceConfig.value.card

  return {
    borderRadius: cardCfg.enabled ? `${cardCfg.border_radius}px` : undefined,
    thColor: 'transparent',
    thColorHover: 'transparent',
    thColorModal: 'transparent',
    thColorHoverModal: 'transparent',
    thColorPopover: 'transparent',
    thColorHoverPopover: 'transparent',
    tdColor: 'transparent',
    tdColorHover: 'transparent',
    tdColorModal: 'transparent',
    tdColorHoverModal: 'transparent',
    tdColorPopover: 'transparent',
    tdColorHoverPopover: 'transparent',
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
