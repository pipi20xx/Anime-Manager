import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

export function useRssDetectManager() {
  const message = useMessage()

  const tasks = ref<any[]>([])
  const loading = ref(false)
  const showEdit = ref(false)
  const editingTask = ref<any>(null)
  const testing = ref(false)
  const testResult = ref<any>(null)

  const templates = ref<any[]>([])
  const clients = ref<any[]>([])

  const editModel = ref<any>({
    id: null,
    name: '',
    rss_url: '',
    enabled: true,
    template_id: null as number | null,
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
    target_client_id: null as string | null,
    save_path: '',
    category: 'Anime',
    auto_fill: true,
    interval_minutes: 360
  })

  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions/templates`)
      if (res.ok) templates.value = await res.json()
    } catch (e) {}
  }

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clients`)
      if (res.ok) clients.value = await res.json()
    } catch (e) {}
  }

  const fetchTasks = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/detect/tasks`)
      if (res.ok) tasks.value = await res.json()
    } catch (e) {
      message.error('加载任务失败')
    } finally {
      loading.value = false
    }
  }

  const openAdd = () => {
    editingTask.value = null
    testResult.value = null
    editModel.value = {
      id: null,
      name: '',
      rss_url: '',
      enabled: true,
      template_id: templates.value.find((t: any) => t.is_default)?.id || null,
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
      target_client_id: clients.value.length > 0 ? clients.value[0].id : null,
      save_path: '',
      category: 'Anime',
      auto_fill: true,
      interval_minutes: 360
    }
    showEdit.value = true
  }

  const openEdit = (row: any) => {
    editingTask.value = row
    testResult.value = null
    editModel.value = { ...row }
    showEdit.value = true
  }

  const saveTask = async () => {
    if (!editModel.value.rss_url.trim()) return message.warning('请输入 RSS 链接')
    
    const payload = { ...editModel.value }
    if (!payload.name) {
      payload.name = `RSS探测-${new Date().toLocaleString()}`
    }

    try {
      const res = await fetch(`${API_BASE}/api/detect/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (res.ok) {
        message.success('任务保存成功')
        showEdit.value = false
        fetchTasks()
      } else {
        const data = await res.json()
        message.error(data.detail || '保存失败')
      }
    } catch (e) {
      message.error('保存失败')
    }
  }

  const deleteTask = async (taskId: number) => {
    try {
      await fetch(`${API_BASE}/api/detect/tasks/${taskId}`, { method: 'DELETE' })
      message.success('已删除任务')
      fetchTasks()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const runTask = async (taskId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/detect/tasks/${taskId}/run`, { method: 'POST' })
      const data = await res.json()
      
      if (data.created > 0) {
        message.success(`成功创建 ${data.created} 个订阅，跳过 ${data.skipped} 个已存在的`)
      } else {
        message.info(`未发现新番剧需要订阅，跳过 ${data.skipped} 个已存在的`)
      }
      
      fetchTasks()
    } catch (e) {
      message.error('执行失败')
    }
  }

  const testRss = async () => {
    if (!editModel.value.rss_url.trim()) return message.warning('请输入 RSS 链接')

    testing.value = true
    testResult.value = null

    try {
      const config: any = {
        rss_url: editModel.value.rss_url.trim(),
        template_id: editModel.value.template_id,
        filter_res: editModel.value.filter_res,
        filter_team: editModel.value.filter_team,
        filter_source: editModel.value.filter_source,
        filter_codec: editModel.value.filter_codec,
        filter_audio: editModel.value.filter_audio,
        filter_sub: editModel.value.filter_sub,
        filter_effect: editModel.value.filter_effect,
        filter_platform: editModel.value.filter_platform
      }

      const res = await fetch(`${API_BASE}/api/detect/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })

      const data = await res.json()

      if (!res.ok) {
        message.error(data.detail || '测试失败')
        return
      }

      testResult.value = data
      
      if (data.detected_shows && data.detected_shows.length > 0) {
        message.success(`识别到 ${data.detected_shows.length} 个番剧`)
      } else {
        message.info('未识别到任何番剧')
      }
    } catch (e: any) {
      message.error('测试失败: ' + (e.message || '未知错误'))
    } finally {
      testing.value = false
    }
  }

  const toggleEnabled = async (task: any) => {
    try {
      const updated = { ...task, enabled: !task.enabled }
      await fetch(`${API_BASE}/api/detect/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
      fetchTasks()
    } catch (e) {}
  }

  const init = () => {
    fetchTasks()
    fetchTemplates()
    fetchClients()
  }

  return {
    tasks, loading, showEdit, editingTask, testResult, testing,
    templates, clients, editModel,
    openAdd, openEdit, saveTask, deleteTask, runTask, testRss, toggleEnabled, init
  }
}
