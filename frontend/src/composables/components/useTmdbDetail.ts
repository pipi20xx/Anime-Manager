import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch } from '../../store/navigationStore'

export function useTmdbDetail(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const detail = ref<any>(null)
  const subscriptions = ref<any[]>([])

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
      const res = await fetch(`${API_BASE}/api/tmdb/detail/${type}/${props.tmdbId}`)
      if (res.ok) {
          detail.value = await res.json()
      } else {
          message.error('获取 TMDB 详情失败')
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
    handleSearch
  }
}
