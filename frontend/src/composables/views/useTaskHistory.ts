import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useGroupedLogs } from '../useGroupedLogs'
import { useEventStream } from '../useEventStream'

export function useTaskHistory() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const tasks = ref<any[]>([])
  const loading = ref(false)
  const selectedTask = ref<any>(null)
  const showLogModal = ref(false)

  const { groupedLogs: selectedTaskGroupedLogs } = useGroupedLogs(selectedTask)
  const moduleFilter = ref('all')
  const searchQuery = ref('')
  
  const page = ref(0)
  const pageSize = ref(20)
  const hasMore = ref(true)
  
  let _unsubscribeEvents: (() => void) | null = null
  let _unsubscribeLogStream: (() => void) | null = null

  // WebSocket 事件流：实时接收任务记录变更推送，替代轮询
  const { on: onEvent } = useEventStream()

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
      const searchParam = searchQuery.value ? `&search=${encodeURIComponent(searchQuery.value)}` : ''
      const res = await fetch(`${API_BASE}/api/task_history?limit=${pageSize.value}&offset=${offset}${moduleParam}${searchParam}`)
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

  const subscribeTaskLogs = (taskId: string) => {
    unsubscribeTaskLogs()
    _unsubscribeLogStream = onEvent('task_log', (data: any) => {
      if (data?.task_id === taskId && selectedTask.value) {
        // 追加实时日志，触发响应式更新
        const logs = [...(selectedTask.value.logs || []), data.log]
        selectedTask.value = { ...selectedTask.value, logs }
      }
    })
  }

  const unsubscribeTaskLogs = () => {
    if (_unsubscribeLogStream) {
      _unsubscribeLogStream()
      _unsubscribeLogStream = null
    }
  }

  const fetchTaskDetail = async (taskId: string) => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/task_history/${taskId}`)
      selectedTask.value = await res.json()
      showLogModal.value = true
      // 任务运行中：订阅实时日志流
      if (selectedTask.value?.status === 'running') {
        subscribeTaskLogs(taskId)
      }
    } catch (e) {
      message.error('获取任务详情失败')
    } finally {
      loading.value = false
    }
  }

  // 弹窗关闭时取消日志流订阅
  watch(showLogModal, (val) => {
    if (!val) {
      unsubscribeTaskLogs()
    }
  })

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
    // 订阅 WS 事件：任务记录变更时刷新列表
    if (!_unsubscribeEvents) {
      _unsubscribeEvents = onEvent('task_record', () => {
        fetchTasks()
      })
    }
  }

  const stopPolling = () => {
    if (_unsubscribeEvents) {
      _unsubscribeEvents()
      _unsubscribeEvents = null
    }
    unsubscribeTaskLogs()
  }

  const getStatusTag = (status: string) => {
    const map: Record<string, { style: any, label: string }> = {
      completed: { style: { color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }, label: '完成' },
      running: { style: { color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }, label: '运行中' },
      error: { style: { color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' }, label: '错误' },
      stopped: { style: { color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' }, label: '已停止' }
    }
    return map[status] || { style: { color: '#fff', backgroundColor: '#616161', borderColor: 'transparent' }, label: status }
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
      if (stats.mode) parts.push(stats.mode)
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
    } else if (module === '识别') {
      const parts = []
      if (stats.title) parts.push(stats.title)
      if (stats.tmdb_id) parts.push(`ID:${stats.tmdb_id}`)
      if (stats.category) parts.push(stats.category)
      // 剧集显示季集信息
      if (stats.category === '剧集') {
        const season = stats.season != null ? String(stats.season).padStart(2, '0') : null
        const episode = stats.episode != null ? String(stats.episode).padStart(2, '0') : null
        if (season && episode) parts.push(`S${season}E${episode}`)
        else if (season) parts.push(`S${season}`)
        else if (episode) parts.push(`E${episode}`)
      }
      return parts.join(' | ') || null
    }
    return null
  }

  const moduleOptions = computed(() => {
    return ['all', '整理', 'STRM', 'RSS', '识别', '规则同步', '订阅补全', '死种清理', 'Webhook联动']
  })

  return {
    API_BASE,
    tasks,
    loading,
    selectedTask,
    selectedTaskGroupedLogs,
    showLogModal,
    moduleFilter,
    searchQuery,
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
