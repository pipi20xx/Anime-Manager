import axios from 'axios'

const getHeaders = () => {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface AppearanceGlobal {
  enabled: boolean
  background_image: string
  background_blur: number
  background_overlay_opacity: number
  layout_opacity: number
}

export interface AppearanceModal {
  enabled: boolean
  background_image: string
  background_blur: number
  background_opacity: number
  background_overlay_opacity: number
  border_color: string
  border_width: number
  border_radius: number
}

export interface AppearanceCard {
  enabled: boolean
  background_image: string
  background_opacity: number
  background_overlay_opacity: number
  border_radius: number
  blur: number
}

export interface AppearanceTabs {
  enabled: boolean
  nav_blur: number
  nav_opacity: number
  tab_active_bg: string
  tab_active_text_color: string
}

export interface AppearanceInput {
  enabled: boolean
  bg_opacity: number
  border_radius: number
  height: number
  blur: number
}

export interface AppearanceSearch {
  enabled: boolean
  bg_opacity: number
  border_radius: number
  height: number
  blur: number
}

export interface AppearanceList {
  enabled: boolean
  bg_opacity: number
  border_radius: number
  blur: number
}

/**
 * 实例级文字样式：仅用于单独自定义弹框/卡片，不在全局默认中提供。
 * 所有字段 undefined 表示继承默认主题文字样式。
 */
export interface AppearanceText {
  color: string
  secondary_color: string
  /** 第三级文字色（URL、元信息、说明等更淡的文字） */
  tertiary_color: string
  /** 彩色底色上的文字色（状态标签、徽章等） */
  tint_color: string
  /** 输入框/搜索框/下拉框中自己输入或已选中的文字色 */
  input_color: string
  /** 文字主色阴影 */
  shadow: string
  /** 次要文字色阴影 */
  secondary_shadow: string
  /** 第三文字色阴影 */
  tertiary_shadow: string
  /** 彩色底色文字色阴影 */
  tint_shadow: string
  /** 输入文字色阴影 */
  input_shadow: string
  font_weight: number
  font_size: number
}

/**
 * 实例级覆盖：每个字段的 undefined 表示"继承全局默认"
 * 仅填写需要覆盖的字段，未填写的字段会自动继承 :root 全局变量值
 */
export interface AppearanceInstanceOverrides {
  modal?: Partial<AppearanceModal>
  card?: Partial<AppearanceCard>
  /** 文字样式：仅实例级覆盖，全局默认不做文字样式调整 */
  text?: Partial<AppearanceText>
  tabs?: Partial<AppearanceTabs>
  input?: Partial<AppearanceInput>
  search?: Partial<AppearanceSearch>
  list?: Partial<AppearanceList>
}

export interface AppearanceConfig {
  global: AppearanceGlobal
  modal: AppearanceModal
  card: AppearanceCard
  tabs: AppearanceTabs
  input: AppearanceInput
  search: AppearanceSearch
  list: AppearanceList
  /** 实例级覆盖：key 对应组件的 appearance-key，value 为该组件的独立配置 */
  instances?: Record<string, AppearanceInstanceOverrides>
}

export interface AppearanceImage {
  filename: string
  size: number
}

export const appearanceApi = {
  getConfig: () =>
    axios.get<AppearanceConfig>('/api/appearance/config', { headers: getHeaders() }),

  updateConfig: (config: Partial<AppearanceConfig>) =>
    axios.put<{ success: boolean; appearance: AppearanceConfig }>('/api/appearance/config', config, { headers: getHeaders() }),

  uploadImage: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return axios.post<{ success: boolean; filename: string }>('/api/appearance/upload', formData, {
      headers: { ...getHeaders(), 'Content-Type': 'multipart/form-data' }
    })
  },

  deleteImage: (filename: string) =>
    axios.delete<{ success: boolean }>(`/api/appearance/image/${filename}`, { headers: getHeaders() }),

  listImages: () =>
    axios.get<AppearanceImage[]>('/api/appearance/images', { headers: getHeaders() }),

  getImageUrl: (filename: string) => `/api/appearance/image/${filename}`
}
