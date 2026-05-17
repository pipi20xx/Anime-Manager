import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch } from '../../store/navigationStore'

export function useTmdbDetail(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const detail = ref<any>(null)
  const subscriptions = ref<any[]>([])
  const expandedSeasons = ref<Set<number>>(new Set())
  const seasonEpisodes = ref<Map<string, any[]>>(new Map())
  const seasonEmbyInfo = ref<Map<string, any>>(new Map())
  const loadingSeasons = ref<Set<string>>(new Set())
  const embyStatus = ref<any>(null)

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) subscriptions.value = await res.json()
    } catch (e) {}
  }

  const isSubscribed = computed(() => {
      return subscriptions.value.some((sub: any) => String(sub.tmdb_id) === String(props.tmdbId))
  })

  const displayGenres = computed(() => {
      if (!detail.value || !detail.value.genres) return []
      return [...new Set(detail.value.genres.filter((g: any) => g))]
  })

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

  const fetchDetail = async () => {
    if (!props.tmdbId) return
    loading.value = true
    fetchSubscriptions()
    try {
      const type = props.mediaType === '电影' ? 'movie' : (props.mediaType === 'movie' ? 'movie' : 'tv')
      const [detailRes, embyRes] = await Promise.all([
        fetch(`${API_BASE}/api/tmdb/detail/${type}/${props.tmdbId}`),
        fetch(`${API_BASE}/api/tmdb/detail/${type}/${props.tmdbId}/emby`)
      ])
      
      if (detailRes.ok) {
          detail.value = await detailRes.json()
      } else {
          message.error('获取 TMDB 详情失败')
      }
      
      if (embyRes.ok) {
        embyStatus.value = await embyRes.json()
      }
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  watch(() => props.show, (val) => {
    if (val) {
        detail.value = props.initialData || null
        fetchDetail()
    }
  })

  const handleClose = () => {
    emit('update:show', false)
  }

  const openExternal = () => {
      const type = props.mediaType === 'movie' || props.mediaType === '电影' ? 'movie' : 'tv'
      window.open(`https://www.themoviedb.org/${type}/${props.tmdbId}`, '_blank')
  }

  const handleSubscribe = () => {
      if (!detail.value) return
      const type = props.mediaType === '电影' ? 'movie' : (props.mediaType === 'movie' ? 'movie' : 'tv')
      navigateToSubscription({
          type: 'tmdb',
          tmdbId: props.tmdbId,
          mediaType: type as 'movie' | 'tv',
          title: detail.value.title || detail.value.name
      })
      emit('update:show', false)
  }

  const handleSearch = () => {
      triggerGlobalSearch(detail.value.original_title || detail.value.original_name || detail.value.title || detail.value.name)
  }

  const toggleSeason = async (seasonNumber: number) => {
    const key = `${props.tmdbId}-${seasonNumber}`
    
    if (expandedSeasons.value.has(seasonNumber)) {
      expandedSeasons.value.delete(seasonNumber)
      expandedSeasons.value = new Set(expandedSeasons.value)
      return
    }
    
    expandedSeasons.value.add(seasonNumber)
    expandedSeasons.value = new Set(expandedSeasons.value)
    
    if (!seasonEpisodes.value.has(key)) {
      loadingSeasons.value.add(key)
      loadingSeasons.value = new Set(loadingSeasons.value)
      
      try {
        const [tmdbRes, embyRes] = await Promise.all([
          fetch(`${API_BASE}/api/tmdb/season/${props.tmdbId}/${seasonNumber}`),
          fetch(`${API_BASE}/api/tmdb/season/${props.tmdbId}/${seasonNumber}/emby`)
        ])
        
        if (tmdbRes.ok) {
          const data = await tmdbRes.json()
          seasonEpisodes.value.set(key, data)
          seasonEpisodes.value = new Map(seasonEpisodes.value)
        }
        
        if (embyRes.ok) {
          const embyData = await embyRes.json()
          seasonEmbyInfo.value.set(key, embyData.episodes || {})
          seasonEmbyInfo.value = new Map(seasonEmbyInfo.value)
        }
      } catch (e) {
        console.error('Failed to fetch season episodes', e)
      } finally {
        loadingSeasons.value.delete(key)
        loadingSeasons.value = new Set(loadingSeasons.value)
      }
    }
  }

  const getSeasonInfo = (seasonNumber: number) => {
    const key = `${props.tmdbId}-${seasonNumber}`
    const data = seasonEpisodes.value.get(key)
    return data?.season_info || null
  }

  const getSeasonEpisodes = (seasonNumber: number) => {
    const key = `${props.tmdbId}-${seasonNumber}`
    const data = seasonEpisodes.value.get(key)
    return data?.episodes || []
  }

  const isSeasonLoading = (seasonNumber: number) => {
    const key = `${props.tmdbId}-${seasonNumber}`
    return loadingSeasons.value.has(key)
  }

  const isSeasonExpanded = (seasonNumber: number) => {
    return expandedSeasons.value.has(seasonNumber)
  }

  const getEpisodeEmbyInfo = (seasonNumber: number, episodeNumber: number) => {
    const key = `${props.tmdbId}-${seasonNumber}`
    const embyData = seasonEmbyInfo.value.get(key)
    return embyData?.[episodeNumber] || null
  }

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return ''
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let i = 0
    let size = bytes
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024
      i++
    }
    return `${size.toFixed(2)} ${units[i]}`
  }

  const isInLibrary = computed(() => {
    return embyStatus.value?.exists || false
  })

  const getSeasonLibraryStatus = (seasonNumber: number) => {
    return embyStatus.value?.seasons?.[seasonNumber] || null
  }

  return {
    loading,
    detail,
    isSubscribed,
    displayGenres,
    getPoster,
    getBackdrop,
    handleClose,
    openExternal,
    handleSubscribe,
    handleSearch,
    toggleSeason,
    getSeasonInfo,
    getSeasonEpisodes,
    isSeasonLoading,
    isSeasonExpanded,
    getEpisodeEmbyInfo,
    formatFileSize,
    embyStatus,
    isInLibrary,
    getSeasonLibraryStatus
  }
}
