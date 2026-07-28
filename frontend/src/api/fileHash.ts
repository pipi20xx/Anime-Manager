/**
 * FileHash API — 文件哈希记录接口
 *
 * 对接后端 /api/file_hashes 路由:
 * - 列表查询 (q搜索, tmdb_id/media_type/season/team筛选, 排序)
 * - 单条查询 (ID/ED2K/SHA1)
 * - 计算单文件哈希并入库
 */
import { api } from './client'

export const fileHashApi = {
  /** 分页查询哈希记录 */
  getList: (params?: {
    q?: string
    tmdb_id?: string
    media_type?: string
    season?: number
    team?: string
    limit?: number
    offset?: number
    sort_by?: string
    sort_order?: string
  }) =>
    api.get<any>('/api/file_hashes', { params }),

  /** 获取单条哈希记录 */
  getDetail: (id: number) =>
    api.get<any>(`/api/file_hashes/${id}`),

  /** 按 ED2K 哈希查询 */
  getByEd2k: (ed2kHash: string) =>
    api.get<any>(`/api/file_hashes/ed2k/${ed2kHash}`),

  /** 按 SHA1 哈希查询 */
  getBySha1: (sha1Hash: string) =>
    api.get<any>(`/api/file_hashes/sha1/${sha1Hash}`),

  /** 计算单文件哈希并入库 */
  calculate: (body: {
    file_path: string
    tmdb_id?: string
    title?: string
    season?: number
    episode?: string
    media_type?: string
    resolution?: string
    team?: string
    video_encode?: string
    audio_encode?: string
    video_effect?: string
    source?: string
    subtitle?: string
    platform?: string
    year?: string
    secondary_category?: string
    origin_country?: string
    release_date?: string
  }) =>
    api.post<any>('/api/file_hashes/calculate', body),
}
