import { onMounted, onUnmounted, type Ref } from 'vue'

/**
 * useDragScroll - 让容器内的可滚动元素支持鼠标拖拽水平滚动
 *
 * 用法:
 * const tableWrapperRef = ref<HTMLElement | null>(null)
 * useDragScroll(tableWrapperRef)
 *
 * <div ref="tableWrapperRef">
 *   <n-data-table ... />
 * </div>
 *
 * 原理:
 * - 在容器内查找所有可水平滚动的元素 (scrollWidth > clientWidth)
 * - 为它们绑定 mousedown / mousemove / mouseup 事件
 * - 鼠标按下后移动超过阈值才进入拖拽模式，避免误触
 * - 拖拽时禁用文本选择，松开后恢复
 * - 使用 MutationObserver 监听 DOM 变化，自动为新出现的滚动元素绑定事件
 */
export function useDragScroll(
  containerRef: Ref<HTMLElement | null>,
  options?: {
    /** 拖拽触发阈值 (px)，移动超过此距离才认为是拖拽而非点击 */
    threshold?: number
    /** 自定义滚动元素选择器，默认自动检测 */
    selector?: string
  }
) {
  const threshold = options?.threshold ?? 5
  const customSelector = options?.selector

  const attachedElements = new WeakSet<Element>()
  let observer: MutationObserver | null = null
  let debounceTimer: number | null = null

  /** 检测元素是否可水平滚动 */
  const isHorizontallyScrollable = (el: HTMLElement): boolean => {
    return el.scrollWidth > el.clientWidth + 1
  }

  /** 为单个滚动元素绑定拖拽事件 */
  const attachDragScroll = (el: HTMLElement) => {
    if (attachedElements.has(el)) return
    attachedElements.add(el)

    let isDown = false
    let isDragging = false
    let startX = 0
    let startScrollLeft = 0
    let pointerId = -1

    const onMouseDown = (e: MouseEvent) => {
      // 仅响应鼠标左键
      if (e.button !== 0) return
      // 不干扰交互元素
      const target = e.target as HTMLElement
      if (target.closest('button, a, input, textarea, select, .n-checkbox, .n-switch, .n-popover, [contenteditable]')) return
      // 仅在可滚动时启用
      if (!isHorizontallyScrollable(el)) return

      isDown = true
      isDragging = false
      startX = e.pageX
      startScrollLeft = el.scrollLeft
      pointerId = e.pointerId || -1
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!isDown) return
      const dx = e.pageX - startX

      // 超过阈值才进入拖拽模式
      if (!isDragging && Math.abs(dx) > threshold) {
        isDragging = true
        el.style.cursor = 'grabbing'
        el.style.userSelect = 'none'
      }

      if (isDragging) {
        e.preventDefault()
        el.scrollLeft = startScrollLeft - dx
      }
    }

    const endDrag = () => {
      if (isDragging) {
        el.style.cursor = 'grab'
        el.style.userSelect = ''
      }
      isDown = false
      isDragging = false
      pointerId = -1
    }

    el.addEventListener('mousedown', onMouseDown)
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', endDrag)

    // 初始 cursor
    el.style.cursor = 'grab'

    // 在元素上存储清理函数
    ;(el as any).__dragScrollCleanup = () => {
      el.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', endDrag)
      el.style.cursor = ''
      el.style.userSelect = ''
      attachedElements.delete(el)
    }
  }

  /** 扫描容器内的可滚动元素并绑定 */
  const scanAndAttach = () => {
    const container = containerRef.value
    if (!container) return

    let scrollEls: NodeListOf<Element>
    if (customSelector) {
      scrollEls = container.querySelectorAll(customSelector)
    } else {
      // 自动检测：naive-ui 常见滚动容器 + 通用 overflow 元素
      scrollEls = container.querySelectorAll(
        '.n-data-table-base-table-body, .n-scrollbar-container, .n-data-table-wrapper, [style*="overflow"], [class*="scroll"]'
      )
    }

    scrollEls.forEach(el => {
      const htmlEl = el as HTMLElement
      // 只绑定可水平滚动的元素
      if (isHorizontallyScrollable(htmlEl)) {
        attachDragScroll(htmlEl)
      }
    })
  }

  /** 带防抖的扫描 */
  const debouncedScan = () => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(scanAndAttach, 100)
  }

  /** 清理所有已绑定的元素 */
  const cleanupAll = () => {
    const container = containerRef.value
    if (!container) return
    // 查找所有有清理函数的元素
    const allEls = container.querySelectorAll('*')
    allEls.forEach(el => {
      const cleanup = (el as any).__dragScrollCleanup
      if (typeof cleanup === 'function') {
        cleanup()
        delete (el as any).__dragScrollCleanup
      }
    })
  }

  onMounted(() => {
    const container = containerRef.value
    if (!container) return

    // 初始扫描 (延迟等待 naive-ui 渲染完成)
    setTimeout(scanAndAttach, 300)

    // 监听 DOM 变化，自动绑定新出现的滚动元素
    observer = new MutationObserver(() => {
      debouncedScan()
    })
    observer.observe(container, { childList: true, subtree: true })
  })

  onUnmounted(() => {
    if (observer) {
      observer.disconnect()
      observer = null
    }
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    cleanupAll()
  })

  return { rescan: debouncedScan }
}
