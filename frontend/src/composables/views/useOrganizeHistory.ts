import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'

export function useOrganizeHistory() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const history = ref<any[]>([])
  const searchQuery = ref('')
  const statusFilter = ref('all') // all, success, failed
  
  const page = ref(0)
  const pageSize = ref(20)
  const hasMore = ref(true)

  const fetchData = async (isRefresh = false) => {
    if (loading.value) return
    if (isRefresh) {
      page.value = 0
      hasMore.value = true
      // Don't clear history immediately to avoid flicker, clear after success
    }
    
    if (!hasMore.value) return

    loading.value = true
    try {
      const offset = page.value * pageSize.value
      const res = await fetch(`${API_BASE}/api/organize/history?limit=${pageSize.value}&offset=${offset}`)
      const data = await res.json()
      
      // 为每个 item 添加 shouldDeleteFile 属性
      const dataWithFlag = data.map((item: any) => ({
        ...item,
        shouldDeleteFile: false
      }))
      
      if (isRefresh) {
        history.value = dataWithFlag
      } else {
        history.value.push(...dataWithFlag)
      }
      
      if (data.length < pageSize.value) {
        hasMore.value = false
      } else {
        page.value++
      }
    } catch (e) {
      message.error('加载历史记录失败')
    } finally {
      loading.value = false
    }
  }

  const loadMore = () => {
    fetchData(false)
  }

  const deleteItem = async (id: number, deleteFile: boolean = false) => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/history/${id}?delete_file=${deleteFile}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.success) {
        message.success(deleteFile ? '记录及文件已删除' : '记录已删除')
        const index = history.value.findIndex(item => item.id === id)
        if (index !== -1) {
          history.value.splice(index, 1)
        }
      } else {
        message.error(data.message || '删除失败')
      }
    } catch (e) { message.error('删除失败') }
  }

  const clearAll = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/history/clear`, { method: 'DELETE' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message || '历史记录已清空')
        history.value = []
      } else {
        message.error(data.detail || '清空失败')
      }
    } catch (e) { 
      message.error('请求服务器失败') 
    } finally {
      fetchData()
    }
  }

  const filteredHistory = computed(() => {
    let result = history.value
    
    if (statusFilter.value !== 'all') {
      result = result.filter(item => item.status === statusFilter.value)
    }

    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      result = result.filter(item => 
        item.title?.toLowerCase().includes(q) || 
        item.filename?.toLowerCase().includes(q) ||
        item.source_path?.toLowerCase().includes(q)
      )
    }
    
    return result
  })

  const getActionLabel = (type: string) => {
    const map: any = {
      'move': '移动',
      'copy': '复制',
      'link': '硬链',
      'cd2_move': 'CD2移动',
      'cd2_copy': 'CD2复制'
    }
    return map[type] || type
  }

  const formatTime = (timeStr: string) => {
    if (!timeStr) return '-'
    return timeStr.replace('T', ' ').split('.')[0]
  }

  onMounted(fetchData)

  return {
    loading,
    history,
    searchQuery,
    statusFilter,
    filteredHistory,
    hasMore,
    fetchData,
    loadMore,
    deleteItem,
    clearAll,
    getActionLabel,
    formatTime
  }
}
