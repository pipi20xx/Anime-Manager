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

export interface AppearanceButton {
  enabled: boolean
  /** 按钮圆角（px） */
  border_radius: number
  /** medium 尺寸按钮高度（px） */
  height_medium: number
  /** small 尺寸按钮高度（px） */
  height_small: number
  /** tiny 尺寸按钮高度（px） */
  height_tiny: number
  /** 纯文字按钮（ghost/quaternary）文字颜色 */
  text_color: string
  /** 纯文字按钮 hover 底色 */
  text_bg_hover: string
  /** 纯文字按钮 pressed 底色 */
  text_bg_pressed: string
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
 * 实例级边框样式扩展：仅用于单独自定义弹框/卡片，不在全局默认中提供。
 * 所有字段 undefined 表示继承默认边框样式。
 */
export interface InstanceBorderOverrides {
  /** 边框颜色 */
  border_color?: string
  /** 边框宽度（px） */
  border_width?: number
  /** 边框样式：solid / dashed / dotted / double / groove / ridge / inset / outset / none */
  border_style?: string
}

/**
 * 实例级覆盖：每个字段的 undefined 表示"继承全局默认"
 * 仅填写需要覆盖的字段，未填写的字段会自动继承 :root 全局变量值
 *
 * 边框样式（border_color/border_width/border_style）为实例级专用字段，
 * 全局默认不做此配置，仅在单独自定义弹框/卡片中支持。
 */
export interface AppearanceInstanceOverrides {
  modal?: Partial<AppearanceModal>
  card?: Partial<AppearanceCard> & InstanceBorderOverrides
  /** 文字样式：仅实例级覆盖，全局默认不做文字样式调整 */
  text?: Partial<AppearanceText>
  tabs?: Partial<AppearanceTabs> & InstanceBorderOverrides
  input?: Partial<AppearanceInput> & InstanceBorderOverrides
  search?: Partial<AppearanceSearch> & InstanceBorderOverrides
  list?: Partial<AppearanceList> & InstanceBorderOverrides
  button?: Partial<AppearanceButton>
}

export interface AppearanceConfig {
  global: AppearanceGlobal
  modal: AppearanceModal
  card: AppearanceCard
  tabs: AppearanceTabs
  input: AppearanceInput
  search: AppearanceSearch
  list: AppearanceList
  button: AppearanceButton
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

  getImageUrl: (filename: string) => `/api/appearance/image/${filename}`,

  getImageBlob: (filename: string) =>
    axios.get<Blob>(`/api/appearance/image/${filename}`, {
      headers: getHeaders(),
      responseType: 'blob'
    })
}
