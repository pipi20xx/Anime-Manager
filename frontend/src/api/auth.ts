/**
 * Auth API — 认证接口
 */
import { api } from './client'

export const authApi = {
  /** 登录 */
  login: (params: { username: string; password: string; otp_code?: string }) =>
    api.post<any>('/api/auth/login', params),

  /** 获取当前用户信息 */
  me: () => api.get<any>('/api/auth/me'),

  /** 修改密码 */
  changePassword: (body: { old_password: string; new_password: string }) =>
    api.post<any>('/api/auth/password', body),

  /** 获取会话列表 */
  getSessions: () => api.get<any>('/api/auth/sessions'),

  /** 删除指定会话 */
  deleteSession: (id: number) => api.delete<any>(`/api/auth/sessions/${id}`),

  /** 删除所有其他会话 */
  deleteAllSessions: () => api.delete<any>('/api/auth/sessions'),

  /** 2FA 设置初始化 */
  setup2fa: () => api.get<any>('/api/auth/2fa/setup'),

  /** 启用 2FA */
  enable2fa: (code: string) => api.post<any>(`/api/auth/2fa/enable?code=${code}`),

  /** 禁用 2FA */
  disable2fa: () => api.post<any>('/api/auth/2fa/disable'),
}
