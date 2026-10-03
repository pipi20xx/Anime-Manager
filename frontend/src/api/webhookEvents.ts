/**
 * WebhookEvents API — 联动记录（Webhook 事件台账）接口
 */
import { api } from './client'

export interface WebhookEvent {
  id: number
  event_key: string
  action: string
  file_path: string
  is_dir: boolean
  sources: string[]
  payload: any
  status: string // pending / processing / success / failed / unmatched
  error_message: string | null
  attempts: number
  dup_count: number
  parent_event_id: number | null
  task_id: string | null
  related_task_ids: string[]
  first_seen_at: string | null
  last_event_at: string | null
  updated_at: string | null
}

export interface WebhookEventStats {
  by_status: Record<string, number>
  total: number
  today_total: number
  today_failed: number
}

export const webhookEventsApi = {
  /** 获取联动记录列表 */
  list: (params?: {
    limit?: number
    offset?: number
    status?: string
    source?: string
    search?: string
    start_time?: string
    end_time?: string
    parent_id?: number
  }) => api.get<any>('/api/linkage_events', { params }),

  /** 获取统计信息（状态分布 + 今日） */
  stats: () => api.get<WebhookEventStats>('/api/linkage_events/stats'),

  /** 获取单条记录详情 */
  get: (id: number) => api.get<WebhookEvent>(`/api/linkage_events/${id}`),

  /** 获取事件全链路执行日志（webhook 接收任务 + 队列处理/目录展开任务） */
  getLogs: (id: number) =>
    api.get<{ tasks: Array<{
      task_id: string
      module: string
      name: string
      status: string
      started_at: string | null
      logs: Array<{ time: string; level: string; message: string }>
    }> }>(`/api/linkage_events/${id}/logs`),

  /** 手动重放事件 */
  replay: (id: number) => api.post<any>(`/api/linkage_events/${id}/replay`),

  /** 批量重放当前筛选结果（与列表筛选条件一致，串行执行） */
  replayAll: (params?: {
    status?: string
    source?: string
    search?: string
    start_time?: string
    end_time?: string
    limit?: number
  }) => api.post<any>('/api/linkage_events/replay_all', null, { params }),

  /** 删除单条记录 */
  remove: (id: number) => api.delete<any>(`/api/linkage_events/${id}`),

  /** 批量清理 */
  clear: (params?: { status?: string; before_days?: number }) =>
    api.post<any>('/api/linkage_events/clear', null, { params }),
}
