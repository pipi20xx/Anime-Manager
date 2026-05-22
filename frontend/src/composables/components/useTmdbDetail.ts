import { ref, computed, watch, nextTick } from 'vue'
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
  const recommendations = ref<any[]>([])
  const currentTmdbId = ref<string | number>('')
  const currentMediaType = ref<string>('')
  const renderReady = ref(false)
  const episodeGroup = ref<any>(null)

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

  const fetchDetail = async (tmdbId?: string | number, mediaType?: string) => {
    const id = tmdbId || currentTmdbId.value || props.tmdbId
    const type = mediaType || currentMediaType.value || props.mediaType
    
    if (!id) return
    
    currentTmdbId.value = id
    currentMediaType.value = type
    
    loading.value = true
    fetchSubscriptions()
    try {
      const apiType = type === '电影' || type === 'movie' ? 'movie' : 'tv'
      const [detailRes, embyRes, recRes, episodeGroupRes] = await Promise.all([
        fetch(`${API_BASE}/api/tmdb/detail/${apiType}/${id}`),
        fetch(`${API_BASE}/api/tmdb/detail/${apiType}/${id}/emby`),
        fetch(`${API_BASE}/api/tmdb/recommendations/${apiType}/${id}`),
        apiType === 'tv' ? fetch(`${API_BASE}/api/sytmdb/episodegroup/${id}`) : Promise.resolve(null)
      ])
      
      if (detailRes.ok) {
          detail.value = await detailRes.json()
      } else {
          message.error('获取 TMDB 详情失败')
      }
      
      if (embyRes.ok) {
        embyStatus.value = await embyRes.json()
      }
      
      if (recRes.ok) {
        recommendations.value = await recRes.json()
      }
      
      if (episodeGroupRes && episodeGroupRes.ok) {
        episodeGroup.value = await episodeGroupRes.json()
        const groupsCount = episodeGroup.value?.groups?.length || 0
        if (groupsCount > 0) {
          console.log(`[剧集组] TMDB ID ${id}: 使用剧集组，共 ${groupsCount} 个组`)
        } else {
          console.log(`[剧集组] TMDB ID ${id}: 无剧集组定义，使用TMDB原始季集`)
        }
      } else {
        episodeGroup.value = null
        console.log(`[剧集组] TMDB ID ${id}: 查询失败，使用TMDB原始季集`)
      }
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  watch(() => props.show, (val) => {
    if (val) {
        renderReady.value = false
        currentTmdbId.value = props.tmdbId
        currentMediaType.value = props.mediaType
        detail.value = props.initialData || null
        expandedSeasons.value = new Set()
        seasonEpisodes.value = new Map()
        seasonEmbyInfo.value = new Map()
        recommendations.value = []
        embyStatus.value = null
        nextTick(() => { renderReady.value = true })
        fetchDetail()
    }
  })

  const handleClose = () => {
    emit('update:show', false)
  }

  const openExternal = () => {
      const type = currentMediaType.value === 'movie' || currentMediaType.value === '电影' ? 'movie' : 'tv'
      window.open(`https://www.themoviedb.org/${type}/${currentTmdbId.value}`, '_blank')
  }

  const openImdb = (imdbId: string) => {
      window.open(`https://www.imdb.com/title/${imdbId}`, '_blank')
  }

  const handleSubscribe = () => {
      if (!detail.value) return
      const type = currentMediaType.value === '电影' || currentMediaType.value === 'movie' ? 'movie' : 'tv'
      navigateToSubscription({
          type: 'tmdb',
          tmdbId: currentTmdbId.value,
          mediaType: type as 'movie' | 'tv',
          title: detail.value.title || detail.value.name
      })
      emit('update:show', false)
  }

  const handleSearch = () => {
      triggerGlobalSearch(detail.value.original_title || detail.value.original_name || detail.value.title || detail.value.name)
  }

  const toggleSeason = async (seasonNumber: number) => {
    const tmdbId = currentTmdbId.value || props.tmdbId
    const key = `${tmdbId}-${seasonNumber}`
    
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
          fetch(`${API_BASE}/api/tmdb/season/${tmdbId}/${seasonNumber}`),
          fetch(`${API_BASE}/api/tmdb/season/${tmdbId}/${seasonNumber}/emby`)
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
        
        if (hasEpisodeGroup.value) {
          const localSeasonsToFetch = new Set<number>()
          
          for (let groupIdx = 0; groupIdx < episodeGroup.value.groups.length; groupIdx++) {
            const group = episodeGroup.value.groups[groupIdx]
            const hasCurrentSeason = group.episodes.some((ep: any) => ep.season_number === seasonNumber)
            if (hasCurrentSeason) {
              localSeasonsToFetch.add(groupIdx + 1)
            }
          }
          
          for (const localSeason of localSeasonsToFetch) {
            const localKey = `local-${tmdbId}-${localSeason}`
            if (!seasonEmbyInfo.value.has(localKey)) {
              try {
                const localEmbyRes = await fetch(`${API_BASE}/api/tmdb/season/${tmdbId}/${localSeason}/emby`)
                if (localEmbyRes.ok) {
                  const localEmbyData = await localEmbyRes.json()
                  seasonEmbyInfo.value.set(localKey, localEmbyData.episodes || {})
                  seasonEmbyInfo.value = new Map(seasonEmbyInfo.value)
                }
              } catch (e) {
                console.error('Failed to fetch local season emby info', e)
              }
            }
          }
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
    const tmdbId = currentTmdbId.value || props.tmdbId
    const key = `${tmdbId}-${seasonNumber}`
    const data = seasonEpisodes.value.get(key)
    return data?.season_info || null
  }

  const getSeasonEpisodes = (seasonNumber: number) => {
    const tmdbId = currentTmdbId.value || props.tmdbId
    const key = `${tmdbId}-${seasonNumber}`
    const data = seasonEpisodes.value.get(key)
    return data?.episodes || []
  }

  const isSeasonLoading = (seasonNumber: number) => {
    const tmdbId = currentTmdbId.value || props.tmdbId
    const key = `${tmdbId}-${seasonNumber}`
    return loadingSeasons.value.has(key)
  }

  const isSeasonExpanded = (seasonNumber: number) => {
    return expandedSeasons.value.has(seasonNumber)
  }

  const getEpisodeEmbyInfo = (seasonNumber: number, episodeNumber: number) => {
    const tmdbId = currentTmdbId.value || props.tmdbId
    
    if (hasEpisodeGroup.value) {
      const { localSeason, localEpisode } = getMappedEpisodeInfo(seasonNumber, episodeNumber)
      const localKey = `local-${tmdbId}-${localSeason}`
      const embyData = seasonEmbyInfo.value.get(localKey)
      return embyData?.[localEpisode] || null
    }
    
    const key = `${tmdbId}-${seasonNumber}`
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

  const handleRecClick = (rec: any) => {
    const type = rec.media_type || rec.type || 'tv'
    
    detail.value = rec
    expandedSeasons.value = new Set()
    seasonEpisodes.value = new Map()
    seasonEmbyInfo.value = new Map()
    recommendations.value = []
    embyStatus.value = null
    
    fetchDetail(rec.id, type)
  }

  const hasEpisodeGroup = computed(() => {
    return episodeGroup.value && episodeGroup.value.groups && episodeGroup.value.groups.length > 0
  })

  const getMappedEpisodeInfo = (tmdbSeason: number, tmdbEpisode: number) => {
    if (!hasEpisodeGroup.value) {
      return { localSeason: tmdbSeason, localEpisode: tmdbEpisode }
    }
    
    for (let groupIdx = 0; groupIdx < episodeGroup.value.groups.length; groupIdx++) {
      const group = episodeGroup.value.groups[groupIdx]
      for (let epIdx = 0; epIdx < group.episodes.length; epIdx++) {
        const ep = group.episodes[epIdx]
        if (ep.season_number === tmdbSeason && ep.episode_number === tmdbEpisode) {
          return {
            localSeason: groupIdx + 1,
            localEpisode: epIdx + 1
          }
        }
      }
    }
    
    return { localSeason: tmdbSeason, localEpisode: tmdbEpisode }
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
    openImdb,
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
    getSeasonLibraryStatus,
    recommendations,
    handleRecClick,
    renderReady,
    episodeGroup,
    hasEpisodeGroup,
    getMappedEpisodeInfo
  }
}
