import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch } from '../../store/navigationStore'

export function useBangumiDetail(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const detail = ref<any>(null)
  const subscriptions = ref<any[]>([])

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

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) subscriptions.value = await res.json()
    } catch (e) {}
  }

  const isSubscribed = computed(() => {
      if (!detail.value) return false
      if (subscriptions.value.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(props.subjectId))) {
          return true
      }
      const title = detail.value.title || detail.value.name
      const orig = detail.value.original_title || detail.value.name
      return subscriptions.value.some((sub: any) => sub.title === title || sub.title === orig)
  })

  const fetchDetail = async () => {
    if (!props.subjectId) return
    loading.value = true
    fetchSubscriptions() 
    try {
      const res = await fetch(`${API_BASE}/api/bangumi/subject/${props.subjectId}`)
      if (res.ok) {
          detail.value = await res.json()
      } else {
          message.error('获取 Bangumi 详情失败')
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
      window.open(`https://bgm.tv/subject/${props.subjectId}`, '_blank')
  }

  const handleSubscribe = async () => {
      if (!detail.value) return
      loading.value = true
      
      message.loading('正在尝试自动匹配并订阅...', { duration: 2000 })
      
      try {
          const res = await fetch(`${API_BASE}/api/bangumi/one_click_subscribe/${props.subjectId}`, {
              method: 'POST'
          })
          const data = await res.json()
          
          if (res.ok && data.success) {
              message.success(data.message || '订阅成功')
              fetchSubscriptions()
              emit('update:show', false)
          } else {
              message.info('匹配置信度不足，正在跳转至手动配置...')
              
              const mRes = await fetch(`${API_BASE}/api/bangumi/match_tmdb/${props.subjectId}`)
              const mData = await mRes.json()
              
              emit('update:show', false)
              
              setTimeout(() => {
                  navigateToSubscription({
                      type: mData.success ? 'tmdb' : 'bangumi',
                      tmdbId: mData.tmdb_id,
                      mediaType: mData.media_type,
                      title: mData.title || detail.value.title || detail.value.name,
                      year: mData.year,
                      bangumiId: props.subjectId,
                      season: mData.season,
                      totalEpisodes: mData.total_episodes || (mData.bgm_info?.total_episodes),
                      poster_path: mData.poster_path || (mData.bgm_info?.poster_path)
                  })
              }, 300)
          }
      } catch (e) {
          console.error(e)
          message.error('订阅过程中发生错误')
      } finally {
          loading.value = false
      }
  }

  return {
    loading,
    detail,
    isSubscribed,
    getImg,
    fetchDetail,
    handleClose,
    openExternal,
    handleSubscribe,
    triggerGlobalSearch
  }
}
