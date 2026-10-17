/**
 * 剪贴板复制 composable —— 全项目唯一入口
 *
 * 为什么必须走这里：
 * navigator.clipboard 只在「安全上下文」（https 或 localhost）才存在。内网用
 * http://192.168.x.x:6868 访问时它是 undefined，直接
 * `navigator.clipboard.writeText(...)` 会抛 TypeError，页面表现就是
 * 「复制失败，请手动选择文本」——其实一个字都没复制。
 *
 * 三级降级：
 *   1) Clipboard API（安全上下文，异步、无副作用）
 *   2) 临时 textarea + document.execCommand('copy')（内网 HTTP 的常规路径）
 *   3) 仍失败时把文本选中，提示用户按 Ctrl+C（而不是干巴巴报错）
 *
 * 用法：
 *   const { copy } = useClipboard()
 *   await copy(text, '已复制路径')        // 成功/失败提示由 composable 统一给
 *   const ok = await copy(text)           // 需要自己控制反馈时看返回值
 */
import { useNotification } from './useNotification'

export function useClipboard() {
  const { success, warning, error: showError } = useNotification()

  /** 降级方案：临时 textarea + execCommand('copy')，返回是否真的复制成功 */
  function legacyCopy(text: string): boolean {
    const prevFocus = (document.activeElement as HTMLElement | null) || null
    const sel = document.getSelection()
    const prevRange = sel && sel.rangeCount ? sel.getRangeAt(0) : null

    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    // 放在视口外但保持可聚焦/可选中（display:none 会导致 select 失效）
    textarea.style.position = 'fixed'
    textarea.style.top = '0'
    textarea.style.left = '-9999px'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)

    let ok = false
    try {
      textarea.focus()
      textarea.select()
      textarea.setSelectionRange(0, text.length)
      ok = document.execCommand('copy')
    } catch {
      ok = false
    }

    if (ok) {
      document.body.removeChild(textarea)
      if (prevRange && sel) {
        sel.removeAllRanges()
        sel.addRange(prevRange)
      }
      try {
        prevFocus?.focus?.()
      } catch {
        /* 元素可能已卸载，忽略 */
      }
      return true
    }

    // 复制没成功：保留 textarea 并选中文本，让用户直接 Ctrl+C
    try {
      textarea.focus()
      textarea.select()
      textarea.setSelectionRange(0, text.length)
    } catch {
      /* 忽略 */
    }
    const cleanup = () => {
      try {
        textarea.remove()
      } catch {
        /* 忽略 */
      }
      window.removeEventListener('pointerdown', cleanup, true)
      window.removeEventListener('keydown', cleanup, true)
    }
    window.addEventListener('pointerdown', cleanup, true)
    window.addEventListener('keydown', cleanup, true)
    window.setTimeout(cleanup, 15000)
    return false
  }

  /**
   * 复制文本到剪贴板。
   * @param text 要复制的文本（空值直接报错返回 false）
   * @param hint 成功提示文案
   * @returns 是否复制成功
   */
  async function copy(text: string, hint = '已复制到剪贴板'): Promise<boolean> {
    const value = text == null ? '' : String(text)
    if (!value) {
      showError('没有可复制的内容')
      return false
    }

    // 1) Clipboard API：安全上下文才有；存在也可能因权限被拒，失败继续降级
    const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined
    if (clipboard?.writeText) {
      try {
        await clipboard.writeText(value)
        success(hint)
        return true
      } catch {
        /* 权限被拒 / 非安全上下文，走降级 */
      }
    }

    // 2) execCommand 降级
    if (legacyCopy(value)) {
      success(hint)
      return true
    }

    // 3) 已选中文本，交给用户 Ctrl+C
    warning('复制失败，已选中文本，请按 Ctrl+C 手动复制')
    return false
  }

  return { copy }
}
