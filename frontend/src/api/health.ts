/**
 * Health Check API — 掉盘与失效检测接口
 */
import { api } from './client'

export const healthApi = {
  /** 获取所有健康检查配置 */
  getConfigs: () => api.get<any[]>('/api/health/configs'),

  /** 创建健康检查配置 */
  createConfig: (body: any) => api.post<any>('/api/health/configs', body),

  /** 更新健康检查配置 */
  updateConfig: (id: number, body: any) => api.put<any>(`/api/health/configs/${id}`, body),

  /** 删除健康检查配置 */
  deleteConfig: (id: number) => api.delete<any>(`/api/health/configs/${id}`),

  /** 触发单个检查 */
  triggerCheck: (id: number) => api.post<any>(`/api/health/check/${id}`),

  /** 触发全部检查 */
  triggerCheckAll: () => api.post<any>('/api/health/check_all'),
}
