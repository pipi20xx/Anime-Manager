/**
 * Cache API — 缓存管理接口
 */
import { api } from './client'

export const cacheApi = {
  /** 清空黑名单 */
  clearBlacklist: () => api.post<any>('/api/cache/clear_blacklist'),
}
