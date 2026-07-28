/**
 * TaskHistory API — 任务执行历史接口
 */
import { api } from './client'

export const taskHistoryApi = {
  /** 获取任务历史列表 */
  getTaskList: (params?: { limit?: number; offset?: number; module?: string; search?: string }) =>
    api.get<any>('/api/task_history', { params }),

  /** 获取单个任务的完整执行日志 */
  getTaskDetail: (taskId: string) =>
    api.get<any>(`/api/task_history/${taskId}`),

  /** 删除单个任务记录 */
  deleteTask: (taskId: string) =>
    api.delete<any>(`/api/task_history/${taskId}`),

  /** 清理旧任务记录 */
  cleanup: (params?: { max_records?: number; max_days?: number }) =>
    api.delete<any>('/api/task_history', { params }),
}
