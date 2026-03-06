import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'

export function useSubscriptionView() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // Data
  const feeds = ref<any[]>([])
  const rules = ref<any[]>([])
  const clients = ref<any[]>([])
  const loading = ref(false)
  const syncing = ref(false)

  // Modals
  const showFeedModal = ref(false)
  const showRuleModal = ref(false)
  const showItemsModal = ref(false)
  const showPreviewModal = ref(false)
  const showHistoryModal = ref(false)
  
  const currentItem = ref<any>(null)
  const previewRuleData = ref<any>(null)
  const isNew = ref(false)

  // Fetching
  const fetchData = async () => {
    loading.value = true
    try {
      const [fRes, rRes, cRes] = await Promise.all([
        fetch(`${API_BASE}/api/feeds`),
        fetch(`${API_BASE}/api/rules`),
        fetch(`${API_BASE}/api/clients`)
      ])
      feeds.value = await fRes.json()
      rules.value = await rRes.json()
      clients.value = await cRes.json()
    } catch (e) {
      message.error('加载数据失败')
    } finally {
      loading.value = false
    }
  }

  // Feeds CRUD
  const openAddFeed = () => { currentItem.value = null; isNew.value = true; showFeedModal.value = true }
  const openEditFeed = (row: any) => { currentItem.value = row; isNew.value = false; showFeedModal.value = true }

  const saveFeed = async (data: any) => {
    try {
      await fetch(`${API_BASE}/api/feeds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      message.success('保存成功')
      fetchData()
    } catch (e) { message.error('保存失败') }
  }

  const deleteFeed = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/feeds/${id}`, { method: 'DELETE' })
      message.success('已删除')
      fetchData()
    } catch (e) { message.error('删除失败') }
  }

  const openViewItems = (row: any) => {
    currentItem.value = row
    showItemsModal.value = true
  }

  const openViewHistory = (row: any) => {
    currentItem.value = row
    showHistoryModal.value = true
  }

  const resetFeedHistory = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/${id}/reset`, { method: 'POST' })
      const data = await res.json()
      message.success(data.message || '重置成功')
    } catch (e) { message.error('重置失败') }
  }

  // Rules CRUD
  const openAddRule = () => { currentItem.value = null; isNew.value = true; showRuleModal.value = true }
  const openEditRule = (row: any) => { currentItem.value = row; isNew.value = false; showRuleModal.value = true }

  const saveRule = async (data: any) => {
    try {
      await fetch(`${API_BASE}/api/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      message.success('规则保存成功')
      fetchData()
    } catch (e) { message.error('保存失败') }
  }

  const duplicateRule = async (rule: any) => {
    const newRule = { ...rule }
    delete newRule.id
    newRule.name = newRule.name + ' (副本)'
    
    try {
      await fetch(`${API_BASE}/api/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRule)
      })
      message.success('规则复制成功')
      fetchData()
    } catch (e) { message.error('复制失败') }
  }

  const deleteRule = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/rules/${id}`, { method: 'DELETE' })
      message.success('规则已删除')
      fetchData()
    } catch (e) { message.error('删除失败') }
  }

  // Actions
  const handlePreviewRule = (data: any) => {
    previewRuleData.value = data
    showPreviewModal.value = true
  }

  const runNow = async () => {  syncing.value = true
    try {
      await fetch(`${API_BASE}/api/rss/run`, { method: 'POST' })
      message.success('已触发 RSS 刷新')
    } catch (e) { message.error('触发失败') }
    finally { syncing.value = false }
  }

  const retryRecognition = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rss/recognition/retry`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
      } else {
        message.error(data.message)
      }
    } catch (e) { message.error('触发重试失败') }
  }

  const clearCache = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rss/recognition/clear`, { method: 'POST' })
      const data = await res.json()
      message.success(data.message)
    } catch (e) { message.error('重置失败') }
  }

  const clearBlacklist = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/cache/clear_blacklist`, { method: 'POST' })
      const data = await res.json()
      message.success(data.message)
    } catch (e) { message.error('清空失败') }
  }

  const syncJackettFeeds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sync-jackett`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
        fetchData()
      } else {
        message.error(data.message || '同步失败')
      }
    } catch (e: any) {
      message.error(e.message || '同步失败')
    }
  }

  return {
    feeds,
    rules,
    clients,
    loading,
    syncing,
    showFeedModal,
    showRuleModal,
    showItemsModal,
    showPreviewModal,
    showHistoryModal,
    currentItem,
    previewRuleData,
    isNew,
    fetchData,
    openAddFeed,
    openEditFeed,
    saveFeed,
    deleteFeed,
    openViewItems,
    openViewHistory,
    resetFeedHistory,
    openAddRule,
    openEditRule,
    saveRule,
    duplicateRule,
    deleteRule,
    handlePreviewRule,
    runNow,
    retryRecognition,
    clearCache,
    clearBlacklist,
    syncJackettFeeds
  }
}
