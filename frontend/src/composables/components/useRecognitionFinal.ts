import { computed } from 'vue'
import { recognitionState } from '../../store/recognitionStore'

export function useRecognitionFinal() {
  const final = computed(() => recognitionState.data?.final_result || {})
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const safeGet = (val: any, fallback = '-') => (val !== undefined && val !== null) ? String(val) : fallback

  const title = computed(() => safeGet(final.value.title, '未知标题'))
  const poster = computed(() => safeGet(final.value.poster_path, ''))
  const category = computed(() => safeGet(final.value.category, '未知分类'))
  const platform = computed(() => safeGet(final.value.platform, ''))
  const tmdb_id = computed(() => safeGet(final.value.tmdb_id, 'N/A'))
  const release_date = computed(() => safeGet(final.value.release_date, '未知日期'))
  const secondary_category = computed(() => safeGet(final.value.secondary_category, ''))
  const origin_country = computed(() => safeGet(final.value.origin_country, ''))

  const resolution = computed(() => safeGet(final.value.resolution, ''))
  const v_encode = computed(() => safeGet(final.value.video_encode, ''))
  const v_effect = computed(() => safeGet(final.value.video_effect, ''))
  const a_encode = computed(() => safeGet(final.value.audio_encode, ''))

  const year = computed(() => safeGet(final.value.year))
  const season = computed(() => final.value.season !== undefined ? `S${final.value.season}` : 'S-')
  const episode = computed(() => final.value.episode !== undefined ? `E${final.value.episode}` : 'E-')
  const source = computed(() => safeGet(final.value.source))

  const subtitle = computed(() => safeGet(final.value.subtitle, '无'))
  const team = computed(() => safeGet(final.value.team, '未知制作组'))
  const processed_name = computed(() => safeGet(final.value.processed_name))
  const filename = computed(() => safeGet(final.value.filename))

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
    final,
    title, poster, category, platform, tmdb_id, release_date, secondary_category, origin_country,
    resolution, v_encode, v_effect, a_encode,
    year, season, episode, source,
    subtitle, team, processed_name, filename,
    getImg
  }
}
