/**
 * Recognition API — 识别接口
 */
import { api } from './client'

export const recognitionApi = {
  /** 全链路识别 */
  recognize: (body: any) => api.post<any>('/api/recognize', body),

  /** 获取剧集季度详情 */
  getTvDetail: (tmdbId: string | number) =>
    api.get<any>(`/api/tmdb/tv/${tmdbId}`),

  /** AI 实验室：语义解析测试 */
  testAi: (body: any) => api.post<any>('/api/ai/test', body),

  /** 特权集数锁定测试 */
  testPrivilege: (body: any) => api.post<any>('/api/privilege/test', body),

  /** 获取内置特权规则列表 */
  getPrivilegeRules: () => api.get<any>('/api/privilege/rules'),
}
