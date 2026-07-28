/**
 * 导航 Store — 管理全局导航状态
 *
 * 迁移自旧版 navigationStore.ts (reactive → Pinia defineStore)
 * 包含：待订阅数据、全局搜索、详情页导航
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

export interface PendingSubscription {
  type: 'tmdb' | 'bangumi'
  tmdbId?: string | number
  bangumiId?: string | number
  mediaType?: 'movie' | 'tv'
  title?: string
  year?: string
  season?: number
  totalEpisodes?: number
  poster_path?: string
}

export const useNavigationStore = defineStore('navigation', () => {
  const router = useRouter()

  // --- 待订阅数据 ---
  const pendingSubscription = ref<PendingSubscription | null>(null)

  // --- 全局搜索 ---
  const searchKeyword = ref('')
  const isLogConsoleOpen = ref(false)
  const isExternalControlOpen = ref(false)

  // --- 导航方法 ---
  function navigateToSubscription(data: PendingSubscription) {
    pendingSubscription.value = data
    router.push({ name: 'Subscription' })
  }

  function triggerGlobalSearch(keyword: string) {
    searchKeyword.value = keyword
    router.push({ name: 'JackettSearch' })
  }

  function openTmdbDetail(id: string | number, type: string = 'tv') {
    router.push({ name: 'TmdbDetail', params: { id, type } })
  }

  function openBangumiDetail(id: string | number) {
    router.push({ name: 'BangumiDetail', params: { id } })
  }

  function openTmdbPersonDetail(id: string | number) {
    router.push({ name: 'TmdbPersonDetail', params: { id } })
  }

  return {
    pendingSubscription,
    searchKeyword,
    isLogConsoleOpen,
    isExternalControlOpen,
    navigateToSubscription,
    triggerGlobalSearch,
    openTmdbDetail,
    openBangumiDetail,
    openTmdbPersonDetail,
  }
})
