/**
 * 确认对话框 composable（单例模式）
 *
 * 返回值：
 * - true  → 用户点击确认按钮
 * - false → 用户点击取消按钮
 * - null  → 用户点击 X 或点击遮罩关闭（dismiss，不做任何操作）
 */
import { ref } from 'vue'

interface ConfirmOptions {
  title?: string
  content: string
  confirmText?: string
  cancelText?: string
  confirmColor?: string
}

const show = ref(false)
const options = ref<ConfirmOptions>({
  title: '',
  content: '',
  confirmText: '确认',
  cancelText: '取消',
  confirmColor: 'primary',
})

let resolvePromise: ((value: boolean | null) => void) | null = null

export function useConfirm() {
  function confirm(optsOrMsg: ConfirmOptions | string): Promise<boolean | null> {
    const opts: ConfirmOptions = typeof optsOrMsg === 'string'
      ? { title: '确认', content: optsOrMsg }
      : optsOrMsg
    options.value = {
      confirmText: '确认',
      cancelText: '取消',
      confirmColor: 'primary',
      ...opts,
    }
    show.value = true
    return new Promise((resolve) => {
      resolvePromise = resolve
    })
  }

  function onConfirm() {
    show.value = false
    resolvePromise?.(true)
    resolvePromise = null
  }

  function onCancel() {
    show.value = false
    resolvePromise?.(false)
    resolvePromise = null
  }

  function onDismiss() {
    show.value = false
    resolvePromise?.(null)
    resolvePromise = null
  }

  return { show, options, confirm, onConfirm, onCancel, onDismiss }
}
