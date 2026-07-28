/**
 * Config API — 系统配置接口
 */
import { api } from './client'

export const configApi = {
  /** 获取完整配置 */
  getConfig: () => api.get<any>('/api/config'),

  /** 保存配置 */
  saveConfig: (body: any) => api.post<any>('/api/config', body),

  /** 同步远程规则库 */
  refreshRemoteRules: () => api.post<any>('/api/refresh_remote_rules'),
}
