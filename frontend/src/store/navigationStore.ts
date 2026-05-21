import { ref } from 'vue'
import router from '../router'

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
  router.push({ name: 'Subscription' })
}

export const searchKeyword = ref('')
export const isSearchOpen = ref(false)
export const isLogConsoleOpen = ref(false)
export const isExternalControlOpen = ref(false)

export const triggerGlobalSearch = (keyword: string) => {
  searchKeyword.value = keyword
  isSearchOpen.value = true
}

export const isLoggedIn = ref(!!localStorage.getItem('apm_access_token'))
export const username = ref(localStorage.getItem('apm_username') || '')

export const loginSuccess = (token: string, user: string) => {
  localStorage.setItem('apm_access_token', token)
  localStorage.setItem('apm_username', user)
  isLoggedIn.value = true
  username.value = user
}

export const logout = () => {
  localStorage.removeItem('apm_access_token')
  localStorage.removeItem('apm_username')
  isLoggedIn.value = false
  username.value = ''
}

export const openTmdbDetail = (id: string | number, type: string = 'tv', initial: any = null) => {
  router.push({ name: 'TmdbDetail', params: { id } })
}

export interface BangumiDetailState {
  show: boolean
  id: string | number
  initial: any
}

export const bangumiDetailState = ref<BangumiDetailState>({
  show: false,
  id: '',
  initial: null
})

export const openBangumiDetail = (id: string | number, initial: any = null) => {
  router.push({ name: 'BangumiDetail', params: { id } })
}

export interface TmdbPersonDetailState {
  show: boolean
  id: string | number
  initial: any
}

export const tmdbPersonDetailState = ref<TmdbPersonDetailState>({
  show: false,
  id: '',
  initial: null
})

export const openTmdbPersonDetail = (id: string | number, initial: any = null) => {
  router.push({ name: 'TmdbPersonDetail', params: { id } })
}
