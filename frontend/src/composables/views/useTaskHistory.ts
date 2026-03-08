import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useTaskHistory() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const tasks = ref<any[]>([])
  const loading = ref(false)
  const selectedTask = ref<any>(null)
  const showLogModal = ref(false)
  const moduleFilter = ref('all')
  
  const page = ref(0)
  const pageSize = ref(20)
  const hasMore = ref(true)
  
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const fetchData = async (isRefresh = false) => {
    if (loading.value) return
    if (isRefresh) {
      page.value = 0
      hasMore.value = true
    }
    
    if (!hasMore.value) return

    loading.value = true
    try {
      const offset = page.value * pageSize.value
      const moduleParam = moduleFilter.value !== 'all' ? `&module=${encodeURIComponent(moduleFilter.value)}` : ''
      const res = await fetch(`${API_BASE}/api/task_history?limit=${pageSize.value}&offset=${offset}${moduleParam}`)
      const data = await res.json()
      
      if (isRefresh) {
        tasks.value = data
      } else {
        tasks.value.push(...data)
      }
      
      if (data.length < pageSize.value) {
        hasMore.value = false
      } else {
        page.value++
      }
    } catch (e) {
      console.error('获取任务列表失败', e)
    } finally {
      loading.value = false
    }
  }

  const loadMore = () => {
    fetchData(false)
  }

  const fetchTasks = () => {
    fetchData(true)
  }

  const fetchTaskDetail = async (taskId: string) => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/task_history/${taskId}`)
      selectedTask.value = await res.json()
      showLogModal.value = true
    } catch (e) {
      message.error('获取任务详情失败')
    } finally {
      loading.value = false
    }
  }

  const deleteTask = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/task_history/${taskId}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('任务记录已删除')
        await fetchTasks()
      }
    } catch (e) {
      message.error('删除失败')
    }
  }

  const cleanupTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/task_history`, { method: 'DELETE' })
      const data = await res.json()
      if (data.status === 'success') {
        message.success(data.message)
        await fetchTasks()
      }
    } catch (e) {
      message.error('清理失败')
    }
  }

  const startPolling = () => {
    fetchTasks()
    pollTimer = setInterval(fetchTasks, 5000)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  const getStatusTag = (status: string) => {
    const map: Record<string, { type: 'success' | 'error' | 'warning' | 'info' | 'default', label: string }> = {
      completed: { type: 'success', label: '完成' },
      running: { type: 'info', label: '运行中' },
      error: { type: 'error', label: '错误' },
      stopped: { type: 'warning', label: '已停止' }
    }
    return map[status] || { type: 'default', label: status }
  }

  const getModuleIcon = (module: string) => {
    return ''
  }

  const formatTime = (iso: string | null) => {
    if (!iso) return '-'
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return '-'
    const s = new Date(start).getTime()
    const e = new Date(end).getTime()
    const sec = Math.floor((e - s) / 1000)
    if (sec < 60) return `${sec}秒`
    if (sec < 3600) return `${Math.floor(sec / 60)}分${sec % 60}秒`
    return `${Math.floor(sec / 3600)}时${Math.floor((sec % 3600) / 60)}分`
  }

  const getTaskStats = (task: any) => {
    const stats = task.stats || {}
    const module = task.module
    
    if (module === 'RSS') {
      const parts = []
      if (stats.total_feeds) parts.push(`${stats.total_feeds}个源`)
      if (stats.total_items) parts.push(`${stats.total_items}项`)
      if (stats.total_matched) parts.push(`${stats.total_matched}项匹配`)
      return parts.join(' | ')
    } else if (module === '整理') {
      const parts = []
      if (stats.success) parts.push(`成功${stats.success}`)
      if (stats.skipped) parts.push(`跳过${stats.skipped}`)
      if (stats.errors) parts.push(`失败${stats.errors}`)
      return parts.join(' | ')
    } else if (module === '死种清理') {
      if (stats.total_stalled) return `清理${stats.total_stalled}个`
    } else if (module === 'STRM') {
      const parts = []
      if (stats.success) parts.push(`成功${stats.success}`)
      if (stats.skipped) parts.push(`跳过${stats.skipped}`)
      if (stats.errors) parts.push(`失败${stats.errors}`)
      return parts.join(' | ')
    } else if (module === '规则同步') {
      const parts = []
      if (stats.total) parts.push(`共${stats.total}条`)
      if (stats.noise) parts.push(`噪声${stats.noise}`)
      if (stats.groups) parts.push(`制作组${stats.groups}`)
      if (stats.render) parts.push(`渲染${stats.render}`)
      if (stats.privileged) parts.push(`特权${stats.privileged}`)
      return parts.join(' | ')
    } else if (module === '订阅补全') {
      if (stats.total_pushed) return `推送${stats.total_pushed}项`
    }
    return null
  }

  const moduleOptions = computed(() => {
    return ['all', '整理', 'STRM', 'RSS', '元数据', '规则同步', '订阅补全', '死种清理', 'Webhook联动']
  })

  return {
    API_BASE,
    tasks,
    loading,
    selectedTask,
    showLogModal,
    moduleFilter,
    hasMore,
    fetchData,
    loadMore,
    fetchTasks,
    fetchTaskDetail,
    deleteTask,
    cleanupTasks,
    startPolling,
    stopPolling,
    getStatusTag,
    getModuleIcon,
    formatTime,
    formatDuration,
    getTaskStats,
    moduleOptions
  }
}
