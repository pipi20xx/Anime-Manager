/**
 * WebSocket 事件订阅 composable
 *
 * 基于系统全局 Store 的单例 WebSocket 连接（/ws/events）。
 * 支持按事件类型订阅，内置心跳检测和断线重连。
 *
 * 用法：
 *   const { on, onReconnect, isConnected } = useWebSocket()
 *   const unsub = on('task_record', (data) => { ... })
 *   const unsubReconnect = onReconnect(() => { fetchInitialData() })
 *   onUnmounted(() => { unsub(); unsubReconnect() })
 */
import { computed } from 'vue'
import { useSystemStore } from '@/stores'

export function useWebSocket() {
  const systemStore = useSystemStore()

  const isConnected = computed(() => systemStore.isConnected)

  /** 订阅指定事件类型，返回取消订阅函数 */
  function on(eventType: string, handler: (data: any) => void): () => void {
    return systemStore.on(eventType, handler)
  }

  /** 注册重连后回调（用于重新拉取初始状态） */
  function onReconnect(handler: () => void): () => void {
    return systemStore.onReconnect(handler)
  }

  function connect() {
    systemStore.connect()
  }

  function disconnect() {
    systemStore.disconnect()
  }

  return {
    isConnected,
    on,
    onReconnect,
    connect,
    disconnect,
  }
}
