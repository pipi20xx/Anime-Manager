<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton, NSpin
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as CastIcon,
  ExpandMoreOutlined as ExpandIcon,
  RefreshOutlined as LoadingIcon,
  CheckCircleOutlined,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch, openTmdbPersonDetail } from '../../store/navigationStore'
import { STATUS_MAP } from '../../composables/useTmdbDisplayMaps'

const route = useRoute()
const router = useRouter()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const message = useMessage()

const tmdbId = computed(() => route.params.id as string)

const loading = ref(false)
const detail = ref<any>(null)
const subscriptions = ref<any[]>([])
const expandedSeasons = ref<Set<number>>(new Set())
const seasonEpisodes = ref<Map<string, any[]>>(new Map())
const seasonEmbyInfo = ref<Map<string, any>>(new Map())
const loadingSeasons = ref<Set<string>>(new Set())
const embyStatus = ref<any>(null)
const recommendations = ref<any[]>([])
const episodeGroup = ref<any>(null)

const fetchSubscriptions = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/subscriptions`)
    if (res.ok) subscriptions.value = await res.json()
  } catch (e) {}
}

const isSubscribed = computed(() => {
  return subscriptions.value.some((sub: any) => String(sub.tmdb_id) === String(tmdbId.value))
})

const displayStatus = computed(() => {
  if (!detail.value?.status) return ''
  return STATUS_MAP[detail.value.status] || detail.value.status
})

const displayCountries = computed(() => {
  return detail.value?.origin_country_zh || []
})

const displayLanguage = computed(() => {
  return detail.value?.original_language_zh || ''
})

const genreNameMap = ref<Map<string, string>>(new Map())

const displayGenres = computed(() => {
  if (!detail.value || !detail.value.genres) return []
  return [...new Set(detail.value.genres
    .filter((g: any) => g)
    .map((g: string) => genreNameMap.value.get(g.toLowerCase()) || g))]
})

const DEFAULT_AVATAR = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzk5OSI+PHBhdGggZD0iTTEyIDEyYzIuMjEgMCA0LTEuNzkgNC00cy0xLjc5LTQtNC00LTQgMS43OS00IDQgMS43OSA0IDQgNHptMCAyYy0yLjY3IDAtOCAxLjM0LTggNHYyaDE2di0yYzAtMi42Ni01LjMzLTQtOC00eiIvPjwvc3ZnPg=='
const DEFAULT_POSTER = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyMDAgMzAwIiBmaWxsPSIjZTBlMGUwIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIvPjxwYXRoIGQ9Ik04MCAxMjAgaDQwIHY0MCBoLTQwIHoiIGZpbGw9IiM5OTkiLz48Y2lyY2xlIGN4PSIxMDAiIGN5PSI5MCIgcj0iMjUiIGZpbGw9IiM5OTkiLz48L3N2Zz4='

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

const getPoster = (path: string) => getImg(path)

const fetchDetail = async () => {
  const id = tmdbId.value
  const type = route.params.type as string || 'tv'

  if (!id) return

  loading.value = true
  fetchSubscriptions()
  try {
    const apiType = type === '电影' || type === 'movie' ? 'movie' : 'tv'
    const [detailRes, recRes, genreRes] = await Promise.all([
      fetch(`${API_BASE}/api/tmdb/detail/${apiType}/${id}`),
      fetch(`${API_BASE}/api/tmdb/recommendations/${apiType}/${id}`),
      fetch(`${API_BASE}/api/user_mapping/genres`)
    ])

    if (detailRes.ok) {
        detail.value = await detailRes.json()
    } else {
        message.error('获取 TMDB 详情失败')
    }

    if (recRes.ok) {
      recommendations.value = await recRes.json()
    }

    if (genreRes.ok) {
      const genreData = await genreRes.json()
      const map = new Map<string, string>()
      for (const item of genreData) {
        if (item.name_en && item.name_zh) {
          map.set(item.name_en.toLowerCase(), item.name_zh)
        }
      }
      genreNameMap.value = map
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchBackgroundData = async () => {
  const id = tmdbId.value
  const type = route.params.type as string || 'tv'
  if (!id) return

  const apiType = type === '电影' || type === 'movie' ? 'movie' : 'tv'

  try {
    const embyRes = await fetch(`${API_BASE}/api/tmdb/detail/${apiType}/${id}/emby`)
    if (embyRes.ok) {
      embyStatus.value = await embyRes.json()
    }
  } catch (e) {
    console.error('Failed to fetch emby status', e)
  }

  if (apiType === 'tv') {
    try {
      const episodeGroupRes = await fetch(`${API_BASE}/api/sytmdb/episodegroup/${id}`)
      if (episodeGroupRes.ok) {
        episodeGroup.value = await episodeGroupRes.json()
      }
    } catch (e) {
      console.error('Failed to fetch episode group', e)
    }
  }
}

const goBack = () => {
  router.back()
}

const openExternal = () => {
    const apiType = (route.params.type as string) === 'movie' ? 'movie' : 'tv'
    window.open(`https://www.themoviedb.org/${apiType}/${tmdbId.value}`, '_blank')
}

