import { ref, reactive } from 'vue'
import { tmdbDetailState } from '../../store/navigationStore'

export function useSearch() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const keyword = ref('')
  const loading = ref(false)
  const hasSearched = ref(false)

  const results = reactive({
      bangumi: [] as any[],
      tmdb_movie: [] as any[],
      tmdb_tv: [] as any[]
  })

  const tmdbDetail = tmdbDetailState

  const bgmDetail = reactive({
      show: false,
      id: '' as string | number,
      initial: null as any
  })

  const subscriptions = ref<any[]>([])

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) subscriptions.value = await res.json()
    } catch (e) { console.error(e) }
  }

  const isSubscribed = (item: any, source: 'tmdb' | 'bangumi' = 'tmdb') => {
      if (source === 'bangumi') {
           return subscriptions.value.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(item.id))
      }
      return subscriptions.value.some((sub: any) => String(sub.tmdb_id) === String(item.id))
  }

  const doSearch = async () => {
      loading.value = true
      hasSearched.value = true
      
      results.bangumi = []
      results.tmdb_movie = []
      results.tmdb_tv = []
      
      try {
          await fetchSubscriptions()
          const res = await fetch(`${API_BASE}/api/explore/search?keyword=${encodeURIComponent(keyword.value || '')}`)
          if (res.ok) {
              const data = await res.json()
              results.bangumi = data.bangumi || []
              results.tmdb_movie = data.tmdb_movie || []
              results.tmdb_tv = data.tmdb_tv || []
          }
      } catch (e) {
          console.error("Search failed", e)
      } finally {
          loading.value = false
      }
  }

  const openTmdb = (item: any, type: string) => {
      tmdbDetail.value.id = item.id
      tmdbDetail.value.type = type
      tmdbDetail.value.initial = item
      tmdbDetail.value.show = true
  }

  const openBangumi = (item: any) => {
      bgmDetail.id = item.id
      bgmDetail.initial = item
      bgmDetail.show = true
  }

  return {
    keyword,
    loading,
    hasSearched,
    results,
    tmdbDetail,
    bgmDetail,
    doSearch,
    openTmdb,
    openBangumi,
    isSubscribed
  }
}
