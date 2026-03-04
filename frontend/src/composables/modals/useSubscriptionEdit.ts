import { ref, watch, toRef } from 'vue'
import { useMessage } from 'naive-ui'

export function useSubscriptionEdit(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const searchResults = ref<any[]>([])
  const searchQuery = ref('')
  
  const formModel = ref({
    id: null,
    tmdb_id: '',
    media_type: 'tv',
    title: '',
    year: '',
    poster_path: '',
    quality_profile_id: null,
    filter_res: '',
    filter_team: '',
    filter_source: '',
    filter_codec: '',
    filter_audio: '',
    filter_sub: '',
    filter_effect: '',
    filter_platform: '',
    include_keywords: '',
    exclude_keywords: '',
    target_feeds: [],
    target_client_id: null,
    save_path: '',
    category: 'Anime',
    enabled: true,
    auto_fill: true,
    bangumi_id: '',
    season: 1,
    start_episode: 1,
    end_episode: 0
  })

  const tmdbSeasons = ref<any[]>([])
  const bangumiName = ref('')
  const templates = ref<any[]>([])
  const profiles = ref<any[]>([])
  const feeds = ref<any[]>([])

  const getImg = (path: string) => {
    if (!path) return ''
    if (path.includes('/api/system/img')) return path
    if (path.includes('image.tmdb.org')) {
      const parts = path.split('/')
      return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
    }
    if (!path.startsWith('http')) return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
    return path
  }

  const fetchFeeds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds`)
      feeds.value = await res.json()
    } catch (e) {}
  }

  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions/templates`)
      templates.value = await res.json()
    } catch (e) {}
  }

  const fetchProfiles = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/priority/profiles`)
      profiles.value = await res.json()
    } catch (e) {}
  }

  const applyTemplate = (tmplId: number) => {
    const tmpl = templates.value.find(t => t.id === tmplId)
    if (!tmpl) return
    
    // 仅覆盖配置类参数，保留标题、ID、海报等核心元数据
    formModel.value.filter_res = tmpl.filter_res || ''
    formModel.value.filter_team = tmpl.filter_team || ''
    formModel.value.filter_source = tmpl.filter_source || ''
    formModel.value.filter_codec = tmpl.filter_codec || ''
    formModel.value.filter_audio = tmpl.filter_audio || ''
    formModel.value.filter_sub = tmpl.filter_sub || ''
    formModel.value.filter_effect = tmpl.filter_effect || ''
    formModel.value.filter_platform = tmpl.filter_platform || ''
    formModel.value.include_keywords = tmpl.include_keywords || ''
    formModel.value.exclude_keywords = tmpl.exclude_keywords || ''
    formModel.value.target_client_id = tmpl.target_client_id
    formModel.value.save_path = tmpl.save_path || ''
    formModel.value.category = tmpl.category || 'Anime'
    formModel.value.auto_fill = tmpl.auto_fill
    
    if (tmpl.target_feeds) {
      // @ts-ignore
      formModel.value.target_feeds = tmpl.target_feeds.split(',').filter(x => x)
    } else {
      // @ts-ignore
      formModel.value.target_feeds = []
    }
    
    message.success(`已套用预设: ${tmpl.name}`)
  }

  const fetchBangumiDetails = async (id: string | number) => {
    if (!id) {
      bangumiName.value = ''
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/bangumi/subject/${id}`)
      if (res.ok) {
        const data = await res.json()
        bangumiName.value = data.title || ''
        if (data.total_episodes > 0 && (formModel.value.end_episode === 0 || props.isNew)) {
          formModel.value.end_episode = data.total_episodes
        }
      } else {
        bangumiName.value = '条目未找到'
      }
    } catch (e) {
      bangumiName.value = '获取失败'
    }
  }

  const fetchTvDetails = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/tmdb/tv/${id}`)
      const data = await res.json()
      tmdbSeasons.value = data.seasons || []
      
      if (!formModel.value.bangumi_id && tmdbSeasons.value.length > 0) {
        const matched = tmdbSeasons.value.find(s => s.season_number === formModel.value.season)
        if (matched) {
          formModel.value.end_episode = matched.episode_count || 0
        }
      }
    } catch (e) {
      console.error('Fetch seasons failed', e)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.value) return
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/tmdb/search?query=${encodeURIComponent(searchQuery.value)}&type=${formModel.value.media_type}`)
      const data = await res.json()
      searchResults.value = data.results || []
    } catch (e) {
      message.error('搜索失败')
    } finally {
      loading.value = false
    }
  }

  const selectResult = (item: any) => {
    formModel.value.tmdb_id = String(item.id)
    formModel.value.title = item.title
    formModel.value.year = item.year
    formModel.value.poster_path = item.poster_path
    searchResults.value = []
    
    if (formModel.value.media_type === 'tv') {
      fetchTvDetails(formModel.value.tmdb_id)
    }
  }

  const onSeasonChange = (val: any) => {
    const sNum = parseInt(val) || 0
    formModel.value.season = sNum
    
    if (!formModel.value.bangumi_id && tmdbSeasons.value.length > 0) {
      const matched = tmdbSeasons.value.find(s => s.season_number === sNum)
      if (matched) {
        formModel.value.end_episode = matched.episode_count || 0
      }
    }
  }

  const handleSave = () => {
    if (!formModel.value.tmdb_id || !formModel.value.title) {
      message.warning('请先选择或输入 TMDB ID 和标题')
      return
    }
    const payload = { ...formModel.value }
    payload.season = parseInt(String(payload.season)) || 0
    payload.start_episode = parseInt(String(payload.start_episode)) || 0
    payload.end_episode = parseInt(String(payload.end_episode)) || 0
    
    if (Array.isArray(payload.target_feeds)) {
      // @ts-ignore
      payload.target_feeds = payload.target_feeds.join(',')
    }
    
    emit('save', payload)
    emit('update:show', false)
  }

  // Watchers
  let bangumiTimer: any = null
  watch(() => formModel.value.bangumi_id, (newId) => {
    if (bangumiTimer) clearTimeout(bangumiTimer)
    bangumiTimer = setTimeout(() => {
      fetchBangumiDetails(newId)
    }, 500)
  })

  // Init logic
  const init = () => {
    fetchTemplates()
    fetchFeeds()
    fetchProfiles()
    bangumiName.value = ''
    if (props.isNew) {
      formModel.value = {
        id: null,
        tmdb_id: props.subData?.tmdb_id || '',
        media_type: props.subData?.media_type || 'tv',
        title: props.subData?.title || '',
        year: props.subData?.year || '',
        poster_path: props.subData?.poster_path || '',
        quality_profile_id: null, 
        filter_res: '',
        filter_team: '',
        filter_source: '',
        filter_codec: '',
        filter_audio: '',
        filter_sub: '',
        filter_effect: '',
        filter_platform: '',
        include_keywords: '',
        exclude_keywords: '',
        target_feeds: [],
        target_client_id: props.clients.length > 0 ? props.clients[0].id : null,
        save_path: '',
        category: 'Anime',
        enabled: true,
        auto_fill: true,
        bangumi_id: props.subData?.bangumi_id ? String(props.subData.bangumi_id) : '',
        season: props.subData?.season ?? 1,
        start_episode: props.subData?.start_episode ?? 1,
        end_episode: props.subData?.end_episode ?? 0
      }
      searchResults.value = []
      searchQuery.value = props.subData?._search_query || props.subData?.title || ''
      tmdbSeasons.value = []

      if (props.subData?._auto_search || props.subData?._search_query) {
        setTimeout(() => {
          handleSearch()
        }, 300)
      }
    } else if (props.subData) {
      formModel.value = { ...props.subData }
      if (typeof formModel.value.target_feeds === 'string' && formModel.value.target_feeds) {
        // @ts-ignore
        formModel.value.target_feeds = formModel.value.target_feeds.split(',').filter(x => x)
      } else {
        // @ts-ignore
        formModel.value.target_feeds = []
      }

      if (formModel.value.media_type === 'tv' && formModel.value.tmdb_id) {
        fetchTvDetails(formModel.value.tmdb_id)
      }
      if (formModel.value.bangumi_id) {
        fetchBangumiDetails(formModel.value.bangumi_id)
      }
    }
  }

  return {
    loading,
    searchResults,
    searchQuery,
    formModel,
    tmdbSeasons,
    bangumiName,
    templates,
    profiles,
    feeds,
    getImg,
    fetchFeeds,
    fetchTemplates,
    fetchProfiles,
    applyTemplate,
    fetchBangumiDetails,
    fetchTvDetails,
    handleSearch,
    selectResult,
    onSeasonChange,
    handleSave,
    init
  }
}
