import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function useBangumiQuickSub(props: { show: boolean }, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const submitting = ref(false)
  const weeklyData = ref<any[]>([])
  const subscriptions = ref<any[]>([])
  const templates = ref<any[]>([])
  const selectedTemplate = ref<number | null>(null)
  const selectedIds = ref<number[]>([])

  const manualId = ref('')
  const manualItems = ref<any[]>([])

  const fetchData = async () => {
    loading.value = true
    try {
      const [calRes, subRes, tmplRes] = await Promise.all([
        fetch(`${API_BASE}/api/bangumi/calendar`),
        fetch(`${API_BASE}/api/subscriptions`),
        fetch(`${API_BASE}/api/subscriptions/templates`)
      ])
      const calData = await calRes.json()
      const subData = await subRes.json()
      const tmplData = await tmplRes.json()
      subscriptions.value = subData
      templates.value = tmplData
      
      const defaultTmpl = tmplData.find((t: any) => t.is_default)
      if (defaultTmpl) selectedTemplate.value = defaultTmpl.id
      else if (tmplData.length > 0) selectedTemplate.value = tmplData[0].id

      weeklyData.value = calData.data.map((day: any) => ({
        ...day,
        items: day.items.map((item: any) => ({
          ...item,
          isSubscribed: subData.some((s: any) => String(s.bangumi_id) === String(item.id))
        }))
      }))

      const allUnsubbed = []
      for (const day of weeklyData.value) {
        for (const item of day.items) {
          if (!item.isSubscribed) allUnsubbed.push(item.id)
        }
      }
      selectedIds.value = allUnsubbed
    } catch (e) { message.error('加载放送数据失败') }
    finally { loading.value = false }
  }

  const addManualItem = async () => {
    if (!manualId.value) return
    try {
      const res = await fetch(`${API_BASE}/api/bangumi/subject/${manualId.value}`)
      if (res.ok) {
        const data = await res.json()
        const isSubbed = subscriptions.value.some((s: any) => String(s.bangumi_id) === String(data.id))
        manualItems.value.push({ id: data.id, title: data.title, image: data.poster_path, isSubscribed: isSubbed })
        if (!isSubbed) selectedIds.value.push(data.id)
        manualId.value = ''
      }
    } catch (e) {}
  }

  const handleBatchSubscribe = async () => {
    if (selectedIds.value.length === 0) return
    const ids = [...selectedIds.value]
    const tid = selectedTemplate.value
    emit('update:show', false)
    message.info(`已启动 ${ids.length} 个番剧的后台订阅任务`)
    try {
      fetch(`${API_BASE}/api/bangumi/batch_subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject_ids: ids, template_id: tid })
      }).then(() => emit('finish'))
    } catch (e) {}
  }

  watch(() => props.show, (val) => {
    if (val) { manualItems.value = []; fetchData() }
  })

  return {
    loading, submitting, weeklyData, templates, selectedTemplate, selectedIds,
    manualId, manualItems,
    fetchData, addManualItem, handleBatchSubscribe
  }
}
