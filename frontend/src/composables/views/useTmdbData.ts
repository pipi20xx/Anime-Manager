import { ref, reactive, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'

export function useTmdbData() {
  const message = useMessage()
  const dialog = useDialog()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const browserData = ref<any[]>([])
  const browserTotal = ref(0)
  const browserPage = ref(1)
  const browserSearch = ref('')
  const browserLoading = ref(false)
  const browserHasMore = ref(true)
  const PAGE_SIZE = 20

  const showEditModal = ref(false)
  const isEditing = ref(false)
  const editForm = reactive({
    id: '', type: 'tv', title: '', poster_path: '', overview: '', manual: true
  })

  const showSyncModal = ref(false)
  const syncLoading = ref(false)
  const syncForm = reactive({ 
    address: localStorage.getItem('sytmdb_address') || '', 
    token: localStorage.getItem('sytmdb_token') || '' 
  })

  const fetchBrowserData = async (append = false) => {
    if (append && !browserHasMore.value) return
    if (!append) {
      browserPage.value = 1
      browserData.value = []
      browserHasMore.value = true
    }
    browserLoading.value = true
    try {
      const url = `${API_BASE}/api/tmdb_full/list?page=${browserPage.value}&search=${encodeURIComponent(browserSearch.value)}`
      const res = await fetch(url)
      const data = await res.json()
      const newItems = data.items || []
      browserTotal.value = data.total || 0
      if (newItems.length < PAGE_SIZE) browserHasMore.value = false
      if (append) {
        browserData.value.push(...newItems)
      } else {
        browserData.value = newItems
      }
      browserPage.value++
    } catch (e) { message.error('数据加载失败') }
    finally { browserLoading.value = false }
  }

  const handleBrowserSearch = () => {
    fetchBrowserData(false)
  }

  const openCreate = () => {
    isEditing.value = false
    Object.assign(editForm, { id: '', type: 'tv', title: '', poster_path: '', overview: '', manual: true })
    showEditModal.value = true
  }

  const openEdit = (item: any) => {
    isEditing.value = true
    Object.assign(editForm, {
      ...item,
      id: item.tmdb_id,
      type: item.media_type,
      poster_path: item.poster_path || '',
      overview: item.overview || '',
      manual: true
    })
    showEditModal.value = true
  }

  const saveMetadata = async () => {
    if (!editForm.id || !editForm.title) {
      message.warning('ID 和 标题为必填项')
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/cache`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      })
      if (res.ok) {
        message.success('保存成功')
        showEditModal.value = false
        fetchBrowserData()
      }
    } catch (e) { message.error('保存失败') }
  }

  const deleteMetadata = (item: any) => {
    const type = item.media_type || item.type
    const id = item.tmdb_id || item.id
    dialog.warning({
      title: '确认删除',
      content: `确定要移除 "${item.title}" 吗？`,
      positiveText: '确认删除',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await fetch(`${API_BASE}/api/cache/${type}/${id}`, { method: 'DELETE' })
          message.success('已移除')
          fetchBrowserData()
        } catch (e) {
          message.error('删除失败')
          return false
        }
      }
    })
  }

  const handleSyncSytmdb = async () => {
    message.info('同步任务已启动，请查看实时日志了解进度')
    try {
      const res = await fetch(`${API_BASE}/api/sytmdb/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      const data = await res.json()
      if (!res.ok) {
        message.error(data.detail || '启动同步失败')
      }
    } catch (e) { message.error('启动同步失败') }
  }

  const runSyncSytmdb = async () => {
    if (!syncForm.address) return
    localStorage.setItem('sytmdb_address', syncForm.address)
    localStorage.setItem('sytmdb_token', syncForm.token)
    showSyncModal.value = false
    message.info('同步任务已启动，请查看实时日志了解进度')
    try {
      await fetch(`${API_BASE}/api/sytmdb/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(syncForm)
      })
    } catch (e) { message.error('启动同步失败') }
  }

  const handleRefreshAll = async (options?: { olderThanDays?: number; year?: number; mediaType?: string }) => {
    try {
      const body: Record<string, any> = {}
      if (options?.olderThanDays) body.older_than_days = options.olderThanDays
      if (options?.year) body.year = options.year
      if (options?.mediaType) body.media_type = options.mediaType
      
      const res = await fetch(`${API_BASE}/api/tmdb_full/refresh_all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (res.ok) message.success(data.message || '全量同步任务已在后台启动')
    } catch (e) { message.error('请求异常') }
  }

  const refreshSingleId = ref<string | null>(null)

  const handleRefreshSingle = (item: any) => {
    const tmdbId = item.tmdb_id || item.id
    const mediaType = item.media_type || item.type
    if (!tmdbId || !mediaType) return
    dialog.warning({
      title: '确认刷新',
      content: `确定要从 TMDB 云端刷新 "${item.title}" 的元数据吗？\n刷新后除固定标题外，所有数据将被最新值覆盖。`,
      positiveText: '确认刷新',
      negativeText: '取消',
      onPositiveClick: async () => {
        refreshSingleId.value = String(tmdbId)
        try {
          const res = await fetch(`${API_BASE}/api/tmdb_full/refresh_all`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tmdb_id: String(tmdbId), media_type: mediaType })
          })
          const data = await res.json()
          if (res.ok) {
            message.success(data.message || '刷新任务已启动')
            await fetchBrowserData(false)
          } else {
            message.error(data.message || '刷新失败')
            return false
          }
        } catch (e) {
          message.error('请求异常')
          return false
        } finally {
          refreshSingleId.value = null
        }
      }
    })
  }

  const handleExport = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tmdb_full/export_dict`)
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tmdb_dict_${new Date().toISOString().slice(0,10)}.json`
      a.click()
      message.success('ID 字典已导出')
    } catch (e) { message.error('导出失败') }
  }

  const clearFingerprints = async () => {
    dialog.warning({
      title: '确认清空智能记忆',
      content: '这将删除所有智能记忆。',
      positiveText: '清空记忆',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await fetch(`${API_BASE}/api/cache/clear_fingerprints`, { method: 'POST' })
          message.success("智能记忆已清空")
        } catch (e) {
          message.error("操作失败")
          return false
        }
      }
    })
  }

  onMounted(fetchBrowserData)

  return {
    browserData,
    browserTotal,
    browserPage,
    browserSearch,
    browserLoading,
    browserHasMore,
    showEditModal,
    isEditing,
    editForm,
    showSyncModal,
    syncLoading,
    syncForm,
    fetchBrowserData,
    handleBrowserSearch,
    openCreate,
    openEdit,
    saveMetadata,
    deleteMetadata,
    handleSyncSytmdb,
    runSyncSytmdb,
    handleRefreshAll,
    handleRefreshSingle,
    refreshSingleId,
    handleExport,
    clearFingerprints
  }
}
