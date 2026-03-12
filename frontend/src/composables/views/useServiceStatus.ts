import { ref, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'

interface ServiceStatus {
  id: string
  name: string
  type: 'scheduler' | 'thread'
  enabled: boolean
  running: boolean
  interval: string
  next_run: string | null
  last_run: string | null
  description: string
}

interface MonitorStatus {
  id: string
  name: string
  type: 'organize' | 'strm'
  enabled: boolean
  mode: string
  running: boolean
  source_dir: string
  target_dir: string
  queue_size: number
  webhook_enabled?: boolean
  check_emby_exists?: boolean
  calculate_hash?: boolean
}

interface RuleStats {
  local: number
  remote: number
  builtin?: number
}

interface RulesData {
  custom_noise: RuleStats
  custom_groups: RuleStats
  custom_render: RuleStats
  privileged: RuleStats
}

interface ServicesData {
  services: ServiceStatus[]
  monitors: MonitorStatus[]
  observers_count: number
  workers_count: number
  queues_count: number
  rules: RulesData
}

export function useServiceStatus() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
  
  const loading = ref(false)
  const data = ref<ServicesData>({
    services: [],
    monitors: [],
    observers_count: 0,
    workers_count: 0,
    queues_count: 0,
    rules: {
      custom_noise: { local: 0, remote: 0 },
      custom_groups: { local: 0, remote: 0 },
      custom_render: { local: 0, remote: 0 },
      privileged: { local: 0, remote: 0 }
    }
  })
  
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/services`)
      if (res.ok) {
        data.value = await res.json()
      }
    } catch (e) {
      console.error('获取服务状态失败', e)
    }
  }

  const startPolling = (interval: number = 5000) => {
    fetchStatus()
    refreshTimer = setInterval(fetchStatus, interval)
  }

  const stopPolling = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  const formatNextRun = (isoString: string | null): string => {
    if (!isoString) return '-'
    try {
      const date = new Date(isoString)
      return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return '-'
    }
  }

  const getStatusTag = (service: ServiceStatus | MonitorStatus): { type: 'success' | 'warning' | 'error' | 'default', text: string } => {
    if ('enabled' in service && !service.enabled) {
      return { type: 'default', text: '已禁用' }
    }
    if (service.running) {
      return { type: 'success', text: '运行中' }
    }
    return { type: 'warning', text: '已停止' }
  }

  onMounted(() => startPolling())
  onUnmounted(() => stopPolling())

  return {
    loading,
    data,
    fetchStatus,
    startPolling,
    stopPolling,
    formatNextRun,
    getStatusTag
  }
}
