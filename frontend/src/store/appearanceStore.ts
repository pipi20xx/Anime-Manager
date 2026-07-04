import { ref } from 'vue'
import { appearanceApi, type AppearanceConfig } from '../api/appearance'

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
    border_color: '#3B82F6',
    border_width: 1,
    border_radius: 14,
  },
  card: {
    enabled: false,
    background_image: '',
    background_opacity: 1,
    border_radius: 14,
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
    root.style.setProperty('--app-global-bg-blur', globalBg.background_blur > 0 ? `${globalBg.background_blur}px` : 'none')
    root.style.setProperty('--app-global-bg-overlay-opacity', String(globalBg.background_overlay_opacity))
    root.style.setProperty('--app-layout-opacity', `${Math.round(globalBg.layout_opacity * 100)}%`)
    root.setAttribute('data-global-bg', 'on')
  } else {
    root.style.setProperty('--app-global-bg-image', 'none')
    root.style.setProperty('--app-global-bg-blur', 'none')
    root.style.setProperty('--app-global-bg-overlay-opacity', '0.6')
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
    root.style.setProperty('--app-modal-blur', modal.background_blur > 0 ? `${modal.background_blur}px` : 'none')
    // 预计算百分比，避免 calc() 在 color-mix() 内的兼容性问题
    root.style.setProperty('--app-modal-bg-opacity-pct', `${Math.round(modal.background_opacity * 100)}%`)
    root.style.setProperty('--app-modal-bg-opacity', String(modal.background_opacity))
    root.style.setProperty('--app-modal-border-color', modal.border_color)
    root.style.setProperty('--app-modal-border-width', `${modal.border_width}px`)
    root.style.setProperty('--app-modal-border-radius', `${modal.border_radius}px`)
  } else {
    root.style.setProperty('--app-modal-bg-image', 'none')
    root.style.setProperty('--app-modal-blur', 'none')
    root.style.setProperty('--app-modal-bg-opacity-pct', '100%')
    root.style.setProperty('--app-modal-bg-opacity', '1')
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
    root.style.setProperty('--card-border-radius', `${card.border_radius}px`)
  } else {
    root.style.setProperty('--app-card-bg-image', 'none')
    root.style.setProperty('--app-card-bg-opacity', '100%')
    root.style.setProperty('--app-card-bg-transparent-pct', '0%')
    root.style.setProperty('--card-border-radius', '14px')
    root.removeAttribute('data-card-bg')
  }

  // === 标签页外观 ===
  const tabs = config.tabs
  if (tabs.enabled) {
    root.style.setProperty('--tabs-nav-blur', tabs.nav_blur > 0 ? `${tabs.nav_blur}px` : 'none')
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
    root.style.setProperty('--input-blur', input.blur > 0 ? `${input.blur}px` : 'none')
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
    root.style.setProperty('--search-input-blur', search.blur > 0 ? `${search.blur}px` : 'none')
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
    root.style.setProperty('--list-blur', list.blur > 0 ? `${list.blur}px` : 'none')
  } else {
    root.style.setProperty('--list-bg-transparent-pct', '0%')
    root.style.setProperty('--list-border-radius', '8px')
    root.style.setProperty('--list-blur', 'none')
  }
}

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
