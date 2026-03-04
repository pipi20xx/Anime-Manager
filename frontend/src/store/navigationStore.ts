import { ref, watch } from 'vue'

export const currentViewKey = ref(localStorage.getItem('apm_view_key') || 'ExploreView')

watch(currentViewKey, (val) => {
  localStorage.setItem('apm_view_key', val)
})

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

export const pendingSubscription = ref<PendingSubscription | null>(null)

export const navigateToSubscription = (data: PendingSubscription) => {
  pendingSubscription.value = data
  currentViewKey.value = 'SubscriptionView'
}

// Search Global State
export const searchKeyword = ref('')
export const isSearchOpen = ref(false)
export const isLogConsoleOpen = ref(false)
export const isExternalControlOpen = ref(false)

export const triggerGlobalSearch = (keyword: string) => {
  searchKeyword.value = keyword
  isSearchOpen.value = true
}

// Auth State
export const isLoggedIn = ref(!!localStorage.getItem('apm_access_token'))
export const username = ref(localStorage.getItem('apm_username') || '')
export const uiAuthEnabled = ref(localStorage.getItem('apm_ui_auth_enabled') !== 'false')

export const loginSuccess = (token: string, user: string) => {
  localStorage.setItem('apm_access_token', token)
  localStorage.setItem('apm_username', user)
  isLoggedIn.value = true
  username.value = user
  // 同时同步到原来的 apm_external_token 兼容旧请求
  localStorage.setItem('apm_external_token', token)
}

export const logout = () => {
  localStorage.removeItem('apm_access_token')
  localStorage.removeItem('apm_username')
  localStorage.removeItem('apm_external_token')
  isLoggedIn.value = false
  username.value = ''
}
