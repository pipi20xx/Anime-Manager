// 类型统一导出
export * from './shared'

// 业务特有类型
export interface LoginParams {
  username: string
  password: string
  otp_code?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  status?: string
}

export interface VersionCheckResponse {
  latest_version: string
  cached: boolean
  cache_age_seconds?: number
  error?: string
}
