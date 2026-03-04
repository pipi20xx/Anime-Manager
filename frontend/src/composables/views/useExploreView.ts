import { ref, computed, defineAsyncComponent } from 'vue'

export function useExploreView() {
  const RecommendTab = defineAsyncComponent(() => import('../../views/explore/RecommendTab.vue'))
  const DiscoveryTab = defineAsyncComponent(() => import('../../views/explore/DiscoveryTab.vue'))
  const SearchTab = defineAsyncComponent(() => import('../../views/explore/SearchTab.vue'))

  const currentTab = ref("recommend")

  const activeComponent = computed(() => {
    switch (currentTab.value) {
      case 'recommend': return RecommendTab
      case 'discover': return DiscoveryTab
      case 'search': return SearchTab
      default: return RecommendTab
    }
  })

  return {
    currentTab,
    activeComponent
  }
}
