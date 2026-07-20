import { watch, onUnmounted, Ref } from 'vue'

/**
 * Enables Android Back Button / Browser Back / PC Mouse Side Button to close a modal/drawer.
 *
 * 实现原理：
 * - 打开弹框时 pushState 一个 history 条目，使 URL 产生可后退的 state
 * - 通过 UI（关闭按钮/遮罩）关闭时，主动 history.back() 消费该 state
 * - 真正的后退（侧滑/侧键/浏览器后退）触发 popstate 时，关闭栈顶弹框
 *
 * 支持嵌套弹框和弹框内视图切换（逐级后退）：使用全局栈 + 单例 popstate 监听器，
 * 确保关闭内层弹框/视图时不会误伤外层。
 *
 * 同时支持「同时关闭多个层级」的场景（如关闭弹框时连带重置内部编辑视图），
 * 使用计数器而非单一标记，确保每个 UI 主动 back 产生的 popstate 都被正确消费。
 *
 * @param isOpen - 控制弹框/视图可见性的 boolean ref
 */

// ── 全局协调状态（模块单例） ──
/** 当前打开的弹框/视图栈（栈顶为最近打开的层级） */
const openStack: Array<Ref<boolean>> = []
/**
 * 计数器：记录由 UI 主动关闭时调用 history.back() 产生的待消费 popstate 数量。
 * 每次 UI 关闭一个层级 → consumeCount++；每次 popstate → 若 >0 则 -- 并跳过。
 */
let consumeCount = 0
/** 全局 popstate 监听器是否已安装 */
let globalListenerInstalled = false
/** 记录每个 ref 是否正在被 popstate 关闭（避免 watch 再次 history.back） */
const closingViaPopstate = new WeakMap<Ref<boolean>, boolean>()

function globalPopStateHandler() {
  // 若是 UI 关闭时主动 back 产生的 popstate，消费掉并跳过
  if (consumeCount > 0) {
    consumeCount--
    return
  }
  // 真正的后退：关闭栈顶弹框
  const top = openStack[openStack.length - 1]
  if (top && top.value) {
    closingViaPopstate.set(top, true)
    top.value = false
  }
}

function ensureGlobalListener() {
  if (!globalListenerInstalled) {
    window.addEventListener('popstate', globalPopStateHandler)
    globalListenerInstalled = true
  }
}

export function useBackClose(isOpen: Ref<boolean>) {
  ensureGlobalListener()

  watch(isOpen, (val) => {
    if (val) {
      // 打开弹框：入栈 + pushState
      openStack.push(isOpen)
      window.history.pushState({ modalOpen: true }, '')
    } else {
      // 关闭弹框：出栈
      const idx = openStack.indexOf(isOpen)
      if (idx !== -1) {
        openStack.splice(idx, 1)
      }

      if (closingViaPopstate.get(isOpen)) {
        // popstate 导致的关闭，history state 已被浏览器消费，无需再 back
        closingViaPopstate.set(isOpen, false)
      } else {
        // UI 导致的关闭，需要消费打开时 push 的 state
        consumeCount++
        window.history.back()
      }
    }
  })

  onUnmounted(() => {
    // 组件卸载时清理栈中残留的引用
    const idx = openStack.indexOf(isOpen)
    if (idx !== -1) {
      openStack.splice(idx, 1)
    }
  })
}
