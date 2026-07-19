import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useGroupedLogs } from '../useGroupedLogs'
import { useEventStream } from '../useEventStream'

export function useOrganizeHistory() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const history = ref<any[]>([])
  const searchQuery = ref('')
  const statusFilter = ref('all') // all, success, failed, skipped
  
  const page = ref(0)
  const pageSize = ref(20)
  const hasMore = ref(true)

  // 任务日志查看相关状态
  const showLogModal = ref(false)
  const logDetail = ref<any>(null)
  const logLoading = ref(false)
  const { groupedLogs: logDetailGroupedLogs } = useGroupedLogs(logDetail)

  // WebSocket 事件流：监听任务完成事件，自动刷新整理历史
  const { on: onEvent } = useEventStream()
  let _unsubscribeEvents: (() => void) | null = null
  let _unsubscribeLogStream: (() => void) | null = null

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
      const statusParam = statusFilter.value !== 'all' ? `&status=${encodeURIComponent(statusFilter.value)}` : ''
      const searchParam = searchQuery.value ? `&search=${encodeURIComponent(searchQuery.value)}` : ''
      const res = await fetch(`${API_BASE}/api/organize/history?limit=${pageSize.value}&offset=${offset}${statusParam}${searchParam}`)
      const data = await res.json()
      
      // 为每个 item 添加 shouldDeleteFile 属性
      const dataWithFlag = data.map((item: any) => ({
        ...item,
        shouldDeleteFile: false
      }))
      
      if (isRefresh) {
        history.value = dataWithFlag
      } else {
        history.value.push(...dataWithFlag)
      }
      
      if (data.length < pageSize.value) {
        hasMore.value = false
      } else {
        page.value++
      }
    } catch (e) {
      message.error('加载历史记录失败')
    } finally {
      loading.value = false
    }
  }

  const loadMore = () => {
    fetchData(false)
  }

  const deleteItem = async (id: number, deleteFile: boolean = false) => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/history/${id}?delete_file=${deleteFile}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.success) {
        message.success(deleteFile ? '记录及文件已删除' : '记录已删除')
        const index = history.value.findIndex(item => item.id === id)
        if (index !== -1) {
          history.value.splice(index, 1)
        }
      } else {
        message.error(data.message || '删除失败')
      }
    } catch (e) { message.error('删除失败') }
  }

  const retryingIds = ref<Set<number>>(new Set())

  const retryItem = async (id: number) => {
    if (retryingIds.value.has(id)) return
    retryingIds.value.add(id)
    try {
      const res = await fetch(`${API_BASE}/api/organize/history/${id}/retry`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message || '重试任务已启动，可在「任务历史」查看进度')
      } else {
        message.error(data.message || '重试失败')
      }
    } catch (e) {
      message.error('请求服务器失败')
    } finally {
      // 释放按钮锁定（后台任务仍在执行）
      setTimeout(() => retryingIds.value.delete(id), 1500)
    }
  }

  const isRetrying = (id: number) => retryingIds.value.has(id)

  /**
   * 查看该历史记录关联的识别任务日志
   * 与任务中心的「识别」日志复用同一份数据，通过 task_id 关联。
   * 旧数据没有 task_id 字段时给出提示。
   */
  const viewTaskLog = async (taskId: string | null | undefined) => {
    if (!taskId) {
      message.warning('该记录未关联任务日志（旧数据不支持查看日志）')
      return
    }
    logLoading.value = true
    showLogModal.value = true
    logDetail.value = null
    try {
      const res = await fetch(`${API_BASE}/api/task_history/${taskId}`)
      if (res.status === 404) {
        message.warning('关联的任务日志已被清理（任务中心会自动清理超过 30 天的记录）')
        showLogModal.value = false
        return
      }
      logDetail.value = await res.json()
      if (!logDetail.value) {
        message.error('未找到任务日志')
        showLogModal.value = false
      }
      // 任务运行中：订阅实时日志流
      if (logDetail.value?.status === 'running') {
        subscribeLogStream(taskId)
      }
    } catch (e) {
      message.error('获取任务日志失败')
      showLogModal.value = false
    } finally {
      logLoading.value = false
    }
  }

  const subscribeLogStream = (taskId: string) => {
    unsubscribeLogStream()
    _unsubscribeLogStream = onEvent('task_log', (data: any) => {
      if (data?.task_id === taskId && logDetail.value) {
        const logs = [...(logDetail.value.logs || []), data.log]
        logDetail.value = { ...logDetail.value, logs }
      }
    })
  }

  const unsubscribeLogStream = () => {
    if (_unsubscribeLogStream) {
      _unsubscribeLogStream()
      _unsubscribeLogStream = null
    }
  }

  // 弹窗关闭时取消日志流订阅
  watch(showLogModal, (val) => {
    if (!val) {
      unsubscribeLogStream()
    }
  })

  const clearAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/history/clear`, { method: 'DELETE' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message || '历史记录已清空')
        history.value = []
      } else {
        message.error(data.detail || '清空失败')
      }
    } catch (e) { 
      message.error('请求服务器失败') 
    } finally {
      fetchData()
    }
  }

  const getActionLabel = (type: string) => {
    const map: any = {
      'move': '移动',
      'copy': '复制',
      'link': '硬链',
      'cd2_move': 'CD2移动',
      'cd2_copy': 'CD2复制'
    }
    return map[type] || type
  }

  const formatTime = (timeStr: string) => {
    if (!timeStr) return '-'
    return timeStr.replace('T', ' ').split('.')[0]
  }

  onMounted(() => {
    fetchData()
    // 订阅 WS 事件：整理任务完成时自动刷新历史列表
    if (!_unsubscribeEvents) {
      _unsubscribeEvents = onEvent('task_record', (data: any) => {
        // 只在整理任务完成时刷新，避免无关任务的频繁刷新
        if (data?.action === 'finish' && data?.module === '整理') {
          fetchData(true)
        }
      })
    }
  })

  onUnmounted(() => {
    if (_unsubscribeEvents) {
      _unsubscribeEvents()
      _unsubscribeEvents = null
    }
    unsubscribeLogStream()
  })

  return {
    loading,
    history,
    searchQuery,
    statusFilter,
    hasMore,
    fetchData,
    loadMore,
    deleteItem,
    retryItem,
    isRetrying,
    clearAll,
    getActionLabel,
    formatTime,
    showLogModal,
    logDetail,
    logLoading,
    logDetailGroupedLogs,
    viewTaskLog
  }
}
