import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useAggregatedFeedItems(props: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const items = ref<any[]>([])
  const total = ref(0)
  const offset = ref(0)
  const hasMore = ref(true)
  const LIMIT = 50

  // 筛选状态
  const selectedFeedIds = ref<number[]>([])
  const keyword = ref('')

  const clientOptions = computed(() => {
    return (props.clients || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const buildQuery = () => {
    const params = new URLSearchParams()
    params.set('limit', String(LIMIT))
    params.set('offset', String(offset.value))
    if (selectedFeedIds.value.length > 0) {
      params.set('feed_ids', selectedFeedIds.value.join(','))
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
      const res = await fetch(`${API_BASE}/api/feeds/items/all?${buildQuery()}`)
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

  const handleToggleHistory = async (item: any, isAdd: boolean) => {
    try {
      if (isAdd) {
        await fetch(`${API_BASE}/api/rss/history`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ guid: item.guid, title: item.title, feed_id: item.feed_id })
        })
      } else {
        await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(item.guid)}`, { method: 'DELETE' })
      }
      // 局部更新
      item.is_downloaded = isAdd
    } catch (e) {
      console.error(e)
    }
  }

  const handleRetryRecognition = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/rss/recognition/retry`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('重试请求失败')
    } finally {
      loading.value = false
    }
  }

  // 批量清除下载记录：根据当前筛选的站点，不筛选则清除全部
  const handleClearHistory = async (): Promise<boolean> => {
    try {
      const qs = selectedFeedIds.value.length > 0
        ? `?feed_ids=${selectedFeedIds.value.join(',')}`
        : ''
      const res = await fetch(`${API_BASE}/api/feeds/reset-history${qs}`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
        await fetchItems(false)
        return true
      } else {
        message.error(data.message || '清除失败')
        return false
      }
    } catch (e) {
      message.error('清除请求失败')
      return false
    }
  }

  return {
    loading,
    items,
    total,
    offset,
    hasMore,
    clientOptions,
    selectedFeedIds,
    keyword,
    fetchItems,
    applyFilter,
    handleDownload,
    handleToggleHistory,
    handleRetryRecognition,
    handleClearHistory
  }
}
