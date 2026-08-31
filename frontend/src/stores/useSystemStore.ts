/**
 * 系统全局 Store — 管理 WebSocket、登录状态、进度等
 *
 * WebSocket 连接到 /ws/events，支持事件类型订阅（替代前端轮询）。
 * 内置心跳检测（30s ping）和断线重连后自动 re-fetch。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ProgressData } from '@/types'

// ===== 模块级单例：事件处理器注册表 =====
/** eventType -> Set<handler> */
const handlers = new Map<string, Set<(data: any) => void>>()
/** 重连后回调 */
const reconnectHandlers = new Set<() => void>()

export const useSystemStore = defineStore('system', () => {
  // --- WebSocket 状态 ---
  const isConnected = ref(false)
  const scanProgress = ref<ProgressData>({ status: 'idle', current: 0, total: 0, message: '' })
  const downloadProgress = ref<ProgressData>({ status: 'idle', current: 0, total: 0, message: '' })
  const logs = ref<string[]>([])

  let socket: WebSocket | null = null
  let logSocket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let logReconnectTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let lastMessageTime = Date.now()

  // --- 登录状态 ---
  const isLoggedIn = ref(!!(localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')))
  const username = ref(localStorage.getItem('apm_username') || '')

  // --- 日志终端 ---
  const showLogModal = ref(false)

  // --- 计算属性 ---
  const hasActiveProgress = computed(() => {
    const sp = scanProgress.value
    const dp = downloadProgress.value
    return (sp.status === 'running' || sp.status === 'scanning') ||
           (dp.status === 'running' || dp.status === 'scanning')
  })

  // --- 心跳 ---
  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        if (Date.now() - lastMessageTime > 60000) {
          console.warn('[WS] 心跳超时，强制重连')
          socket.close()
          return
        }
        socket.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  // --- 指数退避重连 ---
  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, retryCount), 15000)
    retryCount++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  // --- WebSocket 鉴权 ---
  /** WS 握手无法携带 Authorization 头，统一通过 ?token= 传递 */
  function getWsToken(): string {
    return localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token') || ''
  }

  // --- 系统日志 WebSocket (/ws/system/logs) ---
  function connectLogStream() {
    if (logSocket) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const logWsUrl = `${protocol}//${host}/ws/system/logs?token=${encodeURIComponent(getWsToken())}`

    try {
      logSocket = new WebSocket(logWsUrl)
    } catch {
      scheduleLogReconnect()
      return
    }

    logSocket.onmessage = (event) => {
      const msg = String(event.data)
      if (msg) {
        logs.value.push(msg)
        if (logs.value.length > 2000) logs.value.shift()
      }
    }

    logSocket.onclose = () => {
      logSocket = null
      if (isLoggedIn.value) {
        scheduleLogReconnect()
      }
    }

    logSocket.onerror = () => {
      // onclose 会处理重连
    }
  }

  function scheduleLogReconnect() {
    if (logReconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, retryCount), 15000)
    logReconnectTimer = setTimeout(() => {
      logReconnectTimer = null
      connectLogStream()
    }, delay)
  }

  function disconnectLogStream() {
    if (logSocket) {
      logSocket.close()
      logSocket = null
    }
    if (logReconnectTimer) {
      clearTimeout(logReconnectTimer)
      logReconnectTimer = null
    }
  }

  // --- WebSocket 方法 ---
  function connect() {
    if (socket) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/events?token=${encodeURIComponent(getWsToken())}`

    try {
      socket = new WebSocket(wsUrl)
    } catch {
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      isConnected.value = true
      retryCount = 0
      lastMessageTime = Date.now()
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      startHeartbeat()
      // 重连后通知所有订阅者重新拉取数据
      reconnectHandlers.forEach((fn) => {
        try { fn() } catch (e) { console.error('[WS] reconnect handler error:', e) }
      })
    }

    // 同时连接系统日志流
    connectLogStream()

    socket.onmessage = (event) => {
      lastMessageTime = Date.now()
      try {
        const msg = JSON.parse(event.data)
        const { type, data } = msg

        // 心跳响应
        if (type === 'pong') return

        // 兼容旧格式：progress
        if (type === 'progress') {
          const task = data?.task || msg.task
          if (task === 'scan') {
            scanProgress.value = data || msg.data
          } else if (task === 'download' || task === 'organize' || task === 'recognize') {
            downloadProgress.value = data || msg.data
          }
          return
        }

        // 通用事件分发：按 type 调用所有注册的 handler
        if (type && handlers.has(type)) {
          handlers.get(type)!.forEach((fn) => {
            try { fn(data) } catch (e) { console.error('[WS] handler error:', e) }
          })
        }
      } catch (e) {
        // 忽略非 JSON 消息
      }
    }

    socket.onclose = () => {
      isConnected.value = false
      socket = null
      stopHeartbeat()
      if (isLoggedIn.value) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      // onclose 会处理重连
    }
  }

  function disconnect() {
    if (socket) {
      socket.close()
      socket = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()
    isConnected.value = false
    disconnectLogStream()
  }

  function clearLogs() {
    logs.value = []
  }

  // --- 事件订阅 ---
  /** 订阅指定事件类型，返回取消订阅函数 */
  function on(eventType: string, handler: (data: any) => void): () => void {
    if (!handlers.has(eventType)) {
      handlers.set(eventType, new Set())
    }
    handlers.get(eventType)!.add(handler)
    return () => {
      handlers.get(eventType)?.delete(handler)
    }
  }

  /** 注册重连后回调（用于重新拉取初始状态） */
  function onReconnect(handler: () => void): () => void {
    reconnectHandlers.add(handler)
    return () => {
      reconnectHandlers.delete(handler)
    }
  }

  // --- 登录方法 ---
  function loginSuccess(token: string, user: string) {
    localStorage.setItem('apm_access_token', token)
    localStorage.setItem('apm_username', user)
    isLoggedIn.value = true
    username.value = user
  }

  function logout() {
    localStorage.removeItem('apm_access_token')
    localStorage.removeItem('apm_username')
    localStorage.removeItem('apm_external_token')
    isLoggedIn.value = false
    username.value = ''
    disconnect()
  }

  return {
    isConnected,
    scanProgress,
    downloadProgress,
    logs,
    showLogModal,
    isLoggedIn,
    username,
    hasActiveProgress,
    connect,
    disconnect,
    clearLogs,
    on,
    onReconnect,
    loginSuccess,
    logout,
  }
})
