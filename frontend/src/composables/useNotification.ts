/**
 * 通知封装 composable
 * 底层使用 Vuetify snackbar，支持队列、图标、类型映射
 */
import { ref, computed } from 'vue'

/* ------------------------------------------------------------------ *
 *  类型定义
 * ------------------------------------------------------------------ */

export type NotificationType = 'success' | 'error' | 'warning' | 'info'

export interface NotificationItem {
  id: number
  type: NotificationType
  title?: string
  message: string
  timeout: number
}

/** 每种类型的默认配置：图标、Vuetify color、超时 */
interface TypeConfig {
  icon: string
  color: string
  timeout: number
}

const TYPE_CONFIG: Record<NotificationType, TypeConfig> = {
  success: { icon: 'mdi-check-circle',         color: 'success', timeout: 3000 },
  error:   { icon: 'mdi-alert-circle',         color: 'error',   timeout: 5000 },
  warning: { icon: 'mdi-alert',               color: 'warning', timeout: 4000 },
  info:    { icon: 'mdi-information',         color: 'info',    timeout: 3000 },
}

/* ------------------------------------------------------------------ *
 *  全局状态（模块级单例，所有 useNotification() 调用共享同一实例）
 * ------------------------------------------------------------------ */

const queue = ref<NotificationItem[]>([])
let idCounter = 0

/** 当前显示的通知（队列首项） */
const current = computed(() => queue.value[0] ?? null)

/* ------------------------------------------------------------------ *
 *  composable
 * ------------------------------------------------------------------ */

export function useNotification() {
  /**
   * 发送通知
   * @param titleOrMsg  有 message 时作为 title，否则作为 message
   * @param message     可选，通知正文
   * @param type        通知类型
   */
  function notify(
    titleOrMsg: string,
    message?: string,
    type: NotificationType = 'success',
  ) {
    const config = TYPE_CONFIG[type]
    queue.value.push({
      id: ++idCounter,
      type,
      title: message ? titleOrMsg : undefined,
      message: message || titleOrMsg,
      timeout: config.timeout,
    })
  }

  function success(msg: string) { notify(msg, undefined, 'success') }
  function error  (msg: string) { notify(msg, undefined, 'error')   }
  function warning(msg: string) { notify(msg, undefined, 'warning') }
  function info   (msg: string) { notify(msg, undefined, 'info')    }

  /** 关闭当前通知，显示队列中的下一条 */
  function dismiss() {
    queue.value.shift()
  }

  /** 清空整个通知队列 */
  function clear() {
    queue.value = []
  }

  return {
    /** 当前显示中的通知（null 表示无） */
    current,
    /** 获取当前类型对应的图标名 */
    getIcon: (type: NotificationType) => TYPE_CONFIG[type].icon,
    notify,
    success,
    error,
    warning,
    info,
    dismiss,
    clear,
  }
}
