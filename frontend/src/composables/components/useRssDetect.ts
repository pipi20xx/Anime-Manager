import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

export function useRssDetect(props: { show: boolean }, emit: any) {
  const message = useMessage()

  const loading = ref(false)
  const detecting = ref(false)
  const subscribing = ref(false)

  const rssUrl = ref('')
  const previewResult = ref<any>(null)
  const subscribeResult = ref<any>(null)

  const mode = ref<'template' | 'custom'>('template')
  const selectedTemplate = ref<number | null>(null)
  const templates = ref<any[]>([])

  const filterRes = ref('')
  const filterTeam = ref('')
  const filterSource = ref('')
  const filterCodec = ref('')
  const filterAudio = ref('')
  const filterSub = ref('')
  const filterEffect = ref('')
  const filterPlatform = ref('')
  const includeKeywords = ref('')
  const excludeKeywords = ref('')

  const targetClientId = ref<string | null>(null)
  const clients = ref<any[]>([])
  const savePath = ref('')
  const category = ref('Anime')
  const autoFill = ref(true)

  const saveAsTask = ref(false)
  const taskName = ref('')
  const intervalMinutes = ref(360)

  const tasks = ref<any[]>([])

  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions/templates`)
      if (res.ok) {
        templates.value = await res.json()
        const defaultTmpl = templates.value.find((t: any) => t.is_default)
        if (defaultTmpl) selectedTemplate.value = defaultTmpl.id
      }
    } catch (e) {}
  }

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clients`)
      if (res.ok) {
        clients.value = await res.json()
      }
    } catch (e) {}
  }

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/detect/tasks`)
      if (res.ok) {
        tasks.value = await res.json()
      }
    } catch (e) {}
  }

  const handlePreview = async () => {
    if (!rssUrl.value.trim()) {
      message.warning('请输入 RSS 链接')
      return
    }

    detecting.value = true
    previewResult.value = null
    subscribeResult.value = null

    try {
      const config: any = {
        rss_url: rssUrl.value.trim()
      }

      if (mode.value === 'template' && selectedTemplate.value) {
        config.template_id = selectedTemplate.value
      } else {
        if (filterRes.value) config.filter_res = filterRes.value
        if (filterTeam.value) config.filter_team = filterTeam.value
        if (filterSource.value) config.filter_source = filterSource.value
        if (filterCodec.value) config.filter_codec = filterCodec.value
        if (filterAudio.value) config.filter_audio = filterAudio.value
        if (filterSub.value) config.filter_sub = filterSub.value
        if (filterEffect.value) config.filter_effect = filterEffect.value
        if (filterPlatform.value) config.filter_platform = filterPlatform.value
      }

      const res = await fetch(`${API_BASE}/api/detect/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })

      const data = await res.json()
      
      if (!res.ok) {
        message.error(data.detail || '探测失败')
        return
      }

      previewResult.value = data
      
      if (data.detected_shows && data.detected_shows.length > 0) {
        message.success(`识别到 ${data.detected_shows.length} 个番剧`)
      } else {
        message.info('未识别到任何番剧')
      }
    } catch (e: any) {
      message.error('探测失败: ' + (e.message || '未知错误'))
    } finally {
      detecting.value = false
    }
  }

  const handleSubscribe = async () => {
    if (!rssUrl.value.trim()) {
      message.warning('请输入 RSS 链接')
      return
    }

    subscribing.value = true

    try {
      const config: any = {
        rss_url: rssUrl.value.trim(),
        save_task: saveAsTask.value,
        task_name: taskName.value,
        interval_minutes: intervalMinutes.value,
        target_client_id: targetClientId.value,
        save_path: savePath.value,
        category: category.value,
        auto_fill: autoFill.value
      }

      if (mode.value === 'template' && selectedTemplate.value) {
        config.template_id = selectedTemplate.value
      } else {
        if (filterRes.value) config.filter_res = filterRes.value
        if (filterTeam.value) config.filter_team = filterTeam.value
        if (filterSource.value) config.filter_source = filterSource.value
        if (filterCodec.value) config.filter_codec = filterCodec.value
        if (filterAudio.value) config.filter_audio = filterAudio.value
        if (filterSub.value) config.filter_sub = filterSub.value
        if (filterEffect.value) config.filter_effect = filterEffect.value
        if (filterPlatform.value) config.filter_platform = filterPlatform.value
        if (includeKeywords.value) config.include_keywords = includeKeywords.value
        if (excludeKeywords.value) config.exclude_keywords = excludeKeywords.value
      }

      const res = await fetch(`${API_BASE}/api/detect/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })

      const data = await res.json()
      
      if (!res.ok) {
        message.error(data.detail || '订阅失败')
        return
      }

      subscribeResult.value = data
      emit('finish')
      
      if (data.created > 0) {
        message.success(`成功创建 ${data.created} 个订阅，跳过 ${data.skipped} 个已存在的`)
      } else {
        message.info(`未创建新订阅，跳过 ${data.skipped} 个已存在的`)
      }

      if (saveAsTask.value && data.task_saved) {
        message.info('已保存为定时任务')
      }
    } catch (e: any) {
      message.error('订阅失败: ' + (e.message || '未知错误'))
    } finally {
      subscribing.value = false
    }
  }

  const handleRunTask = async (taskId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/detect/tasks/${taskId}/run`, {
        method: 'POST'
      })
      const data = await res.json()
      
      if (data.created > 0) {
        message.success(`成功创建 ${data.created} 个订阅`)
      } else {
        message.info('未发现新番剧需要订阅')
      }
      
      await fetchTasks()
    } catch (e) {
      message.error('执行失败')
    }
  }

  const handleDeleteTask = async (taskId: number) => {
    try {
      await fetch(`${API_BASE}/api/detect/tasks/${taskId}`, {
        method: 'DELETE'
      })
      message.success('已删除任务')
      await fetchTasks()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const resetForm = () => {
    rssUrl.value = ''
    previewResult.value = null
    subscribeResult.value = null
    saveAsTask.value = false
    taskName.value = ''
    intervalMinutes.value = 360
  }

  watch(() => props.show, (val) => {
    if (val) {
      resetForm()
      fetchTemplates()
      fetchClients()
      fetchTasks()
    }
  })

  return {
    loading, detecting, subscribing,
    rssUrl, previewResult, subscribeResult,
    mode, selectedTemplate, templates,
    filterRes, filterTeam, filterSource, filterCodec,
    filterAudio, filterSub, filterEffect, filterPlatform,
    includeKeywords, excludeKeywords,
    targetClientId, clients, savePath, category, autoFill,
    saveAsTask, taskName, intervalMinutes,
    tasks,
    fetchTemplates, fetchClients, fetchTasks,
    handlePreview, handleSubscribe,
    handleRunTask, handleDeleteTask,
    resetForm
  }
}
