import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function useTmdbBlocklist(props: { show: boolean }, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const blocklist = ref<any[]>([])
  const loading = ref(false)
  const showAdd = ref(false)
  const currentItem = ref<any>({})

  const fetchList = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/tmdb-blocklist`)
      if (res.ok) blocklist.value = await res.json()
    } catch (e) {
      message.error('加载屏蔽列表失败')
    } finally {
      loading.value = false
    }
  }

  const openAdd = () => {
    currentItem.value = { tmdb_id: '', media_type: 'tv', title: '', reason: '' }
    showAdd.value = true
  }

  const save = async () => {
    if (!currentItem.value.tmdb_id) {
      message.warning('TMDB ID 不能为空')
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/tmdb-blocklist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentItem.value)
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || '保存失败')
      }
      message.success('添加成功')
      showAdd.value = false
      fetchList()
    } catch (e: any) {
      message.error(e.message || '保存失败')
    }
  }

  const remove = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/tmdb-blocklist/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      message.success('删除成功')
      fetchList()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const close = () => {
    emit('update:show', false)
  }

  watch(() => props.show, (val) => {
    if (val) fetchList()
  })

  return {
    blocklist, loading, showAdd, currentItem,
    fetchList, openAdd, save, remove, close
  }
}
