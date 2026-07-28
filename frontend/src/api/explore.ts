/**
 * Explore API — 番剧探索
 */
import { api } from './client'

export const exploreApi = {
  /** 获取筛选配置（按数据源） */
  getConfig: (source?: string) =>
    api.get<any>('/api/explore/config', { params: source ? { source } : undefined }),

  /** 通用发现查询 */
  getList: (params?: Record<string, any>) => api.get<any>('/api/explore/list', { params }),

  /** 手动综合搜索（同时搜索 TMDB + Bangumi） */
  search: (keyword: string) =>
    api.get<any>('/api/explore/search', { params: { keyword } }),
}
