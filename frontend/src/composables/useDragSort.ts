import { ref, type Ref } from 'vue'

/**
 * useDragSort — 通用卡片拖拽排序 composable
 *
 * 适用于 v-row / v-col 网格布局中的卡片拖拽重排。
 * 不依赖任何第三方拖拽库，纯 HTML5 Drag & Drop API。
 *
 * 用法 1 — 直接修改 ref（数据中心 RulesTab，自有数据）：
 *   const rules = ref<any[]>([])
 *   const { dragIndex, dragOverIndex, onDragStart, onDragOver, onDragEnd } = useDragSort(rules, {
 *     onSort: async () => { await saveToBackend(rules.value) },
 *   })
 *
 * 用法 2 — 通过回调获取新数组（整理器 RulesTab，props 数据）：
 *   const { dragIndex, dragOverIndex, onDragStart, onDragOver, onDragEnd } = useDragSort(() => props.rules, {
 *     onSort: (newList) => { emit('update:rules', newList); emit('save') },
 *   })
 *
 * 模板中:
 *   <v-col
 *     v-for="(item, index) in list"
 *     draggable="true"
 *     @dragstart="onDragStart(index, $event)"
 *     @dragover="onDragOver(index, $event)"
 *     @dragend="onDragEnd"
 *     :class="{ 'drag-sorting': dragIndex === index, 'drag-over': dragOverIndex === index }"
 *   >
 *
 * 特点：
 *   - 拖拽时卡片半透明 + 占位高亮
 *   - 排序后自动更新源数组
 *   - 通过回调通知外部持久化
 */
export function useDragSort(
  listRefOrGetter: Ref<any[]> | (() => any[]),
  options?: {
    /** 排序完成回调，接收新数组（不可变模式）或无参（可变模式） */
    onSort?: (newList?: any[]) => void | Promise<void>
  },
) {
  const dragIndex = ref(-1)
  const dragOverIndex = ref(-1)

  /** 获取当前列表 */
  function getList(): any[] {
    if (typeof listRefOrGetter === 'function') return listRefOrGetter()
    return listRefOrGetter.value
  }

  /** 是否为可变模式（传入 Ref） */
  function isMutable(): boolean {
    return typeof listRefOrGetter !== 'function'
  }

  function onDragStart(index: number, event: DragEvent) {
    dragIndex.value = index
    dragOverIndex.value = -1

    // 设置拖拽数据（必须，否则某些浏览器不会触发 dragover）
    event.dataTransfer!.effectAllowed = 'move'
    event.dataTransfer!.setData('text/plain', String(index))

    // 设置半透明拖拽图像
    const target = event.target as HTMLElement
    if (target) {
      target.style.opacity = '0.5'
    }
  }

  function onDragOver(index: number, event: DragEvent) {
    event.preventDefault()
    event.dataTransfer!.dropEffect = 'move'

    if (dragIndex.value !== -1 && dragIndex.value !== index) {
      dragOverIndex.value = index
    }
  }

  async function onDragEnd() {
    const from = dragIndex.value
    const to = dragOverIndex.value

    // 恢复透明度
    document.querySelectorAll('.drag-sorting').forEach((el) => {
      ;(el as HTMLElement).style.opacity = ''
    })

    dragIndex.value = -1
    dragOverIndex.value = -1

    if (from !== -1 && to !== -1 && from !== to) {
      applySort(from, to)
    }
  }

  function applySort(from: number, to: number) {
    if (isMutable()) {
      // 可变模式：直接修改源数组
      const list = (listRefOrGetter as Ref<any[]>).value
      const item = list.splice(from, 1)[0]
      list.splice(to, 0, item)
      options?.onSort?.()
    } else {
      // 不可变模式：返回新数组
      const list = getList()
      const newList = [...list]
      const [item] = newList.splice(from, 1)
      newList.splice(to, 0, item)
      options?.onSort?.(newList)
    }
  }

  return {
    dragIndex,
    dragOverIndex,
    onDragStart,
    onDragOver,
    onDragEnd,
    applySort,
  }
}
