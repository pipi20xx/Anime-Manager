import { ref } from 'vue'

export function useUsageGuide() {
  const activeTab = ref('pipeline')

  return {
    activeTab
  }
}
