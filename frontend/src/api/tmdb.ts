/**
 * TMDB API — TMDB 数据接口
 */
import { api } from './client'

export const tmdbApi = {
  /** 获取动漫趋势 */
  getTrending: (params?: { page?: number }) => api.get<any>('/api/tmdb/trending', { params }),

  /** 获取二次元分类榜单 */
  getPopular: (mediaType: string, params?: Record<string, any>) =>
    api.get<any>(`/api/tmdb/popular/${mediaType}`, { params }),

  /** 获取作品详细元数据 */
  getDetail: (mediaType: string, tmdbId: string | number) =>
    api.get<any>(`/api/tmdb/detail/${mediaType}/${tmdbId}`),

  /** 获取作品在 Emby 库中的状态 */
  getEmbyStatus: (mediaType: string, tmdbId: string | number) =>
    api.get<any>(`/api/tmdb/detail/${mediaType}/${tmdbId}/emby`),

  /** 获取推荐内容 */
  getRecommendations: (mediaType: string, tmdbId: string | number) =>
    api.get<any>(`/api/tmdb/recommendations/${mediaType}/${tmdbId}`),

  /** 获取季度集信息 */
  getSeason: (tmdbId: string | number, seasonNumber: number) =>
    api.get<any>(`/api/tmdb/season/${tmdbId}/${seasonNumber}`),

  /** 获取季度集的 Emby 库信息 */
  getSeasonEmby: (tmdbId: string | number, seasonNumber: number) =>
    api.get<any>(`/api/tmdb/season/${tmdbId}/${seasonNumber}/emby`),

  /** 搜索 TMDB 条目 */
  search: (params: { query: string; type?: string; page?: number }) =>
    api.get<any>('/api/tmdb/search', { params }),

  /** 获取人物详情 */
  getPerson: (personId: string | number) =>
    api.get<any>(`/api/tmdb/person/${personId}`),

  /** 获取人物参演作品 */
  getPersonCredits: (personId: string | number) =>
    api.get<any>(`/api/tmdb/person/${personId}/credits`),

  /** 同步 Emby 库索引 */
  syncEmbyIndex: () => api.post<any>('/api/tmdb/emby/sync-index'),
}
