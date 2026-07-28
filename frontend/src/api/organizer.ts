/**
 * Organizer API — 文件整理接口
 */
import { api, apiFetch } from './client'

/** 获取认证头 */
function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || ''

export const organizerApi = {
  /** 列出目录文件 */
  listFiles: (body: { path: string; recursive?: boolean }) =>
    api.post<any>('/api/files/list', body),

  /** 删除文件或目录 */
  deleteFile: (body: { path: string }) =>
    api.post<any>('/api/files/delete', body),

  /** 复制文件或目录 */
  copyFile: (body: { src: string; dst: string }) =>
    api.post<any>('/api/files/copy', body),

  /** 移动/重命名文件或目录 */
  moveFile: (body: { src: string; dst: string }) =>
    api.post<any>('/api/files/move', body),

  /** 获取文件详情 */
  getFileInfo: (body: { path: string }) =>
    api.post<any>('/api/files/info', body),

  /** 重命名预览 */
  renamePreview: (body: any) =>
    api.post<any>('/api/rename/preview', body),

/** 启动后台整理任务 */
startBackground: (body: any, opts?: { dry_run?: boolean }) =>
  api.post<any>('/api/organize/start_background', body, { params: opts }),

  /** 获取后台任务列表 */
  getBackgroundTasks: () =>
    api.get<any>('/api/organize/background_tasks'),

  /** 停止后台任务 */
  stopBackgroundTask: (taskId: string) =>
    api.get<any>(`/api/organize/stop`, { params: { task_id: taskId } }),

  /** 删除后台任务记录 */
  deleteBackgroundTask: (taskId: string) =>
    api.delete<any>(`/api/organize/background_tasks/${taskId}`),

  /** 获取整理配置 */
  getConfig: () => api.get<any>('/api/config'),

  /** 保存整理配置 */
  saveConfig: (body: any) => api.post<any>('/api/config', body),

  // --- 整理历史 ---
  /** 分页获取整理历史 */
  getHistory: (params?: { limit?: number; offset?: number; status?: string; search?: string }) =>
    api.get<any>('/api/organize/history', { params }),

  /** 删除单条整理历史 */
  deleteHistory: (historyId: number, deleteFile = false) =>
    api.delete<any>(`/api/organize/history/${historyId}`, { params: { delete_file: deleteFile } }),

  /** 清空整理历史 */
  clearHistory: () =>
    api.delete<any>('/api/organize/history/clear'),

  /** 重试单条整理历史 */
  retryHistory: (historyId: number) =>
    api.post<any>(`/api/organize/history/${historyId}/retry`),

  /** 单项全流程重算 */
  recalculateItem: (body: any) =>
    api.post<any>('/api/organize/recalculate', body),

  // --- Stream-based execution (for FileBrowser) ---
  /** Ad-hoc 流式整理 (dry_run) — 返回 Response 流 */
  streamAdhoc: (body: any, params?: { dry_run?: boolean }) =>
    fetch(`${API_BASE_URL}/api/organize/stream_adhoc?dry_run=${params?.dry_run ?? true}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    }),

  /** 流式执行整理 (返回 Response 流) */
  streamExecute: (body: any) =>
    fetch(`${API_BASE_URL}/api/organize/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    }),
}
