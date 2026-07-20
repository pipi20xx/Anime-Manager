import { useDialog } from 'naive-ui'
import { useBackLayer } from './useBackClose'

/**
 * useBackDialog - 封装 naive-ui 的 useDialog，让所有确认弹框自动支持后退关闭。
 *
 * 用法与 useDialog 完全一致，直接替换即可：
 *   const dialog = useBackDialog()
 *   dialog.warning({ title: '确认删除', content: '...', ... })
 *
 * 实现原理：
 * - 每次调用 warning/error/info/success/create 时，pushState 一个 history 条目
 * - 通过 UI（确认/取消/关闭按钮/遮罩）关闭时，onAfterLeave → history.back() 消费 state
 * - 真正的后退（侧滑/侧键/浏览器后退）触发 popstate → destroy dialog（不重复 back）
 */
export function useBackDialog() {
  const dialog = useDialog()

  const wrap = (method: 'create' | 'warning' | 'error' | 'info' | 'success') => {
    return (options: any) => {
      // 标记：dialog 是否由 popstate（后退）触发关闭
      let closedByPopstate = false
      const originalOnAfterLeave = options.onAfterLeave

      const reactive = dialog[method]({
        ...options,
        onAfterLeave: () => {
          if (closedByPopstate) {
            // popstate 已消费 history state，仅从栈移除
            remove()
          } else {
            // UI 关闭：从栈移除 + history.back() 消费 state
            close()
          }
          originalOnAfterLeave?.()
        }
      })

      const { open, close, remove } = useBackLayer(() => {
        closedByPopstate = true
        reactive.destroy()
      })

      open()
      return reactive
    }
  }

  return {
    ...dialog,
    create: wrap('create'),
    warning: wrap('warning'),
    error: wrap('error'),
    info: wrap('info'),
    success: wrap('success'),
  }
}
