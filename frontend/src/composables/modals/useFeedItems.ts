import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useFeedItems(props: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
  
  const loading = ref(false)
  const items = ref<any[]>([])
  const offset = ref(0)
  const hasMore = ref(true)
  const LIMIT = 100

  const clientOptions = computed(() => {
    return (props.clients || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const fetchItems = async (append = false) => {
    if (!props.feed?.id) return
    if (!append) {
      offset.value = 0
      items.value = []
      hasMore.value = true
    }
    
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/feeds/${props.feed.id}/items?limit=${LIMIT}&offset=${offset.value}`)
      const newItems = await res.json()
      
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
          body: JSON.stringify({ guid: item.guid, title: item.title, feed_id: props.feed.id })
        })
      } else {
        await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(item.guid)}`, { method: 'DELETE' })
      }
      fetchItems(false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRetryRecognition = async () => {
    if (!props.feed?.id) return
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/feeds/${props.feed.id}/retry`, { method: 'POST' })
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

  return {
    loading,
    items,
    offset,
    hasMore,
    clientOptions,
    fetchItems,
    handleDownload,
    handleToggleHistory,
    handleRetryRecognition
  }
}
