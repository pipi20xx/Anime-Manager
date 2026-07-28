/**
 * Strm API — STRM 生成接口
 */
import { api } from './client'

export const strmApi = {
  /** 获取 STRM 配置 */
  getConfig: () => api.get<any>('/api/strm/config'),

  /** 保存 STRM 配置 */
  saveConfig: (body: any) => api.post<any>('/api/strm/config', body),

  /** 生成 STRM 文件（直接执行，流式返回） */
  generate: (body: any) => api.post<any>('/api/strm/execute', body),

  /** 预览 STRM 内容 */
  preview: (body: any) => api.post<any>('/api/strm/preview', body),

  /** 通过任务 ID 后台运行 */
  runTask: (taskId: string) => api.post<any>(`/api/strm/run/${taskId}`),

  /** 获取 STRM 任务列表 */
  getTasks: () => api.get<any>('/api/strm/tasks'),
}
