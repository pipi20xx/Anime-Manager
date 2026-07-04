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
  border_color: string
  border_width: number
  border_radius: number
}

export interface AppearanceCard {
  enabled: boolean
  background_image: string
  background_opacity: number
  border_radius: number
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

export interface AppearanceConfig {
  global: AppearanceGlobal
  modal: AppearanceModal
  card: AppearanceCard
  tabs: AppearanceTabs
  input: AppearanceInput
  search: AppearanceSearch
  list: AppearanceList
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
