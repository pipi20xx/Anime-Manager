import { reactive, ref, computed, onMounted } from 'vue'
import { openBangumiDetail } from '../../store/navigationStore'

export function useRecommend() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const exploreData = reactive({
    schedule: [] as any[],
    subscriptions: [] as any[],
    loading: false
  })

  const currentScheduleTab = ref("")

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) {
          exploreData.subscriptions = await res.json()
      }
    } catch (e) {
      console.error("Fetch subscriptions failed", e)
    }
  }

  // 用 computed 缓存 Set，避免每张卡片每次渲染都遍历订阅列表
  const subscribedBgmIds = computed(() => {
    const ids = new Set<string>()
    const titles = new Set<string>()
    for (const sub of exploreData.subscriptions) {
      if (sub.bangumi_id) ids.add(String(sub.bangumi_id))
      if (sub.title) titles.add(sub.title)
    }
    return { ids, titles }
  })

  const subscribedTmdbIds = computed(() => {
    const ids = new Set<string>()
    for (const sub of exploreData.subscriptions) {
      if (sub.tmdb_id) ids.add(String(sub.tmdb_id))
    }
    return ids
  })

  const isSubscribed = (item: any, source: 'tmdb' | 'bangumi' = 'tmdb') => {
      if (source === 'tmdb') {
          return subscribedTmdbIds.value.has(String(item.id))
      } else {
          if (subscribedBgmIds.value.ids.has(String(item.id))) return true
          const title = item.title || item.name
          const orig = item.original_title || item.name
          return subscribedBgmIds.value.titles.has(title) || subscribedBgmIds.value.titles.has(orig)
      }
  }

  const fetchSchedule = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bangumi/calendar_local`)
      if (res.ok) {
        const schedData = await res.json()
        exploreData.schedule = schedData.data || []
        const todayItem = exploreData.schedule.find((d: any) => d.is_today)
        currentScheduleTab.value = todayItem?.date || exploreData.schedule[0]?.date || ""
      }
    } catch (e) { console.error("Fetch schedule failed", e) }
  }

  const fetchExploreData = async () => {
    exploreData.loading = true
    // 订阅列表独立加载，到位后角标自动响应式更新
    fetchSubscriptions()
    // 各区块并行发起、独立填充，互不阻塞
    await Promise.allSettled([
      fetchSchedule(),
    ])
    exploreData.loading = false
  }

  const getImg = (path: string) => {
    if (!path) return ''
    if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
    if (path.includes('image.tmdb.org')) {
      const parts = path.split('/')
      return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
    }
    if (!path.startsWith('http')) {
      return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
    }
    return path
  }

  const getPoster = (path: string) => getImg(path)
  const getBackdrop = (path: string) => getImg(path)

  const openBangumi = (bgmItem: any) => {
      openBangumiDetail(bgmItem.id, bgmItem)
  }

  onMounted(() => {
    fetchExploreData()
  })

  return {
    exploreData,
    currentScheduleTab,
    fetchSubscriptions,
    isSubscribed,
    fetchExploreData,
    getImg,
    getPoster,
    getBackdrop,
    openBangumi
  }
}
