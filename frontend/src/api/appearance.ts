/**
 * Appearance API — 外观配置接口
 */
import { api } from './client'

export const appearanceApi = {
  /** 获取配置 */
  getConfig: () => api.get<any>('/api/appearance/config'),

  /** 更新配置 */
  updateConfig: (body: any) => api.put<any>('/api/appearance/config', body),

  /** 上传图片 */
  uploadImage: (formData: FormData) =>
    api.post<any>('/api/appearance/upload', formData),

  /** 获取图片 */
  getImage: (filename: string) => `/api/appearance/image/${filename}`,

  /** 删除图片 */
  deleteImage: (filename: string) =>
    api.delete<any>(`/api/appearance/image/${filename}`),

  /** 获取所有图片列表 */
  getImages: () => api.get<any>('/api/appearance/images'),
}