const openImdb = (imdbId: string) => {
    window.open(`https://www.imdb.com/title/${imdbId}`, '_blank')
}

const handleSubscribe = () => {
    if (!detail.value) return
    const type = route.params.type as string || 'tv'
    navigateToSubscription({
        type: 'tmdb',
        tmdbId: tmdbId.value,
        mediaType: type as 'movie' | 'tv',
        title: detail.value.title || detail.value.name
    })
}

const handleSearch = () => {
    triggerGlobalSearch(detail.value.original_title || detail.value.original_name || detail.value.title || detail.value.name)
}

const hasEpisodeGroup = computed(() => {
  return episodeGroup.value && episodeGroup.value.groups && episodeGroup.value.groups.length > 0
})

const getMappedEpisodeInfo = (tmdbSeason: number, tmdbEpisode: number) => {
  if (!hasEpisodeGroup.value) {
    return { localSeason: tmdbSeason, localEpisode: tmdbEpisode }
  }
  
  for (const group of episodeGroup.value.groups) {
    const localSeason = group.order
    for (const ep of group.episodes) {
      if (ep.season_number === tmdbSeason && ep.episode_number === tmdbEpisode) {
        return {
          localSeason: localSeason,
          localEpisode: ep.order + 1
        }
      }
    }
  }
  
  return { localSeason: tmdbSeason, localEpisode: tmdbEpisode }
}

const toggleSeason = async (seasonNumber: number) => {
  const key = `${tmdbId.value}-${seasonNumber}`
  
  if (expandedSeasons.value.has(seasonNumber)) {
    expandedSeasons.value.delete(seasonNumber)
    expandedSeasons.value = new Set(expandedSeasons.value)
    return
  }
  
  expandedSeasons.value.add(seasonNumber)
  expandedSeasons.value = new Set(expandedSeasons.value)
  
  if (!seasonEpisodes.value.has(key)) {
    loadingSeasons.value.add(key)
    loadingSeasons.value = new Set(loadingSeasons.value)
    
    try {
      const tmdbRes = await fetch(`${API_BASE}/api/tmdb/season/${tmdbId.value}/${seasonNumber}`)
      
      if (tmdbRes.ok) {
        const data = await tmdbRes.json()
        seasonEpisodes.value.set(key, data)
        seasonEpisodes.value = new Map(seasonEpisodes.value)
      }
      
      if (hasEpisodeGroup.value) {
        const localSeasonsToFetch = new Set<number>()
        
        for (const group of episodeGroup.value.groups) {
          const hasCurrentSeason = group.episodes.some((ep: any) => ep.season_number === seasonNumber)
          if (hasCurrentSeason) {
            localSeasonsToFetch.add(group.order)
          }
        }
        
        for (const localSeason of localSeasonsToFetch) {
          const localKey = `local-${tmdbId.value}-${localSeason}`
          if (!seasonEmbyInfo.value.has(localKey)) {
            try {
              const localEmbyRes = await fetch(`${API_BASE}/api/tmdb/season/${tmdbId.value}/${localSeason}/emby`)
              if (localEmbyRes.ok) {
                const localEmbyData = await localEmbyRes.json()
                seasonEmbyInfo.value.set(localKey, localEmbyData.episodes || {})
                seasonEmbyInfo.value = new Map(seasonEmbyInfo.value)
              }
            } catch (e) {
              console.error('Failed to fetch local season emby info', e)
            }
          }
        }
      } else {
        const embyRes = await fetch(`${API_BASE}/api/tmdb/season/${tmdbId.value}/${seasonNumber}/emby`)
        if (embyRes.ok) {
          const embyData = await embyRes.json()
          seasonEmbyInfo.value.set(key, embyData.episodes || {})
          seasonEmbyInfo.value = new Map(seasonEmbyInfo.value)
        }
      }
    } catch (e) {
      console.error('Failed to fetch season episodes', e)
    } finally {
      loadingSeasons.value.delete(key)
      loadingSeasons.value = new Set(loadingSeasons.value)
    }
  }
}

