import { reactive, ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'

export function useRecommend() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const exploreData = reactive({
    trending: [] as any[],
    movies: [] as any[],
    tv: [] as any[],
    calendar: [] as any[],
    subscriptions: [] as any[],
    loading: false
  })

  const tmdbDetail = reactive({
      show: false,
      id: '' as string | number,
      type: 'tv',
      initial: null as any
  })

  const bgmDetail = reactive({
      show: false,
      id: '' as string | number,
      initial: null as any
  })

  const currentDayTab = ref("today")

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

  const isSubscribed = (item: any, source: 'tmdb' | 'bangumi' = 'tmdb') => {
      if (source === 'tmdb') {
          return exploreData.subscriptions.some((sub: any) => String(sub.tmdb_id) === String(item.id))
      } else {
          if (exploreData.subscriptions.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(item.id))) {
              return true
          }
          const title = item.title || item.name
          const orig = item.original_title || item.name
          return exploreData.subscriptions.some((sub: any) => 
              sub.title === title || sub.title === orig
          )
      }
  }

  const fetchExploreData = async () => {
    exploreData.loading = true
    try {
      const [trendRes, movieRes, tvRes, calRes] = await Promise.all([
        fetch(`${API_BASE}/api/tmdb/trending`), 
        fetch(`${API_BASE}/api/tmdb/popular/movie`),
        fetch(`${API_BASE}/api/tmdb/popular/tv`),
        fetch(`${API_BASE}/api/bangumi/calendar`)
      ])
      
      if (trendRes.ok) exploreData.trending = (await trendRes.json()).results || []
      if (movieRes.ok) exploreData.movies = (await movieRes.json()).results || []
      if (tvRes.ok) exploreData.tv = (await tvRes.json()).results || []
      
      if (calRes.ok) {
          const calData = await calRes.json()
          exploreData.calendar = calData.data || []
          const todayItem = exploreData.calendar.find((d: any) => d.is_today)
          if (todayItem) currentDayTab.value = todayItem.weekday.en
      }

      await fetchSubscriptions()
    } catch (e) {
      console.error("Explore fetch failed", e)
      message.error("获取数据部分失败")
    } finally {
      exploreData.loading = false
    }
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

  const openDetail = (item: any, type: string) => {
      tmdbDetail.id = item.id
      tmdbDetail.type = type === 'movie' ? 'movie' : 'tv'
      tmdbDetail.initial = item
      tmdbDetail.show = true
  }

  const openBangumi = (bgmItem: any) => {
      bgmDetail.id = bgmItem.id
      bgmDetail.initial = bgmItem
      bgmDetail.show = true
  }

  onMounted(() => {
    fetchExploreData()
  })

  return {
    exploreData,
    tmdbDetail,
    bgmDetail,
    currentDayTab,
    fetchSubscriptions,
    isSubscribed,
    fetchExploreData,
    getImg,
    getPoster,
    getBackdrop,
    openDetail,
    openBangumi
  }
}
