import { ref, watch, nextTick } from 'vue'
import { useMessage } from 'naive-ui'

export function useTmdbPersonDetail(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const detail = ref<any>(null)
  const credits = ref<{ cast: any[], crew: any[] }>({ cast: [], crew: [] })
  const renderReady = ref(false)

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

  const getProfile = (path: string) => getImg(path)
  const getPoster = (path: string) => getImg(path)

  const fetchDetail = async (personId?: string | number) => {
    const id = personId || props.personId
    if (!id) return
    
    loading.value = true
    try {
      const [detailRes, creditsRes] = await Promise.all([
        fetch(`${API_BASE}/api/tmdb/person/${id}`),
        fetch(`${API_BASE}/api/tmdb/person/${id}/credits`)
      ])
      
      if (detailRes.ok) {
        detail.value = await detailRes.json()
      } else {
        message.error('获取人物详情失败')
      }
      
      if (creditsRes.ok) {
        credits.value = await creditsRes.json()
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
      detail.value = props.initialData || null
      credits.value = { cast: [], crew: [] }
      nextTick(() => { renderReady.value = true })
      fetchDetail()
    }
  })

  const handleClose = () => {
    emit('update:show', false)
  }

  const openExternal = () => {
    window.open(`https://www.themoviedb.org/person/${props.personId}`, '_blank')
  }

  const openImdb = (imdbId: string) => {
    window.open(`https://www.imdb.com/name/${imdbId}`, '_blank')
  }

  const genderText = (gender: number) => {
    if (gender === 1) return '女'
    if (gender === 2) return '男'
    return '未知'
  }

  const calculateAge = (birthday: string, deathday?: string) => {
    if (!birthday) return null
    const birth = new Date(birthday)
    const end = deathday ? new Date(deathday) : new Date()
    let age = end.getFullYear() - birth.getFullYear()
    const monthDiff = end.getMonth() - birth.getMonth()
    if (monthDiff < 0 || (monthDiff === 0 && end.getDate() < birth.getDate())) {
      age--
    }
    return age
  }

  return {
    loading,
    detail,
    credits,
    getProfile,
    getPoster,
    handleClose,
    openExternal,
    openImdb,
    genderText,
    calculateAge,
    renderReady
  }
}
