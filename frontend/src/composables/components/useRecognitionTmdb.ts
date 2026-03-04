import { computed } from 'vue'
import { recognitionState } from '../../store/recognitionStore'

export function useRecognitionTmdb() {
  const tmdb = computed(() => recognitionState.data?.tmdb_match || null)
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

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

  return {
    tmdb,
    getImg
  }
}
