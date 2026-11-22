/**
 * 壁纸管理 API
 *
 * 对应后端 /api/appearance/wallpaper/* 端点。
 * 壁纸按访问设备区分：pc（电脑端）/ mobile（移动端），各自独立配置与历史图库。
 */

import { api } from './client'

// ── 类型定义 ──────────────────────────────────────────────

export type WallpaperSourceType = 'api' | 'url' | 'upload' | 'history'

export type WallpaperDisplayMode = 'latest' | 'rotation'

/** 壁纸配置维度：电脑端 / 移动端 */
export type WallpaperDevice = 'pc' | 'mobile'

/** API 源 / 历史条目可适用的设备（any = 两端通用） */
export type WallpaperSourceDevice = WallpaperDevice | 'any'

export interface WallpaperApiSource {
  id: string
  name: string
  url: string
  category: 'acg' | 'general'
  orientation: 'landscape' | 'portrait' | 'any'
  /** 该源适用的设备：pc 仅电脑端 / mobile 仅移动端 / any 两端通用 */
  device: WallpaperSourceDevice
  is_random: boolean
}

export interface WallpaperConfig {
  source_type: WallpaperSourceType
  api_source_id: string
  custom_url: string
  upload_filename: string
  history_filename: string
  /** 后台自动下载新图的间隔（秒），与显示模式无关 */
  refresh_interval: number
  /** 显示方式：latest 跟随最新 | rotation 图库轮播 */
  display_mode: WallpaperDisplayMode
  /** 图库轮播间隔（秒），仅 display_mode=rotation 时使用 */
  rotation_interval: number
  /** 轮播范围：包含历史图库 */
  rotation_include_history: boolean
  /** 轮播范围：包含上传壁纸 */
  rotation_include_uploads: boolean
}

export interface WallpaperUpload {
  filename: string
  size: number
  created_at?: number
}

export interface WallpaperHistory {
  filename: string
  size: number
  created_at: number
  /** 收录设备；旧版本迁移的条目可能为 any（通用） */
  device?: WallpaperSourceDevice
  source_type: string
  source_id: string
  source_url: string
}

function deviceQuery(device?: WallpaperDevice) {
  return device ? { params: { device } } : undefined
}

// ── API 调用 ──────────────────────────────────────────────

export const appearanceApi = {
  /** 获取可用的壁纸 API 源列表（按设备过滤：设备专属源 + 通用源） */
  getSources: (device?: WallpaperDevice) =>
    api.get<{ sources: WallpaperApiSource[] }>('/api/appearance/wallpaper/sources', deviceQuery(device)),

  /** 获取某设备的壁纸配置 */
  getConfig: (device?: WallpaperDevice) =>
    api.get<WallpaperConfig>('/api/appearance/wallpaper/config', deviceQuery(device)),

  /** 更新某设备的壁纸配置（只影响该设备） */
  updateConfig: (config: Partial<WallpaperConfig>, device?: WallpaperDevice) =>
    api.put<{ success: boolean; config: WallpaperConfig }>(
      '/api/appearance/wallpaper/config',
      config,
      deviceQuery(device),
    ),

  /** 列出手动上传的壁纸图片（两端共用图库） */
  listUploads: async (): Promise<WallpaperUpload[]> => {
    const res = await api.get<WallpaperUpload[] | { images?: WallpaperUpload[] }>('/api/appearance/wallpaper/uploads')
    if (Array.isArray(res)) return res
    return res.images ?? []
  },

  /** 列出自动收录的历史壁纸图片（按设备过滤） */
  listHistory: async (device?: WallpaperDevice): Promise<WallpaperHistory[]> => {
    const res = await api.get<WallpaperHistory[] | { history?: WallpaperHistory[] }>(
      '/api/appearance/wallpaper/history',
      deviceQuery(device),
    )
    if (Array.isArray(res)) return res
    return res.history ?? []
  },

  /** 上传壁纸图片 */
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ success: boolean; filename: string }>('/api/appearance/wallpaper/upload', formData)
  },

  /** 删除已上传的壁纸图片 */
  deleteUpload: (filename: string) =>
    api.delete<{ success: boolean }>(`/api/appearance/wallpaper/uploads/${encodeURIComponent(filename)}`),

  /** 删除历史壁纸图片 */
  deleteHistory: (filename: string) =>
    api.delete<{ success: boolean }>(`/api/appearance/wallpaper/history/${encodeURIComponent(filename)}`),

  /** 构建壁纸代理 URL（不传 url 时后端按 device 从配置读取壁纸源） */
  buildProxyUrl: (sourceUrl?: string, isRandom?: boolean, device?: WallpaperDevice): string => {
    const params = new URLSearchParams()
    if (sourceUrl) params.set('url', sourceUrl)
    if (isRandom) params.set('_ts', String(Date.now()))
    if (device) params.set('device', device)
    const query = params.toString()
    return query ? `/api/appearance/wallpaper_proxy?${query}` : '/api/appearance/wallpaper_proxy'
  },
}
