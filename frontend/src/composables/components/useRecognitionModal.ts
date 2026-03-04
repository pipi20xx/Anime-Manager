import { reactive, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function useRecognitionModal(props: any, emit: any) {
  const message = useMessage()

  const getImg = (path: string) => {
    if (!path) return ''
    if (path.includes('/api/system/img')) return path
    if (path.includes('image.tmdb.org')) {
      const parts = path.split('/')
      return `${props.apiBase}/api/system/img?path=/${parts[parts.length - 1]}`
    }
    if (!path.startsWith('http')) return `${props.apiBase}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
    return path
  }

  const getLogClass = (log: string) => {
    if (log.includes("深度审计启动") || log.includes("🚀")) return "p"
    if (log.includes("[DEBUG]")) return "d"
    if (log.includes("🎯") || log.includes("成功")) return "s"
    if (log.includes("✂️") || log.includes("拦截")) return "w"
    if (log.includes("📢") || log.includes("结论")) return "i"
    return ""
  }

  // --- Forced Params ---
  const forcedParams = reactive({ 
    tmdb_id: '', type: null as string | null, season: '', episode: '',
    anime_priority: true
  })
  
  const testSearch = reactive({ keyword: '', loading: false, results: [] as any[] })

  watch(() => props.show, (newVal) => {
    if (newVal && !props.loading) {
      Object.assign(forcedParams, { 
        tmdb_id: '', type: null, season: '', episode: '', 
        anime_priority: true
      })
      testSearch.keyword = ''; testSearch.results = []
    }
  })

  const searchTmdbForTest = async () => {
    if (!testSearch.keyword) return
    testSearch.loading = true
    try {
      const res = await fetch(`${props.apiBase}/api/tmdb/search?query=${encodeURIComponent(testSearch.keyword)}&type=${forcedParams.type || 'tv'}`)
      const data = await res.json()
      testSearch.results = data.results || []
    } finally { testSearch.loading = false }
  }

  const handleRecognize = () => {
    emit('recognize', { 
      ...forcedParams, 
      force_filename: true,
      batch_enhancement: false 
    })
  }

  return {
    getImg,
    getLogClass,
    forcedParams,
    testSearch,
    searchTmdbForTest,
    handleRecognize
  }
}