const getSeasonInfo = (seasonNumber: number) => {
  const key = `${tmdbId.value}-${seasonNumber}`
  const data = seasonEpisodes.value.get(key)
  return data?.season_info || null
}

const getSeasonEpisodes = (seasonNumber: number) => {
  const key = `${tmdbId.value}-${seasonNumber}`
  const data = seasonEpisodes.value.get(key)
  return data?.episodes || []
}

const isSeasonLoading = (seasonNumber: number) => {
  const key = `${tmdbId.value}-${seasonNumber}`
  return loadingSeasons.value.has(key)
}

const isSeasonExpanded = (seasonNumber: number) => {
  return expandedSeasons.value.has(seasonNumber)
}

const getEpisodeEmbyInfo = (seasonNumber: number, episodeNumber: number) => {
  if (hasEpisodeGroup.value) {
    const { localSeason, localEpisode } = getMappedEpisodeInfo(seasonNumber, episodeNumber)
    const localKey = `local-${tmdbId.value}-${localSeason}`
    const embyData = seasonEmbyInfo.value.get(localKey)
    return embyData?.[localEpisode] || null
  }
  
  const key = `${tmdbId.value}-${seasonNumber}`
  const embyData = seasonEmbyInfo.value.get(key)
  return embyData?.[episodeNumber] || null
}

