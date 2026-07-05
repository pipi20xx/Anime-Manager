import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useAggregatedRuleHistory(props: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const items = ref<any[]>([])
  const total = ref(0)
  const offset = ref(0)
  const hasMore = ref(true)
  const LIMIT = 50

  // 筛选状态
  const selectedRuleIds = ref<number[]>([])
  const keyword = ref('')

  const clientOptions = computed(() => {
    return (props.clients || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const buildQuery = () => {
    const params = new URLSearchParams()
    params.set('limit', String(LIMIT))
    params.set('offset', String(offset.value))
    if (selectedRuleIds.value.length > 0) {
      params.set('rule_ids', selectedRuleIds.value.join(','))
    }
    if (keyword.value.trim()) {
      params.set('keyword', keyword.value.trim())
    }
    return params.toString()
  }

  const fetchItems = async (append = false) => {
    if (!append) {
      offset.value = 0
      items.value = []
      hasMore.value = true
    }
    if (!hasMore.value) return

    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/rules/history/all?${buildQuery()}`)
      const data = await res.json()
      const newItems = data.items || []
      total.value = data.total || 0

      if (newItems.length < LIMIT) hasMore.value = false

      if (append) {
        items.value.push(...newItems)
      } else {
        items.value = newItems
      }
      offset.value += newItems.length
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  // 筛选条件变化时重置并从头拉取
  const applyFilter = () => {
    fetchItems(false)
  }

  const handleDownload = async (item: any, clientId: string) => {
    if (!item.link) {
      message.warning('该记录无资源链接')
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/clients/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: clientId,
          url: item.link,
          title: item.title
        })
      })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('请求失败')
    }
  }

  const handleDelete = async (item: any) => {
    try {
      await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(item.guid)}`, { method: 'DELETE' })
      // 局部移除
      const idx = items.value.findIndex(i => i.guid === item.guid)
      if (idx >= 0) items.value.splice(idx, 1)
      total.value = Math.max(0, total.value - 1)
      message.success('已清除记录')
    } catch (e) {
      console.error(e)
    }
  }

  return {
    loading,
    items,
    total,
    offset,
    hasMore,
    clientOptions,
    selectedRuleIds,
    keyword,
    fetchItems,
    applyFilter,
    handleDownload,
    handleDelete
  }
}
