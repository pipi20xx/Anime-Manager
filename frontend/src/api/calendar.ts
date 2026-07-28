/**
 * Calendar API — 追剧日历接口
 *
 * 对接后端 /api/calendar 路由:
 * - 追踪番剧管理 (CRUD)
 * - 从放送表导入
 * - 批量导入
 * - 刷新追踪项
 * - 清理过期项
 * - 每日播报配置
 * - 测试推送
 */
import { api } from './client'

export const calendarApi = {
  /** 获取追踪番剧列表 */
  getSubjects: () =>
    api.get<any>('/api/calendar/subjects'),

  /** 添加追踪番剧 */
  addSubject: (body: { tmdb_id: string; media_type?: string; title?: string; season?: number }) =>
    api.post<any>('/api/calendar/subjects', body),

  /** 更新追踪番剧 */
  updateSubject: (id: number, body: { title?: string; season?: number }) =>
    api.put<any>(`/api/calendar/subjects/${id}`, body),

  /** 删除追踪番剧 */
  deleteSubject: (id: number) =>
    api.delete<any>(`/api/calendar/subjects/${id}`),

  /** 刷新单个追踪番剧的放送日期 */
  refreshSubject: (id: number) =>
    api.post<any>(`/api/calendar/subjects/${id}/refresh`),

  /** 刷新所有追踪番剧 */
  refreshAllSubjects: () =>
    api.post<any>('/api/calendar/subjects/refresh_all'),

  /** 清理过期追踪项 */
  clearExpired: () =>
    api.delete<any>('/api/calendar/subjects/expired'),

  /** 从 Bangumi 放送表导入单个番剧 */
  importBangumi: (bgmId: string | number) =>
    api.post<any>(`/api/calendar/import_bangumi/${bgmId}`),

  /** 批量导入 Bangumi 放送表番剧 */
  batchImportBangumi: (ids: (string | number)[]) =>
    api.post<any>('/api/calendar/batch_import_bangumi', ids),

  /** 测试推送播报 */
  testPush: () =>
    api.post<any>('/api/calendar/test_push'),
}
