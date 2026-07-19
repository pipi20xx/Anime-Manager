/**
 * 通用事件 WebSocket 订阅 composable（单例模式）
 * 替代前端轮询，实时接收后端推送的任务状态、服务状态等事件。
 *
 * 全应用共享一条 WS 连接，多个 composable 调用不会创建多条连接。
 * 内置心跳检测（30s ping）和断线重连后自动 re-fetch。
 *
 * 用法：
 *   const { on, onReconnect, connected } = useEventStream()
 *   on('background_tasks', (data) => { ... })
 *   onReconnect(() => { fetchInitialData() })
 */
import { ref, onMounted, onUnmounted } from 'vue'

// ===== 模块级单例：全应用共享一条 WS 连接 =====
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_BASE = API_BASE.replace(/^http/, 'ws') || `${WS_PROTOCOL}//${window.location.host}`

const connected = ref(false)
let socket: WebSocket | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null
let retryCount = 0
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let lastMessageTime = Date.now()

/** 引用计数：追踪有多少 composable 在使用此连接 */
let _refCount = 0

// 全局事件处理器注册表：eventType -> Set<handler>
const handlers = new Map<string, Set<(data: any) => void>>()
// 重连后回调：用于重新拉取初始状态
const reconnectHandlers = new Set<() => void>()

function connect() {
  if (socket) return

  try {
    socket = new WebSocket(`${WS_BASE}/ws/events`)
  } catch {
    scheduleReconnect()
    return
  }

  socket.onopen = () => {
    connected.value = true
    retryCount = 0
    lastMessageTime = Date.now()
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    startHeartbeat()
    // 重连后通知所有 composable 重新拉取数据
    reconnectHandlers.forEach((fn) => {
      try {
        fn()
      } catch (e) {
        console.error('[EventStream] reconnect handler error:', e)
      }
    })
  }

  socket.onmessage = (event) => {
    lastMessageTime = Date.now()
    try {
      const msg = JSON.parse(event.data)
      const { type, data } = msg
      if (type === 'pong') return // 心跳响应，不需要处理
      if (type && handlers.has(type)) {
        handlers.get(type)!.forEach((fn) => {
          try {
            fn(data)
          } catch (e) {
            console.error('[EventStream] handler error:', e)
          }
        })
      }
    } catch {
      // 忽略非 JSON 消息
    }
  }

  socket.onclose = () => {
    socket = null
    connected.value = false
    stopHeartbeat()
    // 只有还有 composable 在用时才重连
    if (_refCount > 0) {
      scheduleReconnect()
    }
  }

  socket.onerror = () => {
    // onclose 会处理重连
  }
}

function scheduleReconnect() {
  if (retryTimer) return
  // 指数退避：1s, 2s, 4s, 8s, 最大 15s
  const delay = Math.min(1000 * Math.pow(2, retryCount), 15000)
  retryCount++
  retryTimer = setTimeout(() => {
    retryTimer = null
    connect()
  }, delay)
}

function startHeartbeat() {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      // 60 秒没收到任何消息，认为连接已死，强制关闭触发重连
      if (Date.now() - lastMessageTime > 60000) {
        console.warn('[EventStream] 心跳超时，强制重连')
        socket.close()
        return
      }
      // 发送 ping
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

export function useEventStream() {
  onMounted(() => {
    _refCount++
    connect()
  })

  onUnmounted(() => {
    _refCount--
    // 所有 composable 都卸载后才关闭连接
    if (_refCount <= 0) {
      _refCount = 0
      if (socket) {
        socket.close()
        socket = null
      }
      if (retryTimer) {
        clearTimeout(retryTimer)
        retryTimer = null
      }
      stopHeartbeat()
    }
  })

  /**
   * 订阅事件
   * @param eventType 事件类型
   * @param handler 处理函数
   * @returns 取消订阅函数
   */
  const on = (eventType: string, handler: (data: any) => void) => {
    if (!handlers.has(eventType)) {
      handlers.set(eventType, new Set())
    }
    handlers.get(eventType)!.add(handler)
    return () => {
      handlers.get(eventType)?.delete(handler)
    }
  }

  /**
   * 注册重连后回调（用于重新拉取初始状态）
   * @param handler 回调函数
   * @returns 取消注册函数
   */
  const onReconnect = (handler: () => void) => {
    reconnectHandlers.add(handler)
    return () => {
      reconnectHandlers.delete(handler)
    }
  }

  return { on, onReconnect, connected }
}
