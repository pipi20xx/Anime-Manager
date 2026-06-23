<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton, NCollapse, NCollapseItem
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as CastIcon,
  ExpandMoreOutlined as ExpandIcon,
  RefreshOutlined as LoadingIcon,
  CheckCircleOutlined,
  ArrowBackOutlined as BackIcon,
  MovieOutlined as MovieIcon
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
  <div class="m-page m-page-safe-bottom">
    <!-- Header -->
    <div class="m-header m-header-plain">
      <div class="m-header-left">
        <n-button v-bind="{ text: true }" size="small" @click="goBack">
          <template #icon><n-icon size="22"><BackIcon /></n-icon></template>
        </n-button>
      </div>
      <div class="m-header-right">
        <n-button text size="small" @click="openExternal">
          <template #icon><n-icon size="20"><LinkIcon /></n-icon></template>
        </n-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading && !detail" class="m-content">
      <n-skeleton height="240px" width="100%" style="border-radius: var(--m-radius-lg); margin-bottom: var(--m-spacing-lg)" />
      <n-skeleton height="20px" width="60%" style="margin-bottom: var(--m-spacing-md)" />
      <n-skeleton height="16px" width="40%" style="margin-bottom: var(--m-spacing-lg)" />
      <n-skeleton height="80px" width="100%" style="border-radius: var(--m-radius-lg)" />
    </div>

    <!-- Content -->
    <div v-else-if="detail" class="m-page-scrollable">
      <!-- Hero -->
      <div class="m-detail-hero" style="min-height: auto; padding: var(--m-spacing-lg) 0;">
        <div class="m-detail-hero-content" style="padding: 0 var(--m-spacing-lg); align-items: flex-start;">
          <div class="m-detail-poster" style="width: 120px;">
            <n-image :src="getPoster(detail.poster_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" style="width: 100%; aspect-ratio: 3/4;" />
          </div>
          <div class="m-detail-info">
            <h1 class="m-detail-title">
              {{ detail.title || detail.name }}
              <n-tag v-if="detail.adult" type="error" size="tiny" round style="margin-left: 8px; font-weight: bold;">R18</n-tag>
            </h1>
            <div v-if="detail.original_title || detail.original_name" style="font-size: var(--m-text-sm); color: var(--text-muted); margin-top: var(--m-spacing-xs);">
              {{ detail.original_title || detail.original_name }}
            </div>
            <div class="m-detail-meta" style="flex-wrap: wrap;">
              <n-tag v-if="isInLibrary" type="success" size="tiny" round>
                <template #icon><n-icon><CheckCircleOutlined /></n-icon></template>
                已入库
              </n-tag>
              <n-tag type="warning" round size="tiny">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.vote_average?.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="tiny" style="background: var(--app-surface-inner)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ detail.release_date || detail.first_air_date }}
              </n-tag>
              <n-tag v-if="detail.number_of_seasons" type="info" size="tiny" round>
                {{ detail.number_of_seasons }} 季
              </n-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="m-detail-actions" style="display: flex; gap: var(--m-spacing-md); padding: 0 var(--m-spacing-lg) var(--m-spacing-lg);">
        <n-button type="primary" block size="large" @click="handleSubscribe" :disabled="isSubscribed">
          {{ isSubscribed ? '已在订阅中' : '订阅/追番' }}
        </n-button>
        <n-button type="primary" ghost block size="large" @click="handleSearch">
          搜资源
        </n-button>
      </div>

      <div class="m-detail-body">
        <!-- Genres -->
        <div v-if="displayGenres.length > 0" class="m-detail-section">
          <n-space>
            <n-tag v-for="g in displayGenres" :key="g" type="primary" size="small" :bordered="false" round>
              {{ g }}
            </n-tag>
          </n-space>
        </div>

        <!-- Overview -->
        <div class="m-detail-section">
          <h3 class="m-detail-section-title">简介</h3>
          <p style="color: var(--text-secondary); line-height: 1.7; font-size: var(--m-text-md); margin: 0;">
            {{ detail.overview || '暂无简介' }}
          </p>
        </div>

        <!-- Meta Info -->
        <div class="m-detail-section">
          <h3 class="m-detail-section-title">信息</h3>
          <div class="meta-list">
            <div class="meta-row">
              <span class="meta-label">TMDB ID</span>
              <span class="meta-value link" @click="openExternal">{{ detail.id }}</span>
            </div>
            <div v-if="detail.imdb_id" class="meta-row">
              <span class="meta-label">IMDb ID</span>
              <span class="meta-value link" @click="openImdb(detail.imdb_id)">{{ detail.imdb_id }}</span>
            </div>
            <div v-if="displayStatus" class="meta-row">
              <span class="meta-label">状态</span>
              <span class="meta-value">{{ displayStatus }}</span>
            </div>
            <div v-if="displayCountries.length" class="meta-row">
              <span class="meta-label">地区</span>
              <span class="meta-value">{{ displayCountries.join(' / ') }}</span>
            </div>
            <div v-if="displayLanguage" class="meta-row">
              <span class="meta-label">语言</span>
              <span class="meta-value">{{ displayLanguage }}</span>
            </div>
            <div v-if="detail.number_of_episodes" class="meta-row">
              <span class="meta-label">总集数</span>
              <span class="meta-value">{{ detail.number_of_episodes }} 集</span>
            </div>
          </div>
        </div>

        <!-- Cast -->
        <div v-if="detail.cast?.length" class="m-detail-section">
          <h3 class="m-detail-section-title"><n-icon><CastIcon /></n-icon> 演职员</h3>
          <div class="m-h-scroll">
            <div v-for="c in detail.cast" :key="c.actor + c.character" class="cast-card-mobile" @click="openPersonDetail(c.id)">
              <div class="cast-avatar-mobile">
                <n-image :src="getPoster(c.image) || DEFAULT_AVATAR" object-fit="cover" preview-disabled :fallback-src="DEFAULT_AVATAR" />
              </div>
              <div class="cast-name-mobile">{{ c.actor }}</div>
            </div>
          </div>
        </div>

        <!-- Seasons -->
        <div v-if="detail.seasons?.length" class="m-detail-section">
          <h3 class="m-detail-section-title">季度信息</h3>
          <n-collapse>
            <n-collapse-item 
              v-for="s in detail.seasons" 
              :key="s.id" 
              :name="String(s.season_number)"
              @click="toggleSeason(s.season_number)"
            >
              <template #header>
                <div class="season-header-mobile">
                  <n-image :src="getPoster(s.poster_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" style="width: 48px; aspect-ratio: 3/4; border-radius: var(--m-radius-sm);" />
                  <div class="season-info-mobile">
                    <div class="season-name-mobile">
                      {{ s.name }}
                      <n-tag v-if="getSeasonLibraryStatus(s.season_number)?.exists" type="success" size="tiny" round>已入库</n-tag>
                    </div>
                    <div class="season-ep-mobile">{{ s.episode_count }} 集</div>
                  </div>
                  <n-icon v-if="isSeasonLoading(s.season_number)" class="loading-spin">
                    <LoadingIcon />
                  </n-icon>
                </div>
              </template>
              
              <div class="episodes-mobile">
                <div v-if="getSeasonInfo(s.season_number)?.overview" class="season-overview-mobile">
                  {{ getSeasonInfo(s.season_number).overview }}
                </div>
                <div v-for="ep in getSeasonEpisodes(s.season_number)" :key="ep.episode" class="episode-item-mobile">
                  <div class="ep-still-mobile" v-if="ep.still_path">
                    <n-image :src="getPoster(ep.still_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" />
                  </div>
                  <div class="ep-still-mobile ep-placeholder-mobile" v-else>
                    <span>E{{ ep.episode }}</span>
                  </div>
                  <div class="ep-content-mobile">
                    <div class="ep-title-mobile">
                      <span class="ep-num-mobile">E{{ ep.episode }}</span>
                      <span class="ep-name-mobile">{{ ep.name || '未命名' }}</span>
                      <n-tag v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.exists" type="success" size="tiny" round>已入库</n-tag>
                    </div>
                    <div class="ep-meta-mobile">
                      <span v-if="ep.vote_average"><n-icon size="12"><StarIcon /></n-icon> {{ ep.vote_average.toFixed(1) }}</span>
                      <span v-if="ep.runtime">{{ ep.runtime }}分钟</span>
                      <span v-if="ep.air_date">{{ ep.air_date }}</span>
                    </div>
                    <div v-if="ep.overview" class="ep-overview-mobile">{{ ep.overview }}</div>
                    <div v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.files?.length" class="ep-files-mobile">
                      <div v-for="(file, idx) in getEpisodeEmbyInfo(s.season_number, ep.episode).files" :key="idx" class="ep-file-mobile">
                        <span>{{ file.name }}</span>
                        <span v-if="file.size"> · {{ formatFileSize(file.size) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="getSeasonEpisodes(s.season_number).length === 0 && !isSeasonLoading(s.season_number)" class="m-empty" style="padding: var(--m-spacing-xl) 0;">
                  暂无集信息
                </div>
              </div>
            </n-collapse-item>
          </n-collapse>
        </div>

        <!-- Recommendations -->
        <div v-if="recommendations.length" class="m-detail-section">
          <h3 class="m-detail-section-title">相关推荐</h3>
          <div class="m-h-scroll">
            <div v-for="rec in recommendations" :key="rec.id" class="rec-card-mobile" @click="handleRecClick(rec)">
              <div class="rec-poster-mobile">
                <n-image :src="getPoster(rec.poster_path)" object-fit="cover" preview-disabled />
              </div>
              <div class="rec-title-mobile">{{ rec.title || rec.name }}</div>
              <div class="rec-meta-mobile">
                <span v-if="rec.vote_average"><n-icon size="10"><StarIcon /></n-icon> {{ rec.vote_average.toFixed(1) }}</span>
                <span>{{ (rec.release_date || rec.first_air_date || '').slice(0, 4) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.meta-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--m-text-md);
}

.meta-label {
  color: var(--text-muted);
}

.meta-value {
  color: var(--text-primary);
  font-weight: 500;
  max-width: 60%;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-value.link {
  color: var(--n-primary-color);
}

.cast-card-mobile {
  min-width: 72px;
  width: 72px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.cast-avatar-mobile {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  margin-bottom: var(--m-spacing-xs);
  background: var(--app-surface-inner);
}

.cast-avatar-mobile :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cast-name-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-primary);
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.season-header-mobile {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  flex: 1;
  min-width: 0;
}

.season-info-mobile {
  flex: 1;
  min-width: 0;
}

.season-name-mobile {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.season-ep-mobile {
  font-size: var(--m-text-sm);
  color: var(--text-muted);
  margin-top: var(--m-spacing-xs);
}

.loading-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.episodes-mobile {
  padding: var(--m-spacing-md) 0;
}

.season-overview-mobile {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
}

.episode-item-mobile {
  display: flex;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md) 0;
  border-bottom: 1px solid var(--app-border-light);
}

.episode-item-mobile:last-child {
  border-bottom: none;
}

.ep-still-mobile {
  width: 100px;
  flex-shrink: 0;
  aspect-ratio: 16/9;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  background: var(--app-surface-inner);
}

.ep-still-mobile :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ep-placeholder-mobile {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--m-text-sm);
}

.ep-content-mobile {
  flex: 1;
  min-width: 0;
}

.ep-title-mobile {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.ep-num-mobile {
  color: var(--n-primary-color);
  flex-shrink: 0;
}

.ep-name-mobile {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ep-meta-mobile {
  display: flex;
  gap: var(--m-spacing-md);
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  margin-top: var(--m-spacing-xs);
}

.ep-overview-mobile {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: var(--m-spacing-sm);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ep-files-mobile {
  margin-top: var(--m-spacing-sm);
}

.ep-file-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  background: var(--app-surface-inner);
  padding: var(--m-spacing-xs) var(--m-spacing-sm);
  border-radius: var(--m-radius-sm);
  margin-bottom: var(--m-spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-card-mobile {
  min-width: 110px;
  width: 110px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
}

.rec-poster-mobile {
  width: 110px;
  aspect-ratio: 2/3;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  margin-bottom: var(--m-spacing-sm);
  background: var(--app-surface-inner);
}

.rec-poster-mobile :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.rec-title-mobile {
  font-size: var(--m-text-sm);
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-meta-mobile {
  display: flex;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  margin-top: var(--m-spacing-xs);
}
</style>