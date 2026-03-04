import { ref, watch, nextTick } from 'vue'
import { recognitionState, getLogClass } from '../../store/recognitionStore'

export function useRecognitionLogs() {
  const logScrollbar = ref<any>(null)

  watch(() => recognitionState.logs.length, async () => { 
    await nextTick()
    if (logScrollbar.value) {
      logScrollbar.value.scrollTo({ position: 'bottom', behavior: 'smooth' })
    }
  })

  return {
    recognitionState,
    getLogClass,
    logScrollbar
  }
}
