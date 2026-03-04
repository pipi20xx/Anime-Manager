import { computed } from 'vue'
import { recognitionState } from '../../store/recognitionStore'

export function useRecognitionRaw() {
  const raw = computed(() => recognitionState.data?.raw_meta || {})
  const tags = computed(() => Array.isArray(raw.value.tags) ? raw.value.tags : [])

  const safeGet = (val: any) => val !== undefined && val !== null ? String(val) : '-'

  return {
    raw,
    tags,
    safeGet
  }
}
