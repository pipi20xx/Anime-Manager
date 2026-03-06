import axios from 'axios'

const getHeaders = () => {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface VersionCheckResponse {
  latest_version: string
  cached: boolean
  cache_age_seconds?: number
  error?: string
}

export const systemApi = {
  checkVersion: () => axios.get<VersionCheckResponse>('/api/system/version/check', { headers: getHeaders() })
}