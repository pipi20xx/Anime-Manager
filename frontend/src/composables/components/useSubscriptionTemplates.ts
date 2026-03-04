import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function useSubscriptionTemplates(props: { show: boolean, clients: any[] }, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const templates = ref<any[]>([])
  const loading = ref(false)
  const showEdit = ref(false)
  const feeds = ref<any[]>([])

  const editModel = ref<any>({
    id: null,
    name: '',
    is_default: false,
    filter_res: '',
    filter_team: '',
    filter_source: '',
    filter_codec: '',
    filter_audio: '',
    filter_sub: '',
    filter_effect: '',
    filter_platform: '',
    include_keywords: '',
    exclude_keywords: '',
    target_client_id: null,
    save_path: '',
    category: 'Anime',
    target_feeds: [],
    auto_fill: true
  })

  const fetchFeeds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds`)
      feeds.value = await res.json()
    } catch (e) {}
  }

  const fetchTemplates = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions/templates`)
      templates.value = await res.json()
    } catch (e) {
      message.error('加载模板失败')
    } finally {
      loading.value = false
    }
  }

  const openAdd = () => {
    editModel.value = {
      id: null,
      name: '',
      is_default: templates.value.length === 0,
      filter_res: '',
      filter_team: '',
      filter_source: '',
      filter_codec: '',
      filter_audio: '',
      filter_sub: '',
      filter_effect: '',
      filter_platform: '',
      include_keywords: '',
      exclude_keywords: '',
      target_client_id: props.clients.length > 0 ? props.clients[0].id : null,
      save_path: '',
      category: 'Anime',
      target_feeds: [],
      auto_fill: true
    }
    showEdit.value = true
  }

  const openEdit = (row: any) => {
    editModel.value = { ...row }
    if (typeof editModel.value.target_feeds === 'string' && editModel.value.target_feeds) {
      editModel.value.target_feeds = editModel.value.target_feeds.split(',').filter((x: string) => x)
    } else {
      editModel.value.target_feeds = []
    }
    showEdit.value = true
  }

  const saveTemplate = async () => {
    if (!editModel.value.name) return message.warning('请输入模板名称')
    const payload = { ...editModel.value }
    if (Array.isArray(payload.target_feeds)) {
      payload.target_feeds = payload.target_feeds.join(',')
    }
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        message.success('模板保存成功')
        showEdit.value = false
        fetchTemplates()
      }
    } catch (e) { message.error('保存失败') }
  }

  const deleteTemplate = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/subscriptions/templates/${id}`, { method: 'DELETE' })
      message.success('已删除')
      fetchTemplates()
    } catch (e) { message.error('删除失败') }
  }

  const setDefault = async (row: any) => {
    const copy = { ...row, is_default: true }
    try {
      await fetch(`${API_BASE}/api/subscriptions/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(copy)
      })
      message.success(`已将 ${row.name} 设为默认模板`)
      fetchTemplates()
    } catch (e) {}
  }

  watch(() => props.show, (val) => {
    if (val) {
      fetchTemplates()
      fetchFeeds()
    }
  })

  const close = () => emit('update:show', false)

  return {
    templates, loading, showEdit, feeds, editModel,
    openAdd, openEdit, saveTemplate, deleteTemplate, setDefault,
    close
  }
}