const formatFileSize = (bytes: number) => {
  if (!bytes || bytes === 0) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(2)} ${units[i]}`
}

const isInLibrary = computed(() => {
  return embyStatus.value?.exists || false
})

const getSeasonLibraryStatus = (seasonNumber: number) => {
  return embyStatus.value?.seasons?.[seasonNumber] || null
}

const handleRecClick = (rec: any) => {
  const type = rec.media_type || rec.type || 'tv'
  
  detail.value = null
  expandedSeasons.value = new Set()
  seasonEpisodes.value = new Map()
  seasonEmbyInfo.value = new Map()
  recommendations.value = []
  embyStatus.value = null
  
  router.push({ name: 'TmdbDetail', params: { id: rec.id, type: route.params.type } })
}

const openPersonDetail = (personId: string | number) => {
  if (!personId) return
  router.push({ name: 'TmdbPersonDetail', params: { id: personId } })
}

onMounted(() => {
  fetchDetail().then(() => {
    fetchBackgroundData()
  })
})

watch(tmdbId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchDetail()
  }
})
</script>

<template>
  <div class="tmdb-detail-page">
    <div class="page-header">
      <n-button size="small" @click="goBack">
        <template #icon><n-icon><BackIcon /></n-icon></template>
        返回
      </n-button>
    </div>

    <div v-if="loading && !detail" class="loading-box">
      <n-skeleton height="400px" width="100%" />
    </div>

    <div v-else-if="detail" class="detail-container">
        <div class="header-content">
          <div class="poster-col">
            <n-image :src="getPoster(detail.poster_path) || DEFAULT_POSTER" class="main-poster" object-fit="cover" :fallback-src="DEFAULT_POSTER" />
          </div>
          <div class="info-col">
            <div class="title-row">
              <h1 class="title">{{ detail.title || detail.name }}</h1>
              <n-tag v-if="detail.adult" type="error" size="small" round style="font-weight: bold;">R18</n-tag>
              <n-tag v-if="isInLibrary" type="success" size="small" round>
                <template #icon><n-icon><CheckCircleOutlined /></n-icon></template>
                已入库
              </n-tag>
            </div>
            <div class="original-title">{{ detail.original_title || detail.original_name }}</div>
            <div v-if="detail.tagline" class="tagline">"{{ detail.tagline }}"</div>
            
            <n-space class="meta-tags" align="center">
              <n-tag type="warning" round size="small">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.vote_average?.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="small" style="background: var(--app-surface-card-mixed)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ detail.release_date || detail.first_air_date }}
              </n-tag>
              <n-tag v-if="detail.number_of_seasons" type="info" size="small" round>
                {{ detail.number_of_seasons }} 季
              </n-tag>
              <n-tag v-if="detail.number_of_episodes" type="info" size="small" round>
                {{ detail.number_of_episodes }} 集
              </n-tag>
            </n-space>

            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">TMDB ID</span>
                <span class="info-value link" @click="openExternal">{{ detail.id }}</span>
              </div>
              <div v-if="detail.imdb_id" class="info-item">
                <span class="info-label">IMDb ID</span>
                <span class="info-value link" @click="openImdb(detail.imdb_id)">{{ detail.imdb_id }}</span>
              </div>
              <div v-if="displayStatus" class="info-item">
                <span class="info-label">状态</span>
                <span class="info-value">{{ displayStatus }}</span>
              </div>
              <div v-if="displayCountries.length" class="info-item">
                <span class="info-label">地区</span>
                <span class="info-value">{{ displayCountries.join(' / ') }}</span>
              </div>
              <div v-if="displayLanguage" class="info-item">
                <span class="info-label">语言</span>
                <span class="info-value">{{ displayLanguage }}</span>
              </div>
            </div>

            <div class="actions">
              <n-button type="primary" size="small" @click="handleSubscribe" :disabled="isSubscribed">
                {{ isSubscribed ? '已在订阅中' : '订阅/追番' }}
              </n-button>
              <n-button type="primary" size="small" @click="handleSearch">
                搜资源
              </n-button>
            </div>
          </div>
        </div>

        <div class="body-content">
          <div v-if="displayGenres.length > 0" class="genres-row">
            <n-space>
              <n-tag v-for="g in displayGenres" :key="g" type="primary" size="tiny" :bordered="false" round>
                {{ g }}
              </n-tag>
            </n-space>
          </div>

          <div class="overview-section">
            <h3>简介</h3>
            <p class="overview-text">{{ detail.overview || '暂无简介' }}</p>
          </div>

          <div v-if="detail.cast?.length" class="cast-section">
            <h3><n-icon><CastIcon /></n-icon> 演职员</h3>
            <n-scrollbar x-scrollable>
              <div class="cast-scroller">
                <div v-for="c in detail.cast" :key="c.actor + c.character" class="cast-card" @click="openPersonDetail(c.id)">
                  <div class="cast-avatar">
                    <n-image :src="getPoster(c.image) || DEFAULT_AVATAR" object-fit="cover" preview-disabled :fallback-src="DEFAULT_AVATAR" />
                  </div>
                  <div class="cast-names">
                    <div class="actor-name" :title="c.actor">{{ c.actor }}</div>
                  </div>
                </div>
              </div>
            </n-scrollbar>
          </div>

          <div v-if="detail.seasons?.length" class="seasons-section">
            <h3>季度信息</h3>
            <div class="seasons-list">
              <div v-for="s in detail.seasons" :key="s.id" class="season-item">
                <div class="season-card" @click="toggleSeason(s.season_number)">
                  <div class="s-poster">
                    <n-image :src="getPoster(s.poster_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" />
                  </div>
                  <div class="s-info">
                    <div class="s-name-row">
                      <span class="s-name">{{ s.name }}</span>
                      <n-tag v-if="getSeasonLibraryStatus(s.season_number)?.exists" type="success" size="tiny" round>
                        已入库
                      </n-tag>
                    </div>
                    <div class="s-ep">{{ s.episode_count }} 集</div>
                  </div>
                  <div class="s-expand-icon">
                    <n-icon v-if="isSeasonLoading(s.season_number)" class="loading-spin">
                      <LoadingIcon />
                    </n-icon>
                    <n-icon v-else :class="{ 'expanded': isSeasonExpanded(s.season_number) }">
                      <ExpandIcon />
                    </n-icon>
                  </div>
                </div>
                <div v-if="isSeasonExpanded(s.season_number)" class="episodes-panel">
                  <div v-if="getSeasonInfo(s.season_number)?.overview" class="season-overview">
                    {{ getSeasonInfo(s.season_number).overview }}
                  </div>
                  <div v-for="ep in getSeasonEpisodes(s.season_number)" :key="ep.episode" class="episode-item">
                    <div class="ep-still" v-if="ep.still_path">
                      <n-image :src="getPoster(ep.still_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" />
                    </div>
                    <div class="ep-still ep-still-placeholder" v-else>
                      <span>E{{ ep.episode }}</span>
                    </div>
                    <div class="ep-content">
                      <div class="ep-header">
                        <div class="ep-title">
                          <span class="ep-num-badge">E{{ ep.episode }}</span>
                          <span class="ep-name">{{ ep.name || '未命名' }}</span>
                          <span v-if="ep.episode_type === 'finale'" class="ep-type ep-type-finale">本季大结局</span>
                          <span v-else-if="ep.episode_type === 'mid_season'" class="ep-type ep-type-mid">季中结局</span>
                          <span v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.exists" class="ep-type ep-type-emby">已入库</span>
                        </div>
                        <div class="ep-meta">
                          <span v-if="ep.vote_average" class="ep-rating">
                            <n-icon size="12"><StarIcon /></n-icon>
                            {{ ep.vote_average.toFixed(1) }}
                          </span>
                          <span v-if="ep.runtime" class="ep-runtime">{{ ep.runtime }}分钟</span>
                          <span v-if="ep.air_date" class="ep-date">{{ ep.air_date }}</span>
                        </div>
                      </div>
                      <div v-if="ep.overview" class="ep-overview">{{ ep.overview }}</div>
                      <div v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.files?.length" class="ep-emby-info">
                        <div v-for="(file, idx) in getEpisodeEmbyInfo(s.season_number, ep.episode).files" :key="idx" class="emby-file-item">
                          <span class="emby-filename">{{ file.name }}</span>
                          <span v-if="file.size" class="emby-size"> · {{ formatFileSize(file.size) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="getSeasonEpisodes(s.season_number).length === 0 && !isSeasonLoading(s.season_number)" class="no-episodes">
                    暂无集信息
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="recommendations.length" class="recommendations-section">
            <h3>相关推荐</h3>
            <n-scrollbar x-scrollable>
              <div class="rec-list">
                <div v-for="rec in recommendations" :key="rec.id" class="rec-item" @click="handleRecClick(rec)">
                  <div class="rec-poster">
                    <n-image :src="getPoster(rec.poster_path)" object-fit="cover" preview-disabled />
                  </div>
                  <div class="rec-info">
                    <div class="rec-title">{{ rec.title || rec.name }}</div>
                    <div class="rec-meta">
                      <span v-if="rec.vote_average" class="rec-rating">
                        <n-icon size="10"><StarIcon /></n-icon>
                        {{ rec.vote_average.toFixed(1) }}
                      </span>
                      <span class="rec-year">{{ (rec.release_date || rec.first_air_date || '').slice(0, 4) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </n-scrollbar>
          </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.tmdb-detail-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--app-bg-color) var(--app-layout-opacity, 100%), transparent);
}

.page-header {
  padding: 16px 32px;
  border-bottom: 1px solid var(--app-border-light);
}

.loading-box { padding: 40px; }

.detail-container { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.header-content { position: relative; z-index: 2; padding: 30px 32px; display: flex; gap: 20px; width: 100%; }
.main-poster {
  width: 260px; aspect-ratio: 3/4;
  border-radius: var(--card-border-radius, 6px);
  box-shadow: 0 8px 24px var(--shadow-heavy);
  border: 1px solid var(--app-border-light);
  overflow: hidden; background: var(--bg-primary);
}
.main-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }

.info-col { flex-grow: 1; }
.title-row { display: flex; align-items: center; gap: 12px; }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--text-primary); line-height: 1.2; }
.original-title { font-size: 13px; color: var(--text-tertiary); margin-bottom: 4px; }
.tagline { font-size: 14px; font-style: italic; color: var(--n-primary-color); margin-bottom: 12px; opacity: var(--opacity-primary); }
.meta-tags { margin-bottom: 15px; }
.info-grid { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 15px; }
.info-item { display: flex; align-items: center; gap: 6px; }
.info-label { font-size: 12px; color: var(--text-tertiary); }
.info-value { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.info-value.link { color: var(--n-primary-color); cursor: pointer; }
.info-value.link:hover { text-decoration: underline; }
.actions { display: flex; gap: 10px; }

.body-content { padding: 30px 32px 32px 32px; }
.genres-row { margin-bottom: 16px; }
.overview-section { margin-bottom: 20px; }
.overview-section h3 { margin: 0 0 8px 0; color: var(--n-primary-color); font-size: 15px; }
.overview-text { color: var(--text-secondary); line-height: 1.6; font-size: 14px; text-align: justify; }

.cast-section { margin-bottom: 24px; }
.cast-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; display: flex; align-items: center; gap: 6px; }
.cast-scroller { display: flex; gap: 16px; padding-bottom: 8px; }
.cast-card { min-width: 90px; width: 90px; display: flex; flex-direction: column; align-items: center; text-align: center; cursor: pointer; transition: transform 0.2s; }
.cast-card:hover { transform: translateY(-4px); }
.cast-avatar {
  width: 64px; height: 64px;
  border-radius: 50%; overflow: hidden;
  border: 1px solid var(--app-border-light);
  margin-bottom: 6px; background: var(--app-surface-card-mixed);
}
.cast-avatar :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.actor-name { font-size: 12px; color: var(--text-primary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }

.seasons-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; }
.seasons-list { display: flex; flex-direction: column; gap: 12px; }
.season-item { border: 1px solid var(--app-border-light); border-radius: var(--card-border-radius, 8px); overflow: hidden; }
.season-card { 
  display: flex; align-items: center; gap: 12px; padding: 12px; 
  cursor: pointer; transition: background 0.2s;
}
.season-card:hover { background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(255,255,255,0.04)); }
.s-poster { width: 60px; aspect-ratio: 2/3; border-radius: var(--button-border-radius, 4px); overflow: hidden; background: var(--bg-primary); flex-shrink: 0; }
.s-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.s-info { flex: 1; min-width: 0; }
.s-name-row { display: flex; align-items: center; gap: 8px; }
.s-name { font-size: 13px; font-weight: bold; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-ep { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
.s-expand-icon { color: var(--text-tertiary); transition: transform 0.3s; }
.s-expand-icon .expanded { transform: rotate(180deg); }
.loading-spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.episodes-panel {
  background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.05));
  border-top: 1px solid var(--app-border-light);
  padding: 12px;
}
.season-overview {
  font-size: 13px; color: var(--text-secondary); line-height: 1.6;
  padding: 10px 12px; margin-bottom: 12px;
  background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.1)); border-radius: 6px;
  border-left: 3px solid var(--n-primary-color);
}
.episode-item { 
  display: flex; gap: 12px; 
  padding: 10px; border-radius: 6px; 
  transition: background 0.2s; 
  margin-bottom: 8px;
}
.episode-item:last-child { margin-bottom: 0; }
.episode-item:hover { background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(255,255,255,0.04)); }
.ep-still { 
  width: 200px; aspect-ratio: 16/9; 
  border-radius: 4px; overflow: hidden; 
  flex-shrink: 0; background: var(--bg-primary); 
}
.ep-still :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.ep-still-placeholder {
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); font-size: 18px; font-weight: bold;
  background: var(--app-surface-card-mixed);
}
.ep-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.ep-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.ep-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ep-num-badge { 
  font-size: 11px; font-weight: bold; color: var(--n-primary-color); 
  padding: 2px 6px; background: var(--n-primary-color-supply); 
  border-radius: 4px; flex-shrink: 0; 
}
.ep-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.ep-type { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 6px; }
.ep-type-finale { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.ep-type-mid { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.ep-type-emby { background: rgba(34, 197, 94, 0.1); color: #22c55e; }
.ep-meta { display: flex; gap: 8px; font-size: 12px; color: var(--text-tertiary); }
.ep-rating { display: flex; align-items: center; gap: 2px; }
.ep-overview { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
.ep-emby-info { margin-top: 6px; padding: 8px; background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.1)); border-radius: 4px; }
.emby-file-item { font-size: 11px; color: var(--text-tertiary); margin-bottom: 4px; }
.emby-file-item:last-child { margin-bottom: 0; }
.emby-filename { color: var(--text-secondary); }
.no-episodes { padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px; }

.recommendations-section { margin-top: 24px; }
.recommendations-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; }
.rec-list { display: flex; gap: 12px; padding-bottom: 8px; }
.rec-item { min-width: 120px; width: 120px; cursor: pointer; transition: transform 0.2s; }
.rec-item:hover { transform: translateY(-4px); }
.rec-poster { width: 100%; aspect-ratio: 2/3; border-radius: 6px; overflow: hidden; background: var(--bg-primary); margin-bottom: 8px; }
.rec-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.rec-info { width: 100%; }
.rec-title { font-size: 12px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rec-meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-tertiary); margin-top: 4px; }
.rec-rating { display: flex; align-items: center; gap: 2px; }
</style>
