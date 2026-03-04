import { reactive, ref, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { recognitionState, performRecognition } from '../../store/recognitionStore'

export function useHome() {
  const message = useMessage()
  const result = ref<any>(null)
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

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

  const sandboxSearch = reactive({ keyword: '', loading: false, results: [] as any[] })

  const handleRecognize = () => {
    performRecognition(API_BASE, message)
  }

  const searchTmdbForSandbox = async () => {
    if (!sandboxSearch.keyword) return
    sandboxSearch.loading = true
    try {
      const res = await fetch(`${API_BASE}/api/tmdb/search?query=${encodeURIComponent(sandboxSearch.keyword)}&type=${recognitionState.forced_type || 'tv'}`)
      const resData = await res.json()
      sandboxSearch.results = resData.results || []
    } catch (e: any) { message.error("搜索失败") }
    finally { sandboxSearch.loading = false }
  }

  const selectSandboxResult = (res: any) => {
    recognitionState.forced_tmdb_id = String(res.id)
    recognitionState.forced_type = res.media_type || recognitionState.forced_type
    sandboxSearch.results = []
  }

  onMounted(() => {
    const savedPriority = localStorage.getItem('anime_priority')
    if (savedPriority !== null) recognitionState.animePriority = savedPriority === 'true'
    const savedOffline = localStorage.getItem('offline_priority')
    if (savedOffline !== null) recognitionState.offlinePriority = savedOffline === 'true'
    const savedBgmPriority = localStorage.getItem('bangumi_priority')
    if (savedBgmPriority !== null) recognitionState.bangumiPriority = savedBgmPriority === 'true'
    const savedBgmFailover = localStorage.getItem('bangumi_failover')
    if (savedBgmFailover !== null) recognitionState.bangumiFailover = savedBgmFailover === 'true'
    const savedForceFile = localStorage.getItem('force_filename')
    if (savedForceFile !== null) recognitionState.forceFilename = savedForceFile === 'true'
    const savedFingerprint = localStorage.getItem('series_fingerprint')
    if (savedFingerprint !== null) recognitionState.seriesFingerprint = savedFingerprint === 'true'
    const savedBatch = localStorage.getItem('batch_enhancement')
    if (savedBatch !== null) recognitionState.batchEnhancement = savedBatch === 'true'
  })

  watch(() => recognitionState.animePriority, (v) => localStorage.setItem('anime_priority', String(v)))
  watch(() => recognitionState.offlinePriority, (v) => localStorage.setItem('offline_priority', String(v)))
  watch(() => recognitionState.bangumiPriority, (v) => localStorage.setItem('bangumi_priority', String(v)))
  watch(() => recognitionState.bangumiFailover, (v) => localStorage.setItem('bangumi_failover', String(v)))
  watch(() => recognitionState.forceFilename, (v) => localStorage.setItem('force_filename', String(v)))
  watch(() => recognitionState.seriesFingerprint, (v) => localStorage.setItem('series_fingerprint', String(v)))
  watch(() => recognitionState.batchEnhancement, (v) => localStorage.setItem('batch_enhancement', String(v)))

  return {
    API_BASE,
    result,
    sandboxSearch,
    recognitionState,
    getImg,
    handleRecognize,
    searchTmdbForSandbox,
    selectSandboxResult
  }
}
