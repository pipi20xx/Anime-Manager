/**
 * 通用事件 WebSocket 订阅 composable
 * 替代前端轮询，实时接收后端推送的任务状态、服务状态等事件。
 *
 * 用法：
 *   const { on, connected } = useEventStream()
 *   on('background_tasks', (data) => { ... })
 *   on('task_record', (data) => { ... })
 *   on('services_status', (data) => { ... })
 */
import { ref, onMounted, onUnmounted } from 'vue'

export function useEventStream() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
  const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const WS_BASE = API_BASE.replace(/^http/, 'ws') || `${WS_PROTOCOL}//${window.location.host}`

  const connected = ref(false)
  let socket: WebSocket | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0

  // 事件处理器注册表：eventType -> Set<handler>
  const handlers = new Map<string, Set<(data: any) => void>>()

  const connect = () => {
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
      if (retryTimer) {
        clearTimeout(retryTimer)
        retryTimer = null
      }
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const { type, data } = msg
        if (type && handlers.has(type)) {
          handlers.get(type)!.forEach((fn) => {
            try {
              fn(data)
            } catch (e) {
              console.error('[EventStream] handler error:', e)
            }
          })
        }
      } catch (e) {
        // 忽略非 JSON 消息
      }
    }

    socket.onclose = () => {
      socket = null
      connected.value = false
      scheduleReconnect()
    }

    socket.onerror = () => {
      // onclose 会处理重连
    }
  }

  const scheduleReconnect = () => {
    if (retryTimer) return
    // 指数退避：1s, 2s, 4s, 8s, 最大 15s
    const delay = Math.min(1000 * Math.pow(2, retryCount), 15000)
    retryCount++
    retryTimer = setTimeout(() => {
      retryTimer = null
      connect()
    }, delay)
  }

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

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    if (socket) {
      socket.close()
      socket = null
    }
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    handlers.clear()
  })

  return { on, connected }
}
