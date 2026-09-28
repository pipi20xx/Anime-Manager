/**
 * Scheduler API — 任务计划（定时任务统一管理）接口
 */
import { api } from './client'

export interface SchedulerLastRun {
  task_id: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  processed: number
}

export interface BuiltinExtraParam {
  key: string
  label: string
  type: 'number' | 'text' | 'select'
  min?: number
  max?: number
  default?: any
  hint?: string
  options?: { title: string; value: any }[]
  value: any
}

export interface SchedulerJob {
  job_id: string
  name: string
  module: string
  description: string
  schedule_desc: string
  enabled?: boolean
  scheduled: boolean
  locked: boolean
  editable: boolean
  can_run: boolean
  schedule_type?: 'interval' | 'daily' | 'fixed'
  cron?: string | null
  cron_source?: 'override' | 'default' | null
  extra_params?: BuiltinExtraParam[] | null
  next_run: string | null
  last_run: SchedulerLastRun | null
}

export interface SchedulerAction {
  action: string
  name: string
  module: string
  description: string
  params_schema?: BuiltinExtraParam[] | null
}

export interface CustomScheduledJob {
  id: number
  name: string
  action: string
  action_name: string
  module: string
  cron: string
  schedule_desc: string
  params: Record<string, any> | null
  enabled: boolean
  scheduled: boolean
  next_run: string | null
  last_run: SchedulerLastRun | null
}

export interface CustomJobBody {
  name?: string
  action: string
  cron: string
  params?: Record<string, any> | null
  enabled: boolean
}

export interface CronPreview {
  cron: string
  desc: string
  next_runs: string[]
}

export const schedulerApi = {
  /** 获取所有系统内置定时任务及状态 */
  getJobs: () => api.get<{ jobs: SchedulerJob[] }>('/api/scheduler/jobs'),

  /** 启用/停用系统内置定时任务 */
  toggleJob: (jobId: string, enabled: boolean) =>
    api.post<any>(`/api/scheduler/jobs/${jobId}/toggle`, { enabled }),

  /** 修改系统内置定时任务的周期/开关（cron 覆盖 + 附加参数） */
  updateJob: (jobId: string, body: { enabled?: boolean; cron?: string; extra?: Record<string, number> }) =>
    api.put<any>(`/api/scheduler/jobs/${jobId}`, body),

  /** 预览 cron 表达式的未来触发时间 */
  cronPreview: (cron: string) =>
    api.post<CronPreview>('/api/scheduler/cron/preview', { cron }),

  /** 立即手动执行系统内置定时任务 */
  runJob: (jobId: string) =>
    api.post<any>(`/api/scheduler/jobs/${jobId}/run`),

  /** 获取可选的任务动作目录 */
  getActions: () => api.get<{ actions: SchedulerAction[] }>('/api/scheduler/actions'),

  /** 获取自定义定时任务列表 */
  getCustomJobs: () => api.get<{ jobs: CustomScheduledJob[] }>('/api/scheduler/custom'),

  /** 创建自定义定时任务 */
  createCustomJob: (body: CustomJobBody) =>
    api.post<any>('/api/scheduler/custom', body),

  /** 修改自定义定时任务 */
  updateCustomJob: (id: number, body: CustomJobBody) =>
    api.put<any>(`/api/scheduler/custom/${id}`, body),

  /** 删除自定义定时任务 */
  deleteCustomJob: (id: number) =>
    api.delete<any>(`/api/scheduler/custom/${id}`),

  /** 启用/停用自定义定时任务 */
  toggleCustomJob: (id: number, enabled: boolean) =>
    api.post<any>(`/api/scheduler/custom/${id}/toggle`, { enabled }),

  /** 立即执行自定义定时任务 */
  runCustomJob: (id: number) =>
    api.post<any>(`/api/scheduler/custom/${id}/run`),
}
