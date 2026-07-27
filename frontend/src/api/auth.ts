import { api } from './client'
import type { LoginParams, LoginResponse } from '@/types'

export const authApi = {
  login: (params: LoginParams) =>
    api.post<LoginResponse>('/api/auth/login', params),

  me: () =>
    api.get<{ username: string }>('/api/auth/me'),
}
