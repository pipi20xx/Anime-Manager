/**
 * Bangumi API — Bangumi 数据接口
 */
import { api } from './client'

export const bangumiApi = {
  /** 获取每日放送表 */
  getCalendar: () => api.get<any>('/api/bangumi/calendar'),

  /** 获取本地日历 */
  getCalendarLocal: () => api.get<any>('/api/bangumi/calendar_local'),

  /** 获取季度番剧列表 */
  getSeasonal: (params?: Record<string, any>) => api.get<any>('/api/bangumi/seasonal', { params }),

  /** 获取增强版追剧日历 */
  getCalendarFull: () => api.get<any>('/api/bangumi/calendar/full'),

  /** 获取条目详情 */
  getSubject: (subjectId: string | number) =>
    api.get<any>(`/api/bangumi/subject/${subjectId}`),

  /** 获取条目章节列表 */
  getSubjectEpisodes: (subjectId: string | number) =>
    api.get<any>(`/api/bangumi/subject/${subjectId}/episodes`),

  /** Bangumi 匹配 TMDB */
  matchTmdb: (subjectId: string | number) =>
    api.get<any>(`/api/bangumi/match_tmdb/${subjectId}`),

  /** 一键快速订阅 */
  oneClickSubscribe: (subjectId: string | number, body?: any) =>
    api.post<any>(`/api/bangumi/one_click_subscribe/${subjectId}`, body),

  /** 批量订阅每日放送 */
  batchSubscribe: (body: any) => api.post<any>('/api/bangumi/batch_subscribe', body),

  /** 获取 BangumiData 表统计 */
  getMappingStats: () => api.get<any>('/api/bangumi/mapping/stats'),

  /** 从 bangumi-data 同步映射 */
  syncMapping: (force?: boolean) =>
    api.post<any>('/api/bangumi/mapping/sync', undefined, { params: force !== undefined ? { force } : undefined }),

  /** 预热 Bangumi Subject 缓存 */
  warmup: (force?: boolean) =>
    api.post<any>('/api/bangumi/mapping/warmup', undefined, { params: force !== undefined ? { force } : undefined }),

  /** 查询缓存预热进度 */
  getWarmupStatus: () => api.get<any>('/api/bangumi/mapping/warmup/status'),

  /** 查询映射 */
  lookupMapping: (bgmId: string | number) =>
    api.get<any>(`/api/bangumi/mapping/lookup/${bgmId}`),
}
