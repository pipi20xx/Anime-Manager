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

  /** 修正单条记录的季号/集号/TMDB ID (传 null 清空) */
  updateInfo: (id: number, body: { season: number | null; episode: string | null; tmdb_id: string | null }) =>
    api.patch<any>(`/api/file_hashes/${id}`, body),

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

  /** 一键修复标题：根据 TMDBID 和类型从数据中心补全标题 */
  fixTitles: (body?: {
    ids?: number[]
    q?: string
    tmdb_id?: string
    media_type?: string
    season?: number
    team?: string
  }) =>
    api.post<any>('/api/file_hashes/fix_titles', body || {}),

  /** 重新识别：按源路径重跑识别并覆盖季集/TMDB ID/标题/识别信息 */
  reRecognize: (body?: {
    ids?: number[]
    q?: string
    tmdb_id?: string
    media_type?: string
    season?: number
    team?: string
  }) =>
    api.post<any>('/api/file_hashes/re_recognize', body || {}),
}
