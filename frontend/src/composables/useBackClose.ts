import { watch, onUnmounted, Ref } from 'vue'

/**
 * Enables Android Back Button / Browser Back / PC Mouse Side Button to close a modal/drawer/dialog.
 *
 * 实现原理：
 * - 打开弹框时 pushState 一个 history 条目，使 URL 产生可后退的 state
 * - 通过 UI（关闭按钮/遮罩）关闭时，主动 history.back() 消费该 state
 * - 真正的后退（侧滑/侧键/浏览器后退）触发 popstate 时，关闭栈顶层级
 *
 * 支持嵌套弹框和弹框内视图切换（逐级后退）：使用全局栈 + 单例 popstate 监听器，
 * 确保关闭内层弹框/视图时不会误伤外层。
 *
 * 同时支持「同时关闭多个层级」的场景（如关闭弹框时连带重置内部编辑视图），
 * 使用计数器而非单一标记，确保每个 UI 主动 back 产生的 popstate 都被正确消费。
 */

// ── 全局协调状态（模块单例） ──
/** 当前打开的层级栈，每项是一个关闭函数（栈顶为最近打开的层级） */
const closeStack: Array<() => void> = []
/**
 * 计数器：记录由 UI 主动关闭时调用 history.back() 产生的待消费 popstate 数量。
 * 每次 UI 关闭一个层级 → consumeCount++；每次 popstate → 若 >0 则 -- 并跳过。
 */
let consumeCount = 0
/** 全局 popstate 监听器是否已安装 */
let globalListenerInstalled = false

function globalPopStateHandler() {
  // 若是 UI 关闭时主动 back 产生的 popstate，消费掉并跳过
  if (consumeCount > 0) {
    consumeCount--
    return
  }
  // 真正的后退：关闭栈顶层级
  const closeFn = closeStack[closeStack.length - 1]
  if (closeFn) {
    closeFn()
  }
}

function ensureGlobalListener() {
  if (!globalListenerInstalled) {
    window.addEventListener('popstate', globalPopStateHandler)
    globalListenerInstalled = true
  }
}

/**
 * 底层 API：注册一个「可后退关闭」的层级。
 * 适用于 dialog 等非 Ref<boolean> 场景。
 *
 * @param onBack - 后退触发时的关闭回调（如 dialog.destroy()）
 * @returns 控制器：open() 打开时调用，close() UI关闭时调用
 */
export function useBackLayer(onBack: () => void) {
  ensureGlobalListener()
  let inStack = false

  /** 打开层级：入栈 + pushState */
  const open = () => {
    if (inStack) return
    inStack = true
    closeStack.push(onBack)
    window.history.pushState({ modalOpen: true }, '')
  }

  /** UI 主动关闭：出栈 + history.back() 消费 state */
  const close = () => {
    if (!inStack) return
    inStack = false
    const idx = closeStack.indexOf(onBack)
    if (idx !== -1) closeStack.splice(idx, 1)
    consumeCount++
    window.history.back()
  }

  /** popstate 触发关闭后：仅出栈（history state 已被浏览器消费） */
  const remove = () => {
    if (!inStack) return
    inStack = false
    const idx = closeStack.indexOf(onBack)
    if (idx !== -1) closeStack.splice(idx, 1)
  }

  return { open, close, remove }
}

/**
 * 高层 API：让一个 Ref<boolean> 控制的弹框/视图支持后退关闭。
 *
 * @param isOpen - 控制弹框/视图可见性的 boolean ref
 */
export function useBackClose(isOpen: Ref<boolean>) {
  let closingViaPopstate = false

  const { open, close, remove } = useBackLayer(() => {
    closingViaPopstate = true
    isOpen.value = false
  })

  watch(isOpen, (val) => {
    if (val) {
      open()
    } else {
      if (closingViaPopstate) {
        // popstate 导致的关闭，history state 已被浏览器消费，仅出栈
        closingViaPopstate = false
        remove()
      } else {
        // UI 导致的关闭，需要消费打开时 push 的 state
        close()
      }
    }
  })

  onUnmounted(() => {
    // 组件卸载时清理栈中残留的引用
    remove()
  })
}
