/**
 * Notifications API — 通知中心（发送记录）接口
 */
import { api } from './client'

export const notificationsApi = {
  /** 获取通知记录列表 */
  list: (params?: { limit?: number; offset?: number; event_type?: string; status?: string }) =>
    api.get<any>('/api/notifications', { params }),

  /** 删除单条通知记录 */
  remove: (id: number) => api.delete<any>(`/api/notifications/${id}`),

  /** 清空全部通知记录 */
  clear: () => api.delete<any>('/api/notifications'),
}
