/**
 * System API — 系统管理接口
 */
import { api } from './client'

export const systemApi = {
  /** 获取版本信息 */
  getVersion: () => api.get<any>('/api/system/version'),

  /** 检查更新 */
  checkUpdate: () => api.get<any>('/api/system/check_update'),

  /** 触发更新 */
  triggerUpdate: (body?: any) => api.post<any>('/api/system/update', body),

  /** 获取系统健康状态 */
  getHealth: () => api.get<any>('/api/system/health'),

  /** 获取系统日志 */
  getLogs: (params?: { level?: string; limit?: number }) =>
    api.get<any>('/api/system/logs', { params }),

  /** 触发死种超时清理 */
  stalledCheck: () => api.post<any>('/api/system/stalled_check'),

  /** TMDB 图片本地代理 */
  getImageProxy: (path: string) => `/api/system/img?path=${path}`,

  /** Bangumi 图片本地代理 */
  getBgmImageProxy: (url: string) => `/api/system/bgm_img?url=${encodeURIComponent(url)}`,

  /** 测试 Telegram 通知 */
  testTelegram: (body?: any) => api.post<any>('/api/system/telegram/test', body),

  /** 列出数据库表 */
  getDbTables: () => api.get<any>('/api/system/db/tables'),

  /** 执行 SQL 查询 */
  queryDb: (body: { sql: string }) => api.post<any>('/api/system/db/query', body),

  /** 获取表信息 */
  getDbTableInfo: (tableName: string) => api.get<any>(`/api/system/db/table_info/${tableName}`),
}
