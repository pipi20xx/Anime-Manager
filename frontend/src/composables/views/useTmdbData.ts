import { ref, reactive, onMounted, h } from 'vue'
import { useMessage, useDialog, NButton, NIcon } from 'naive-ui'
import { DeleteSweepOutlined, CloseOutlined } from '@vicons/material'

export function useTmdbData() {
  const message = useMessage()
  const dialog = useDialog()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const browserData = ref<any[]>([])
  const browserTotal = ref(0)
  const browserPage = ref(1)
  const browserSearch = ref('')
  const browserLoading = ref(false)

  const showEditModal = ref(false)
  const isEditing = ref(false)
  const editForm = reactive({
    id: '', type: 'tv', title: '', poster_path: '', overview: '', manual: true
  })

  const showSyncModal = ref(false)
  const syncLoading = ref(false)
  const syncForm = reactive({ address: '' })

  const fetchBrowserData = async () => {
    browserLoading.value = true
    try {
      const url = `${API_BASE}/api/tmdb_full/list?page=${browserPage.value}&search=${encodeURIComponent(browserSearch.value)}`
      const res = await fetch(url)
      const data = await res.json()
      browserData.value = data.items || []
      browserTotal.value = data.total || 0
    } catch (e) { message.error('数据加载失败') }
    finally { browserLoading.value = false }
  }

  const handleBrowserSearch = () => {
    browserPage.value = 1; fetchBrowserData()
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
      onPositiveClick: async () => {
        await fetch(`${API_BASE}/api/cache/${type}/${id}`, { method: 'DELETE' })
        message.success('已移除')
        fetchBrowserData()
      }
    })
  }

  const handleSyncSytmdb = async () => {
    showSyncModal.value = true
  }

  const runSyncSytmdb = async () => {
    if (!syncForm.address) return
    syncLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/cache/sytmdb_sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(syncForm)
      })
      const result = await res.json()
      message.success(`同步完成: ${result.message}`)
      showSyncModal.value = false
      fetchBrowserData()
    } catch (e) { message.error('同步失败') }
    finally { syncLoading.value = false }
  }

  const handleRefreshAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tmdb_full/refresh_all`, { method: 'POST' })
      if (res.ok) message.success('全量同步任务已在后台启动')
    } catch (e) { message.error('请求异常') }
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
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, {
          onClick: () => dialog.destroyAll()
        }, { icon: () => h(NIcon, null, { default: () => h(CloseOutlined) }), default: () => '取消' }),
        h(NButton, {
          type: 'warning',
          onClick: async () => {
            try {
              const res = await fetch(`${API_BASE}/api/cache/clear_fingerprints`, { method: 'POST' })
              message.success("智能记忆已清空")
              dialog.destroyAll()
            } catch (e) {
              message.error("操作失败")
            }
          }
        }, { icon: () => h(NIcon, null, { default: () => h(DeleteSweepOutlined) }), default: () => '清空记忆' })
      ])
    })
  }

  onMounted(fetchBrowserData)

  return {
    browserData,
    browserTotal,
    browserPage,
    browserSearch,
    browserLoading,
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
    handleExport,
    clearFingerprints
  }
}
