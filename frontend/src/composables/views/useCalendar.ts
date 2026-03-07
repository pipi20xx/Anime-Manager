import { ref, onMounted, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useCalendar() {
  const loading = ref(true)
  const trackingList = ref<any[]>([])
  const bangumiRaw = ref<any[]>([])
  const message = useMessage()

  // 状态
  const viewDate = ref(new Date())
  const showManageModal = ref(false)
  const editingId = ref<number | null>(null)
  const editBuffer = ref({ title: '', season: 1 })
  const importingBatch = ref(false)
  const isTestingPush = ref(false)

  // 配置项 (每日推送)
  const calendarConfig = ref({
    daily_push_enabled: false,
    push_time: '09:00'
  })

  // 手动添加
  const newSubject = ref({ tmdb_id: '', media_type: 'tv', title: '', season: 1 })

  // Desktop Calendar Grid
  const calendarGrid = computed(() => {
    const year = viewDate.value.getFullYear()
    const month = viewDate.value.getMonth()
    const firstDay = new Date(year, month, 1).getDay()
    const startOffset = firstDay === 0 ? 6 : firstDay - 1
    const startDate = new Date(year, month, 1)
    startDate.setDate(startDate.getDate() - startOffset)
    
    const grid = []
    const todayStr = new Date().toLocaleDateString()
    
    for (let i = 0; i < 42; i++) {
      const d = new Date(startDate)
      d.setDate(startDate.getDate() + i)
      const matchDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      
      const cell: any = {
        dateStr: matchDate,
        day: d.getDate(),
        isToday: d.toLocaleDateString() === todayStr,
        isCurrentMonth: d.getMonth() === month,
        items: []
      }

      trackingList.value.forEach(sub => {
        if (sub.episodes_cache && Array.isArray(sub.episodes_cache)) {
          const matches = sub.episodes_cache.filter((ep: any) => ep.air_date === matchDate)
          if (matches.length > 0) {
            const epNums = matches.map((m: any) => m.episode).sort((a: number, b: number) => a - b)
            let epDisplay = ''
            if (epNums.length === 1) epDisplay = `E${epNums[0]}`
            else {
              const isContinuous = epNums.every((num: number, idx: number) => idx === 0 || num === epNums[idx - 1] + 1)
              epDisplay = isContinuous ? `E${epNums[0]}-${epNums[epNums.length - 1]}` : `E${epNums.join(',')}`
            }

            cell.items.push({
              id: sub.id,
              title: sub.title,
              season: sub.season,
              episodeDisplay: `S${sub.season}${epDisplay}`,
              epDetails: matches.map((m: any) => `第 ${m.episode} 集: ${m.name || '未命名'}`).join('<br/>')
            })
          }
        }
      })
      grid.push(cell)
    }
    return grid
  })

  // Mobile Agenda View (Next 7 days + Today)
  const mobileAgenda = computed(() => {
    const list = []
    const today = new Date()
    today.setHours(0,0,0,0) // Normalize

    for(let i = 0; i < 14; i++) { // Show 2 weeks
      const d = new Date(today)
      d.setDate(today.getDate() + i)
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      const dayLabel = i === 0 ? '今天' : i === 1 ? '明天' : i === 2 ? '后天' : `周${['日','一','二','三','四','五','六'][d.getDay()]}`
      
      const items: any[] = []
      
      trackingList.value.forEach(sub => {
        if (sub.episodes_cache && Array.isArray(sub.episodes_cache)) {
          const matches = sub.episodes_cache.filter((ep: any) => ep.air_date === dateStr)
          if (matches.length > 0) {
             items.push({
               id: sub.id,
               title: sub.title,
               season: sub.season,
               episodes: matches.map((m: any) => ({ ep: m.episode, title: m.name }))
             })
          }
        }
      })

      if (items.length > 0) {
        list.push({
          dateStr,
          dayLabel,
          fullDate: `${d.getMonth() + 1}月${d.getDate()}日`,
          items
        })
      }
    }
    return list
  })

  const fetchData = async () => {
    loading.value = true
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const [trackRes, bgmRes, configRes] = await Promise.all([
        fetch(`${API_BASE}/api/calendar/subjects`),
        fetch(`${API_BASE}/api/bangumi/calendar`),
        fetch(`${API_BASE}/api/config`)
      ])
      trackingList.value = await trackRes.json()
      const bgmData = await bgmRes.json()
      if (bgmData.status === 'success') bangumiRaw.value = bgmData.data
      
      const configData = await configRes.json()
      calendarConfig.value = {
        daily_push_enabled: configData.calendar_daily_push || false,
        push_time: configData.calendar_push_time || '09:00'
      }
    } finally {
      loading.value = false
    }
  }

  const saveCalendarConfig = async () => {
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calendar_daily_push: calendarConfig.value.daily_push_enabled,
          calendar_push_time: calendarConfig.value.push_time
        })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('推送设置已更新')
      }
    } catch (e) {
      message.error('保存设置失败')
    }
  }

  const testCalendarPush = async () => {
    isTestingPush.value = true
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/test_push`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('推送请求失败')
    } finally {
      isTestingPush.value = false
    }
  }

  const handleAutoImport = async (bgmItem: any) => {
    message.info(`正在为《${bgmItem.title}》同步数据...`)
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/import_bangumi/${bgmItem.id}`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
        fetchData()
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('导入失败')
    }
  }

  const handleBatchImport = async () => {
    const allIds = bangumiRaw.value.flatMap(day => day.items.map((item: any) => item.id))
    if (allIds.length === 0) return
    
    importingBatch.value = true
    message.info(`正在批量导入 ${allIds.length} 个项目，请稍候...`)
    
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/batch_import_bangumi`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(allIds)
      })
      const data = await res.json()
      message.success(`批量操作完成：成功 ${data.success} 个，失败 ${data.failed} 个`)
      fetchData()
    } catch (e) {
      message.error('批量导入请求失败')
    } finally {
      importingBatch.value = false
    }
  }

  const startEdit = (sub: any) => {
    editingId.value = sub.id
    editBuffer.value = { title: sub.title, season: sub.season }
  }

  const saveEdit = async (id: number) => {
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/subjects/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editBuffer.value)
      })
      const data = await res.json()
      if (data.success) {
        message.success('更新成功')
        editingId.value = null
        fetchData()
      }
    } catch (e) {
      message.error('更新失败')
    }
  }

  const handleAddSubject = async () => {
    if (!newSubject.value.tmdb_id) return
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/subjects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSubject.value)
      })
      const data = await res.json()
      if (data.success) {
        message.success('添加成功')
        fetchData()
        newSubject.value = { tmdb_id: '', media_type: 'tv', title: '', season: 1 }
      }
    } catch (e) {
      message.error('添加失败')
    }
  }

  const refreshSubject = async (id: number) => {
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/subjects/${id}/refresh`, { method: 'POST' })
      const data = await res.json()
      if (data.success) { message.success('已同步最新放送日期'); fetchData(); }
    } catch (e) { message.error('同步失败') }
  }

  const refreshAllSubjects = async () => {
    if (trackingList.value.length === 0) {
      message.info('没有需要刷新的追踪项')
      return
    }
    loading.value = true
    message.info(`正在刷新 ${trackingList.value.length} 个追踪项...`)
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      const res = await fetch(`${API_BASE}/api/calendar/subjects/refresh_all`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        message.success(data.message)
        fetchData()
      }
    } catch (e) {
      message.error('批量刷新失败')
    } finally {
      loading.value = false
    }
  }

  const deleteSubject = async (id: number) => {
    try {
      const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
      await fetch(`${API_BASE}/api/calendar/subjects/${id}`, { method: 'DELETE' })
      fetchData()
    } catch (e) { message.error('删除失败') }
  }

  onMounted(fetchData)

  return {
    loading,
    trackingList,
    bangumiRaw,
    viewDate,
    showManageModal,
    editingId,
    editBuffer,
    newSubject,
    importingBatch,
    calendarGrid,
    mobileAgenda,
    calendarConfig,
    isTestingPush,
    fetchData,
    saveCalendarConfig,
    testCalendarPush,
    handleAutoImport,
    handleBatchImport,
    startEdit,
    saveEdit,
    handleAddSubject,
    refreshSubject,
    refreshAllSubjects,
    deleteSubject
  }
}
