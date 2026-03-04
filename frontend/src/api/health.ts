import axios from 'axios'

export interface HealthCheckConfig {
  id?: number
  name: string
  file_path: str
  file_url: str
  enabled: boolean
  last_status?: string
  last_check?: string
  created_at?: string
}

const getHeaders = () => {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const healthApi = {
  getConfigs: () => axios.get<HealthCheckConfig[]>('/api/health/configs', { headers: getHeaders() }),
  createConfig: (config: HealthCheckConfig) => axios.post<HealthCheckConfig>('/api/health/configs', config, { headers: getHeaders() }),
  updateConfig: (id: number, config: HealthCheckConfig) => axios.put<HealthCheckConfig>(`/api/health/configs/${id}`, config, { headers: getHeaders() }),
  deleteConfig: (id: number) => axios.delete(`/api/health/configs/${id}`, { headers: getHeaders() }),
  triggerCheck: (id: number) => axios.post(`/api/health/check/${id}`, {}, { headers: getHeaders() }),
  triggerCheckAll: () => axios.post('/api/health/check_all', {}, { headers: getHeaders() })
}
