import { reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function useRecognitionModal(props: any, emit: any) {
  const message = useMessage()

  // --- Hash Calculation State ---
  const isHashing = ref(false)
  const hashResult = ref<any>(null)

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
      hashResult.value = null
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

  const calculateHash = async () => {
    if (!props.file?.path || !props.data?.final_result) {
      message.warning('缺少文件路径或识别结果')
      return
    }
    isHashing.value = true
    hashResult.value = null
    try {
      const fr = props.data.final_result
      const payload: any = {
        file_path: props.file.path,
        tmdb_id: fr.tmdb_id && fr.tmdb_id !== 'N/A' ? String(fr.tmdb_id) : undefined,
        title: fr.title || undefined,
        season: fr.season !== undefined ? Number(fr.season) : undefined,
        episode: fr.episode !== undefined ? String(fr.episode) : undefined,
        media_type: fr.category || undefined,
        resolution: fr.resolution || undefined,
        team: fr.team || undefined,
        video_encode: fr.video_encode || undefined,
      }
      const res = await fetch(`${props.apiBase}/api/file_hashes/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (data.status === 'success') {
        hashResult.value = data.data
        message.success(data.message || '哈希计算完成，已写入数据库')
      } else {
        message.error(data.detail || '哈希计算失败')
      }
    } catch (e) {
      message.error('哈希计算请求失败')
    } finally {
      isHashing.value = false
    }
  }

  return {
    getImg,
    getLogClass,
    forcedParams,
    testSearch,
    searchTmdbForTest,
    handleRecognize,
    isHashing,
    hashResult,
    calculateHash
  }
}
