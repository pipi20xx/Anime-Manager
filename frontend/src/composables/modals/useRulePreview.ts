import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useRulePreview(props: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
  
  const loading = ref(false)
  const items = ref<any[]>([])

  const clientOptions = computed(() => {
    return (props.clients || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const fetchPreview = async () => {
    if (!props.ruleData) return
    loading.value = true
    items.value = []
    try {
      const res = await fetch(`${API_BASE}/api/rss/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(props.ruleData)
      })
      items.value = await res.json()
    } catch (e) {
      console.error('预览获取失败', e)
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
          body: JSON.stringify({ guid: item.guid, title: item.title, feed_id: item.feed_id })
        })
      } else {
        await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(item.guid)}`, { method: 'DELETE' })
      }
      fetchPreview()
    } catch (e) {
      console.error(e)
    }
  }

  return {
    loading,
    items,
    clientOptions,
    fetchPreview,
    handleDownload,
    handleToggleHistory
  }
}
