import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { isDarkMode } from '../../store/themeStore'

export function useLogConsole() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
  const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const WS_BASE = API_BASE.replace(/^http/, 'ws') || `${WS_PROTOCOL}//${window.location.host}`

  interface LogItem {
    id: number
    content: string
  }

  const consoleLogs = ref<LogItem[]>([])
  const isPaused = ref(false)
  const autoScroll = ref(true)
  const virtualListInst = ref<any>(null)
  const socketStatus = ref<'connected' | 'disconnected' | 'connecting'>('disconnected')
  const logDates = ref<string[]>([])
  const selectedDate = ref<string | null>(null) // null means Live
  const isLoadingHistory = ref(false)
  const isInitialLoading = ref(false)
  const currentPage = ref(1)
  const pageSize = 500
  const hasMore = ref(true)

  let logCounter = 0
  let socket: WebSocket | null = null
  let retryTimer: any = null

  const appendLog = (content: string) => {
    if (consoleLogs.value.length > 10000) {
      consoleLogs.value = consoleLogs.value.slice(0, 8000)
    }
    
    consoleLogs.value.unshift({
      id: logCounter++,
      content: content
    })
    
    if (autoScroll.value) {
      nextTick(() => {
        scrollToTop()
      })
    }
  }

  const scrollToTop = () => {
    virtualListInst.value?.scrollTo({ position: 'top' })
  }

  const fetchLogDates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/logs/dates`)
      logDates.value = await res.json()
    } catch (e) { console.error('Failed to fetch log dates') }
  }

  const fetchHistoryLog = async (date: string, page = 1) => {
    isLoadingHistory.value = true
    if (page === 1) {
      consoleLogs.value = []
      currentPage.value = 1
      hasMore.value = true
      isInitialLoading.value = true
    }
    
    try {
      const url = `${API_BASE}/api/system/logs/date/${date}?page=${page}&limit=${pageSize}`
      const res = await fetch(url)
      
      const text = await res.text()
      if (text.includes("--- [结束]")) {
        hasMore.value = false
        if (page === 1) {
          consoleLogs.value = [{ id: -1, content: "该日期暂无更多日志记录" }]
        }
        return
      }

      const lines = text.split('\n').filter(l => l.trim())
      if (lines.length < pageSize) {
        hasMore.value = false
      }

      const newLogs = lines.map((line, index) => ({
        id: (page - 1) * pageSize + index,
        content: line
      }))

      if (page === 1) {
        consoleLogs.value = newLogs
        nextTick(() => {
          scrollToTop()
        })
      } else {
        consoleLogs.value = [...consoleLogs.value, ...newLogs]
      }
      
      currentPage.value = page
    } catch (e) {
      appendLog(`>>> 无法加载 ${date} 的日志，请检查网络或日志文件 <<<`)
    } finally {
      isLoadingHistory.value = false
      isInitialLoading.value = false
    }
  }

  const loadMoreHistory = () => {
    if (!selectedDate.value || isLoadingHistory.value || !hasMore.value) return
    fetchHistoryLog(selectedDate.value, currentPage.value + 1)
  }

  const handleDateChange = (val: string | null) => {
    if (val === null) {
      clearConsole()
      appendLog(">>> 正在切换回实时日志流... <<<")
      
      // 强制重连以获取最新的历史回填 (对齐 cs123)
      if (socket) {
        socket.close()
        socket = null
      }
      connectWebSocket()
      
      isPaused.value = false
    } else {
      isPaused.value = true
      fetchHistoryLog(val)
    }
  }

  const connectWebSocket = () => {
    if (socket) return

    socketStatus.value = 'connecting'
    const wsUrl = `${WS_BASE}/ws/system/logs`
    socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      socketStatus.value = 'connected'
      appendLog(">>> 系统实时控制台连接成功 (最新置顶) <<<")
      if (retryTimer) {
        clearTimeout(retryTimer)
        retryTimer = null
      }
    }

    socket.onmessage = (event) => {
      if (isPaused.value) return
      appendLog(event.data)
    }

    socket.onclose = () => {
      socket = null
      socketStatus.value = 'disconnected'
      appendLog(">>> 连接断开，正在尝试重连... <<<")
      retryTimer = setTimeout(connectWebSocket, 3000)
    }
  }

  const clearConsole = () => {
    consoleLogs.value = []
    logCounter = 0
  }

  const openFullLog = async () => {
    const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    let url: string
    if (selectedDate.value) {
      url = `${API_BASE}/api/system/logs/date/${selectedDate.value}?download=true`
    } else {
      url = `${API_BASE}/api/system/logs/raw?type=monitor&download=true`
    }

    try {
      const response = await fetch(url, { headers })
      if (!response.ok) {
        throw new Error(`获取日志失败: ${response.statusText}`)
      }
      
      const text = await response.text()
      const isDark = isDarkMode.value
      
      const bgColor = isDark ? '#1e1e2e' : '#ffffff'
      const textColor = isDark ? '#e0e0e0' : '#1a1a1a'
      
      const newWindow = window.open('', '_blank')
      if (newWindow) {
        newWindow.document.write(`
          <!DOCTYPE html>
          <html>
          <head>
            <title>日志查看 - ${selectedDate.value || 'monitor'}</title>
            <style>
              body {
                font-family: 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
                padding: 20px;
                margin: 0;
                background-color: ${bgColor};
                color: ${textColor};
              }
              pre {
                white-space: pre-wrap;
                word-wrap: break-word;
              }
            </style>
          </head>
          <body>
            <pre>${text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </body>
          </html>
        `)
        newWindow.document.close()
      }
    } catch (error) {
      console.error('打开日志失败:', error)
      alert('打开日志失败，请检查网络连接')
    }
  }

  onMounted(() => {
    connectWebSocket()
    fetchLogDates()
  })

  onUnmounted(() => {
    if (socket) {
      socket.close()
      socket = null
    }
    if (retryTimer) clearTimeout(retryTimer)
  })

  return {
    consoleLogs,
    isPaused,
    autoScroll,
    virtualListInst,
    socketStatus,
    logDates,
    selectedDate,
    isLoadingHistory,
    isInitialLoading,
    hasMore,
    handleDateChange,
    loadMoreHistory,
    scrollToTop,
    clearConsole,
    openFullLog
  }
}
