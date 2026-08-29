import { ref } from 'vue'
import { api } from '@/api/client'

/**
 * 媒体规格字段的规范值选项 (分辨率/编码/字幕语言/制作组等)。
 *
 * 数据来自 GET /api/priority/field-options:
 * - 封闭字段与识别端归一化输出同源 (recognition_engine/field_options.py)
 * - team 从已识别的 feed_items 按频次自动聚合
 * 模块级缓存, 多个弹窗共享一份, 不重复请求。
 */
const options = ref<Record<string, string[]>>({})
let pending: Promise<void> | null = null
let loaded = false

export function useFieldOptions() {
  async function load() {
    if (loaded) return
    if (!pending) {
      pending = api.get<Record<string, string[]>>('/api/priority/field-options')
        .then(d => { options.value = d || {}; loaded = true })
        .catch(() => { /* 失败时下拉无选项, 组件仍可手输 */ })
        .finally(() => { pending = null })
    }
    await pending
  }

  return { options, load }
}
