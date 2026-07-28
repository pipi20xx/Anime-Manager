/**
 * Clients API — 下载客户端接口
 */
import { api } from './client'

export const clientsApi = {
  /** 获取所有客户端 */
  getClients: () => api.get<any[]>('/api/clients'),

  /** 保存客户端（批量） */
  saveClients: (clients: any[]) => api.post<any>('/api/clients', clients),

  /** 删除客户端（通过保存不含该客户端的列表实现） */
  deleteClient: async (id: string) => {
    const all = await clientsApi.getClients()
    const filtered = all.filter((c: any) => c.id !== id)
    return clientsApi.saveClients(filtered)
  },

  /** 测试客户端连接 */
  testClient: (body: any) => api.post<any>('/api/clients/test', body),

  /** 手动下载任务 */
  manualDownload: (body: { client_id: string; url: string; save_path?: string; category?: string; tags?: string }) =>
    api.post<any>('/api/clients/download', body),

  /** 获取 Jackett 站点列表 */
  getJackettIndexers: () => api.get<any[]>('/api/jackett/indexers'),
}
