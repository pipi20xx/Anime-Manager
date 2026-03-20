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

    const newWindow = window.open('', '_blank')
    if (!newWindow) {
      alert('无法打开新窗口，请检查浏览器弹窗设置')
      return
    }

    const isDark = isDarkMode.value
    const bgColor = isDark ? '#1e1e2e' : '#ffffff'
    const textColor = isDark ? '#e0e0e0' : '#1a1a1a'
    const accentColor = isDark ? '#89b4fa' : '#1e88e5'
    const borderColor = isDark ? '#313244' : '#e0e0e0'

    newWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>日志查看 - ${selectedDate.value || 'monitor'}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          
          /* 隐藏 CloudDrive2 扩展菜单 */
          .cd-offline-menu,
          .cd-offline-menu * {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            top: -9999px !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
          }
          
          body {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
            padding: 0;
            margin: 0;
            background-color: ${bgColor};
            color: ${textColor};
            height: 100vh;
            display: flex;
            flex-direction: column;
          }
          .header {
            flex-shrink: 0;
            background-color: ${bgColor};
            padding: 15px 20px;
            border-bottom: 1px solid ${borderColor};
            z-index: 100;
          }
          .header h1 {
            font-size: 16px;
            margin-bottom: 8px;
          }
          .info {
            font-size: 12px;
            color: ${isDark ? '#a6adc8' : '#666'};
          }
          .info span {
            margin-right: 20px;
          }
          .loading {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 1000;
            background-color: ${bgColor};
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          }
          .loading-spinner {
            border: 3px solid ${borderColor};
            border-top: 3px solid ${accentColor};
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
          }
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          .log-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
          }
          .log-line {
            padding: 2px 0;
            border-bottom: 1px solid ${isDark ? '#1e1e2e' : '#f5f5f5'};
          }
          .log-line:hover {
            background-color: ${isDark ? '#313244' : '#f5f5f5'};
          }
          .log-line-match {
            background-color: ${isDark ? 'rgba(137, 180, 250, 0.2)' : 'rgba(30, 136, 229, 0.1)'};
            border-left: 3px solid ${accentColor};
          }
          .log-line-current {
            background-color: ${isDark ? 'rgba(137, 180, 250, 0.4)' : 'rgba(30, 136, 229, 0.2)'} !important;
            border-left: 3px solid ${accentColor};
            font-weight: bold;
          }
          .search-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            align-items: center;
          }
          .search-input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid ${borderColor};
            border-radius: 4px;
            background-color: ${bgColor};
            color: ${textColor};
            font-family: inherit;
            font-size: 14px;
          }
          .search-input:focus {
            outline: none;
            border-color: ${accentColor};
          }
          .search-buttons {
            display: flex;
            gap: 4px;
          }
          .search-btn {
            padding: 8px 12px;
            border: 1px solid ${borderColor};
            border-radius: 4px;
            background-color: ${bgColor};
            color: ${textColor};
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
          }
          .search-btn:hover {
            background-color: ${isDark ? '#313244' : '#f5f5f5'};
          }
          .search-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          .search-count {
            padding: 8px 12px;
            font-size: 12px;
            color: ${isDark ? '#a6adc8' : '#666'};
            min-width: 80px;
            text-align: center;
          }
          .load-more {
            text-align: center;
            padding: 20px;
            color: ${accentColor};
            cursor: pointer;
            border: 1px dashed ${borderColor};
            margin: 10px 0;
            border-radius: 4px;
          }
          .load-more:hover {
            background-color: ${isDark ? '#313244' : '#f5f5f5'};
          }
          .loading-more {
            text-align: center;
            padding: 20px;
            color: ${isDark ? '#a6adc8' : '#666'};
          }
          .no-more {
            text-align: center;
            padding: 20px;
            color: ${isDark ? '#6c7086' : '#999'};
            font-style: italic;
          }
          .error-message {
            background-color: ${isDark ? '#f38ba8' : '#f8d7da'};
            color: ${isDark ? '#1e1e2e' : '#721c24'};
            padding: 15px;
            margin: 20px;
            border-radius: 4px;
            border-left: 4px solid ${accentColor};
          }
        </style>
      </head>
      <body>
        <div class="loading" id="loading">
          <div class="loading-spinner"></div>
          <div>正在加载日志...</div>
        </div>
        <div class="header">
          <h1>日志查看 - ${selectedDate.value || 'monitor'}</h1>
          <div class="search-bar">
            <input 
              type="text" 
              id="searchInput" 
              class="search-input" 
              placeholder="搜索日志..."
              autocomplete="off"
            />
            <div class="search-buttons">
              <button id="prevBtn" class="search-btn" disabled>↑</button>
              <button id="nextBtn" class="search-btn" disabled>↓</button>
            </div>
            <div id="searchCount" class="search-count">无匹配</div>
          </div>
          <div class="info">
            <span id="lineCount">行数: 计算中...</span>
            <span id="loadedCount">已加载: 0 行</span>
            <span id="fileSize">大小: 计算中...</span>
          </div>
        </div>
        <div class="log-container" id="logContainer">
          <div id="logContent"></div>
          <div id="loadMore" class="load-more" style="display: none;">点击加载更多</div>
          <div id="loadingMore" class="loading-more" style="display: none;">正在加载更多...</div>
          <div id="noMore" class="no-more" style="display: none;">已加载全部日志</div>
        </div>
      </body>
      </html>
    `)
    newWindow.document.close()

    try {
      const response = await fetch(url, { headers })
      if (!response.ok) {
        throw new Error(`获取日志失败: ${response.statusText}`)
      }
      
      const text = await response.text()
      const lines = text.split('\n').filter(l => l.trim())
      const totalLines = lines.length
      const pageSize = 1000
      
      const logContent = newWindow.document.getElementById('logContent')
      const loading = newWindow.document.getElementById('loading')
      const lineCount = newWindow.document.getElementById('lineCount')
      const loadedCount = newWindow.document.getElementById('loadedCount')
      const fileSize = newWindow.document.getElementById('fileSize')
      const loadMore = newWindow.document.getElementById('loadMore')
      const loadingMore = newWindow.document.getElementById('loadingMore')
      const noMore = newWindow.document.getElementById('noMore')
      const logContainer = newWindow.document.getElementById('logContainer')
      
      let currentPage = 0
      let hasMore = true
      let searchResults: number[] = []
      let currentSearchIndex = -1
      let loadedPages = new Set<number>()
      
      const renderLines = (linesToRender: string[], append: boolean = false) => {
        const html = linesToRender.map((line, idx) => {
          const globalIndex = append ? currentPage * pageSize + idx : idx
          const isMatch = searchResults.includes(globalIndex)
          const isCurrentMatch = globalIndex === searchResults[currentSearchIndex]
          
          let lineHtml = line.replace(/</g, '&lt;').replace(/>/g, '&gt;')
          
          if (isMatch) {
            lineHtml = `<div class="log-line log-line-match ${isCurrentMatch ? 'log-line-current' : ''}" data-index="${globalIndex}">${lineHtml}</div>`
          } else {
            lineHtml = `<div class="log-line" data-index="${globalIndex}">${lineHtml}</div>`
          }
          
          return lineHtml
        }).join('')
        
        if (append) {
          logContent.innerHTML += html
        } else {
          logContent.innerHTML = html
        }
      }
      
      const loadPage = async (pageIndex: number) => {
        if (loadedPages.has(pageIndex)) return
        
        loadedPages.add(pageIndex)
        const start = pageIndex * pageSize
        const end = start + pageSize
        const linesToRender = lines.slice(start, end)
        
        await new Promise(resolve => setTimeout(resolve, 50))
        
        const tempDiv = newWindow.document.createElement('div')
        tempDiv.innerHTML = linesToRender.map((line, idx) => {
          const globalIndex = start + idx
          const isMatch = searchResults.includes(globalIndex)
          const isCurrentMatch = globalIndex === searchResults[currentSearchIndex]
          
          let lineHtml = line.replace(/</g, '&lt;').replace(/>/g, '&gt;')
          
          if (isMatch) {
            return `<div class="log-line log-line-match ${isCurrentMatch ? 'log-line-current' : ''}" data-index="${globalIndex}">${lineHtml}</div>`
          } else {
            return `<div class="log-line" data-index="${globalIndex}">${lineHtml}</div>`
          }
        }).join('')
        
        logContent.innerHTML += tempDiv.innerHTML
        
        const loaded = loadedPages.size * pageSize
        if (loadedCount) {
          loadedCount.textContent = `已加载: ${Math.min(loaded, totalLines).toLocaleString()} 行`
        }
      }
      
      const performSearch = (query: string) => {
        searchResults = []
        currentSearchIndex = -1
        
        if (!query.trim()) {
          const lines = logContent.querySelectorAll('.log-line')
          lines.forEach(line => {
            line.classList.remove('log-line-match', 'log-line-current')
          })
          updateSearchUI()
          return
        }
        
        const lowerQuery = query.toLowerCase()
        
        for (let i = 0; i < totalLines; i++) {
          if (lines[i].toLowerCase().includes(lowerQuery)) {
            searchResults.push(i)
          }
        }
        
        if (searchResults.length > 0) {
          currentSearchIndex = 0
          highlightSearchResults()
          scrollToMatch(0)
        }
        
        updateSearchUI()
      }
      
      const highlightSearchResults = () => {
        const lines = logContent.querySelectorAll('.log-line')
        lines.forEach(line => {
          const idx = parseInt(line.getAttribute('data-index') || '0')
          if (searchResults.includes(idx)) {
            line.classList.add('log-line-match')
          }
        })
        
        if (currentSearchIndex >= 0 && currentSearchIndex < searchResults.length) {
          const currentLine = logContent.querySelector(`[data-index="${searchResults[currentSearchIndex]}"]`)
          if (currentLine) {
            currentLine.classList.add('log-line-current')
          }
        }
      }
      
      const scrollToMatch = async (index: number) => {
        if (index < 0 || index >= searchResults.length) return
        
        const targetIndex = searchResults[index]
        const targetPage = Math.floor(targetIndex / pageSize)
        
        if (!loadedPages.has(targetPage)) {
          await loadPage(targetPage)
        }
        
        await new Promise(resolve => setTimeout(resolve, 200))
        
        const targetLine = logContent.querySelector(`[data-index="${targetIndex}"]`)
        if (targetLine) {
          targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }
      
      const nextMatch = async () => {
        if (searchResults.length === 0) return
        currentSearchIndex = (currentSearchIndex + 1) % searchResults.length
        highlightSearchResults()
        await scrollToMatch(currentSearchIndex)
        updateSearchUI()
      }
      
      const prevMatch = async () => {
        if (searchResults.length === 0) return
        currentSearchIndex = (currentSearchIndex - 1 + searchResults.length) % searchResults.length
        highlightSearchResults()
        await scrollToMatch(currentSearchIndex)
        updateSearchUI()
      }
      
      const updateSearchUI = () => {
        const searchCount = newWindow.document.getElementById('searchCount')
        if (searchCount) {
          if (searchResults.length === 0) {
            searchCount.textContent = '无匹配'
          } else {
            searchCount.textContent = `${currentSearchIndex + 1} / ${searchResults.length}`
          }
        }
      }
      
      const loadMoreLines = async () => {
        if (loadedPages.size >= Math.ceil(totalLines / pageSize)) return
        
        const nextPage = loadedPages.size
        await loadPage(nextPage)
        
        hasMore = loadedPages.size < Math.ceil(totalLines / pageSize)
        
        if (hasMore) {
          loadMore.style.display = 'block'
        } else {
          loadMore.style.display = 'none'
          noMore.style.display = 'block'
        }
        
        if (searchResults.length > 0) {
          const searchInput = newWindow.document.getElementById('searchInput') as HTMLInputElement
          if (searchInput && searchInput.value.trim()) {
            performSearch(searchInput.value)
          }
        }
      }
      
      await loadPage(0)
      
      await new Promise(resolve => setTimeout(resolve, 200))
      
      lineCount.textContent = `行数: ${totalLines.toLocaleString()}`
      fileSize.textContent = `大小: ${(text.length / 1024).toFixed(2)} KB`
      
      hasMore = loadedPages.size < Math.ceil(totalLines / pageSize)
      
      loading.style.display = 'none'
      
      if (hasMore) {
        loadMore.style.display = 'block'
      } else {
        noMore.style.display = 'block'
      }
      
      await new Promise(resolve => setTimeout(resolve, 100))
      
      loadMore.addEventListener('click', loadMoreLines)
      
      logContainer.addEventListener('scroll', () => {
        const { scrollTop, scrollHeight, clientHeight } = logContainer
        if (scrollHeight - scrollTop - clientHeight < 100 && hasMore) {
          loadMoreLines()
        }
      })
      
      const searchInput = newWindow.document.getElementById('searchInput')
      const prevBtn = newWindow.document.getElementById('prevBtn')
      const nextBtn = newWindow.document.getElementById('nextBtn')
      
      if (searchInput) {
        searchInput.addEventListener('input', (e: Event) => {
          const target = e.target as HTMLInputElement
          performSearch(target.value)
          
          if (prevBtn && nextBtn) {
            const hasResults = searchResults.length > 0
            prevBtn.disabled = !hasResults
            nextBtn.disabled = !hasResults
          }
        })
        
        searchInput.addEventListener('keydown', (e: KeyboardEvent) => {
          if (e.key === 'Enter' && searchResults.length > 0) {
            e.preventDefault()
            nextMatch()
          } else if (e.key === 'F3' || (e.ctrlKey && e.key === 'g')) {
            e.preventDefault()
            if (e.shiftKey) {
              prevMatch()
            } else {
              nextMatch()
            }
          }
        })
      }
      
      if (prevBtn) {
        prevBtn.addEventListener('click', () => {
          prevMatch()
        })
      }
      
      if (nextBtn) {
        nextBtn.addEventListener('click', () => {
          nextMatch()
        })
      }
      
    } catch (error) {
      console.error('打开日志失败:', error)
      const loading = newWindow.document.getElementById('loading')
      if (loading) {
        loading.innerHTML = `
          <div class="error-message">
            <strong>❌ 打开日志失败</strong><br>
            ${error instanceof Error ? error.message : '未知错误'}
          </div>
        `
      }
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
