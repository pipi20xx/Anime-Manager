<script setup lang="ts">
/**
 * TmdbDetailView — TMDB 详情页
 *
 * 功能（对标旧前端 TmdbDetailViewDesktop）:
 * - 背景横幅 + 剧照画廊 (横向滚动)
 * - 海报展示
 * - 元数据标签 (状态/评分/季数/语言/国家)
 * - 演员阵容横向滚动
 * - 季度列表 (TV) 可展开查看集信息 + Emby 入库状态
 * - 每集缩略图 + Emby 文件列表
 * - 推荐内容
 * - 快速订阅 / 搜资源 / 外部链接
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { tmdbApi, subscriptionApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'TmdbDetailView' })

const route = useRoute()
const { error: showError } = useNotification()
const navStore = useNavigationStore()

const detail = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const recommendations = ref<any[]>([])
const subscriptions = ref<any[]>([])
const embyStatus = ref<any>(null)
const embyLoading = ref(false)

// 季度展开状态
const expandedSeasons = ref<Set<number>>(new Set())
const seasonEpisodes = ref<Map<string, any>>(new Map())
const seasonEmbyInfo = ref<Map<string, any>>(new Map())
const loadingSeasons = ref<Set<string>>(new Set())
const loadingSeasonEmby = ref<Set<string>>(new Set())

// 状态映射
const STATUS_MAP: Record<string, string> = {
  'Returning Series': '连载中',
  'Ended': '已完结',
  'Canceled': '已取消',
  'Pilot': '试播',
  'In Production': '制作中',
  'Planned': '计划中',
  'Released': '已上映',
  'Post Production': '后期制作',
  'Rumored': '传闻中',
}

const isSubscribed = computed(() => {
  return subscriptions.value.some(
    (sub: any) => String(sub.tmdb_id) === String(route.params.id)
  )
})

// 从 backdrops 列表随机选一张，没有则回退到 backdrop_path
const randomBackdrop = computed(() => {
  if (detail.value?.backdrops?.length) {
    return detail.value.backdrops[Math.floor(Math.random() * detail.value.backdrops.length)].file_path
  }
  return detail.value?.backdrop_path || ''
})

// 季度/演员等图片：raw TMDB 路径需要加尺寸前缀，已代理的路径直接返回
function getPosterUrl(path: string, size: string = 'w300'): string {
  if (!path) return ''
  if (path.includes('/api/system/img')) return path
  const cleanPath = path.replace(/^\/(w\d+|original)\//, '/')
  return getImg(`/${size}${cleanPath.startsWith('/') ? cleanPath : '/' + cleanPath}`)
}

function formatMinutes(min: number): string {
  if (!min) return ''
  const h = Math.floor(min / 60)
  const m = min % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatFileSize(bytes: number): string {
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

// 季度入库状态
function getSeasonLibraryStatus(seasonNumber: number): any {
  return embyStatus.value?.seasons?.[seasonNumber] || null
}

// 每集 Emby 信息
function getEpisodeEmbyInfo(seasonNumber: number, episodeNumber: number): any {
  const key = String(seasonNumber)
  const embyData = seasonEmbyInfo.value.get(key)
  return embyData?.[episodeNumber] || null
}

async function fetchDetail(retryCount = 0) {
  const type = (route.params.type as string) || 'tv'
  const id = route.params.id as string
  if (!id) return

  loading.value = true
  error.value = null
  // 重置状态
  expandedSeasons.value = new Set()
  seasonEpisodes.value = new Map()
  seasonEmbyInfo.value = new Map()
  loadingSeasonEmby.value = new Set()
  embyStatus.value = null
  embyLoading.value = true

  const MAX_RETRIES = 3

  try {
    const [detailData, recData, subData] = await Promise.allSettled([
      tmdbApi.getDetail(type, id),
      tmdbApi.getRecommendations(type, id),
      subscriptionApi.getSubscriptions(),
    ])

    // 检查详情请求是否失败（网络错误）
    if (detailData.status === 'rejected') {
      const errMsg = String(detailData.reason)
      // 网络错误才重试
      if (retryCount < MAX_RETRIES - 1 && 
          (errMsg.includes('fetch') || errMsg.includes('network') || errMsg.includes('timeout'))) {
        console.log(`[TMDB Detail] 请求失败，${retryCount + 1}/${MAX_RETRIES} 秒后重试...`)
        await new Promise(r => setTimeout(r, 1000 * (retryCount + 1)))
        return fetchDetail(retryCount + 1)
      }
      throw detailData.reason
    }

    if (detailData.status === 'fulfilled') {
      detail.value = detailData.value
      // 后台异步获取 Emby 状态（不阻塞详情展示）
      embyLoading.value = true
      tmdbApi.getEmbyStatus(type, id).then(data => {
        embyStatus.value = data
      }).catch(() => {}).finally(() => {
        embyLoading.value = false
      })
    }

    if (recData.status === 'fulfilled') {
      const rec = recData.value
      recommendations.value = rec?.results || rec || []
    }

    if (subData.status === 'fulfilled') {
      subscriptions.value = subData.value || []
    }
  } catch (err: any) {
    error.value = err?.message || '加载详情失败，请检查网络连接'
    embyLoading.value = false
    console.error('[TMDB Detail] 加载失败:', err)
  } finally {
    loading.value = false
  }
}

const seasonErrors = ref<Map<string, string>>(new Map())

async function toggleSeason(seasonNumber: number, retryCount = 0) {
  const key = String(seasonNumber)
  if (expandedSeasons.value.has(seasonNumber)) {
    expandedSeasons.value.delete(seasonNumber)
    return
  }

  expandedSeasons.value.add(seasonNumber)
  seasonErrors.value.delete(key)

  if (!seasonEpisodes.value.has(key) && detail.value?.id) {
    loadingSeasons.value.add(key)
    const MAX_RETRIES = 3

    try {
      // 先拉取 TMDB 集信息（立即可展示，不等 Emby）
      let seasonData
      try {
        seasonData = await tmdbApi.getSeason(detail.value.id, seasonNumber)
      } catch (err: any) {
        const errMsg = String(err)
        if (retryCount < MAX_RETRIES - 1 &&
            (errMsg.includes('fetch') || errMsg.includes('network') || errMsg.includes('timeout'))) {
          console.log(`[Season ${seasonNumber}] 请求失败，${retryCount + 1}/${MAX_RETRIES} 秒后重试...`)
          await new Promise(r => setTimeout(r, 1000 * (retryCount + 1)))
          expandedSeasons.value.delete(seasonNumber)
          return toggleSeason(seasonNumber, retryCount + 1)
        }
        throw err
      }

      // TMDB 集信息就绪，立即展示
      seasonEpisodes.value.set(key, seasonData)

      // 异步拉取 Emby 入库信息（不阻塞集列表展示）
      loadingSeasonEmby.value.add(key)
      tmdbApi.getSeasonEmby(detail.value.id, seasonNumber)
        .then(data => {
          seasonEmbyInfo.value.set(key, data?.episodes || {})
        })
        .catch(() => {})
        .finally(() => {
          loadingSeasonEmby.value.delete(key)
        })

    } catch (err: any) {
      console.error(`[Season ${seasonNumber}] 加载失败:`, err)
      seasonErrors.value.set(key, err?.message || '加载季度信息失败')
      seasonEpisodes.value.set(key, { episodes: [] })
    } finally {
      loadingSeasons.value.delete(key)
    }
  }
}

function getSeasonError(seasonNumber: number): string | undefined {
  return seasonErrors.value.get(String(seasonNumber))
}

function getSeasonEpisodes(seasonNumber: number): any[] {
  const key = String(seasonNumber)
  return seasonEpisodes.value.get(key)?.episodes || []
}

function getSeasonInfo(seasonNumber: number): any {
  const key = String(seasonNumber)
  return seasonEpisodes.value.get(key)?.season_info || null
}

function handleSubscribe() {
  if (!detail.value) return
  navStore.navigateToSubscription({
    type: 'tmdb',
    tmdbId: detail.value.id,
    mediaType: (route.params.type as any) || 'tv',
    title: detail.value.title || detail.value.name,
    poster_path: detail.value.poster_path,
  })
}

function handleSearch() {
  if (!detail.value) return
  navStore.triggerGlobalSearch(
    detail.value.title || detail.value.name || detail.value.original_title || detail.value.original_name
  )
}

function openExternal() {
  const type = (route.params.type as string) === 'movie' ? 'movie' : 'tv'
  window.open(`https://www.themoviedb.org/${type}/${route.params.id}`, '_blank')
}

function openImdb(imdbId: string) {
  window.open(`https://www.imdb.com/title/${imdbId}`, '_blank')
}

function openRecommendation(item: any) {
  navStore.openTmdbDetail(item.id, item.media_type || (route.params.type as string) || 'tv')
}

function openPerson(personId: number) {
  navStore.openTmdbPersonDetail(personId)
}

watch(() => route.params.id, () => {
  if (route.params.id) {
    window.scrollTo(0, 0)
    fetchDetail()
  }
})

onMounted(() => {
  fetchDetail()
})
</script>

<template>
  <div class="tmdb-detail-view">
    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <v-skeleton-loader type="image" height="300" class="mb-4" />
      <v-container fluid class="pa-4 pa-md-6">
        <v-row>
          <v-col cols="12" sm="3" md="2">
            <v-skeleton-loader type="image" />
          </v-col>
          <v-col cols="12" sm="9" md="10">
            <v-skeleton-loader type="heading, paragraph, paragraph" />
          </v-col>
        </v-row>
      </v-container>
    </template>

    <!-- 详情内容 -->
    <template v-else-if="detail">
      <!-- 背景横幅 (从 backdrops 随机选一张) -->
      <div
        v-if="randomBackdrop"
        class="detail-backdrop"
        :style="{ backgroundImage: `url(${randomBackdrop})` }"
      >
        <div class="backdrop-overlay" />
      </div>

      <v-container fluid class="pa-4 pa-md-6 detail-content">
        <v-row>
          <!-- 海报 -->
          <v-col cols="12" sm="3" md="2">
            <v-img
              v-if="detail.poster_path"
              :src="getImg(detail.poster_path)"
              cover
              rounded="xl"
              aspect-ratio="2/3"
              class="elevation-4"
            />
          </v-col>

          <!-- 信息 -->
          <v-col cols="12" sm="9" md="10">
            <div class="d-flex align-center ga-2 flex-wrap">
              <h1 class="page-title text-h4 font-weight-bold">{{ detail.title || detail.name }}</h1>
              <v-chip v-if="embyStatus?.exists" size="small" color="success" variant="tonal">
                <v-icon start size="14">mdi-check-circle</v-icon>
                已入库
              </v-chip>
              <v-chip v-else-if="embyLoading" size="small" color="primary" variant="tonal">
                <v-progress-circular indeterminate size="12" width="2" class="mr-1" />
                查询中
              </v-chip>
              <v-chip v-else size="small" color="grey" variant="tonal">
                <v-icon start size="14">mdi-close-circle-outline</v-icon>
                未入库
              </v-chip>
            </div>
            <div v-if="detail.original_title || detail.original_name" class="page-subtitle text-body-1 mt-1">
              {{ detail.original_title || detail.original_name }}
            </div>
            <div v-if="detail.tagline" class="page-subtitle text-body-2 font-italic mt-1">
              "{{ detail.tagline }}"
            </div>

            <!-- 标签 -->
            <v-chip-group class="mt-3" column>
              <v-chip v-if="detail.vote_average" size="small" variant="tonal" color="warning">
                ⭐ {{ detail.vote_average?.toFixed(1) }}
                <span v-if="detail.vote_count" class="ml-1 text-caption">({{ detail.vote_count }})</span>
              </v-chip>
              <v-chip v-if="detail.release_date || detail.first_air_date" size="small" variant="tonal">
                <v-icon start size="14">mdi-calendar</v-icon>
                {{ detail.release_date || detail.first_air_date }}
              </v-chip>
              <v-chip v-if="detail.status" size="small" variant="tonal" color="info">
                {{ STATUS_MAP[detail.status] || detail.status }}
              </v-chip>
              <v-chip v-if="detail.number_of_seasons" size="small" variant="tonal" color="info">
                {{ detail.number_of_seasons }} 季
              </v-chip>
              <v-chip v-if="detail.number_of_episodes" size="small" variant="tonal" color="info">
                {{ detail.number_of_episodes }} 集
              </v-chip>
              <v-chip v-if="detail.runtime" size="small" variant="tonal">
                {{ formatMinutes(detail.runtime) }}
              </v-chip>
              <v-chip v-if="detail.original_language_zh" size="small" variant="tonal" color="primary">
                {{ detail.original_language_zh }}
              </v-chip>
              <v-chip v-if="detail.origin_country_zh?.length" size="small" variant="tonal" color="primary">
                {{ detail.origin_country_zh.join(' / ') }}
              </v-chip>
            </v-chip-group>

            <!-- 流派 -->
            <div v-if="detail.genres?.length" class="mt-2">
              <v-chip v-for="(g, i) in detail.genres" :key="i" size="small" variant="tonal" color="primary" class="mr-1 mb-1">
                {{ g }}
              </v-chip>
            </div>

            <!-- ID 信息 + 外部链接 -->
            <div class="mt-3 d-flex ga-2 flex-wrap align-center">
              <v-chip size="small" variant="tonal" color="info">
                <span class="cursor-pointer" @click="openExternal">TMDB ID: {{ detail.id }}</span>
              </v-chip>
              <v-chip v-if="detail.imdb_id" size="small" variant="tonal" color="info">
                <span class="cursor-pointer" @click="openImdb(detail.imdb_id)">IMDb ID: {{ detail.imdb_id }}</span>
              </v-chip>
            </div>

            <!-- 操作按钮 -->
            <div class="mt-4 d-flex ga-2 flex-wrap">
              <v-btn color="primary" variant="flat" prepend-icon="mdi-rss" @click="handleSubscribe">
                {{ isSubscribed ? '已订阅 · 编辑' : '快速订阅' }}
              </v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-magnify" @click="handleSearch">
                搜资源
              </v-btn>
            </div>

            <!-- 简介 -->
            <div v-if="detail.overview" class="mt-4">
              <div class="section-title text-subtitle-2 font-weight-medium mb-1">简介</div>
              <div class="page-subtitle text-body-2" style="line-height: 1.6">{{ detail.overview }}</div>
            </div>
          </v-col>
        </v-row>

        <!-- 演员阵容 -->
        <div v-if="detail.cast?.length" class="mt-8">
          <div class="section-title text-subtitle-1 font-weight-bold mb-3">演员阵容</div>
          <div class="cast-card-grid">
            <v-card
              v-for="c in detail.cast.slice(0, 20)"
              :key="c.id || c.actor"
              class="glass-card media-card cursor-pointer"
              variant="flat"
              @click="openPerson(c.id)"
            >
              <div class="media-card__poster">
                <v-img
                  v-if="c.image"
                  :src="c.image"
                  cover
                  class="rounded-t-xl"
                >
                  <template #placeholder>
                    <v-skeleton-loader type="image" />
                  </template>
                </v-img>
                <div v-else class="cast-card__placeholder">
                  <v-icon icon="mdi-account" size="36" />
                </div>
              </div>
              <div class="media-card__info">
                <div class="media-card__title">{{ c.actor }}</div>
                <div v-if="c.character" class="media-card__subtitle">{{ c.character }}</div>
              </div>
            </v-card>
          </div>
        </div>

        <!-- 季度列表 (TV) -->
        <div v-if="detail.seasons?.length" class="mt-8">
          <div class="section-title text-subtitle-1 font-weight-bold mb-3">季度信息</div>
          <v-expansion-panels variant="accordion" class="mb-4">
            <v-expansion-panel
              v-for="season in detail.seasons.filter((s: any) => s.season_number > 0)"
              :key="season.id"
            >
              <v-expansion-panel-title @click="toggleSeason(season.season_number)">
                <div class="d-flex align-center ga-3 w-100">
                  <v-avatar v-if="season.poster_path" rounded="lg" size="48">
                    <v-img :src="getPosterUrl(season.poster_path, 'w300')" cover />
                  </v-avatar>
                  <v-avatar v-else rounded="lg" size="48" color="surface-variant">
                    <v-icon icon="mdi-television-classic" />
                  </v-avatar>
                  <div class="flex-grow-1">
                    <div class="d-flex align-center ga-2">
                      <span class="font-weight-medium">{{ season.name }}</span>
                      <v-chip v-if="getSeasonLibraryStatus(season.season_number)?.exists" size="x-small" color="success" variant="tonal">
                        已入库
                      </v-chip>
                      <v-chip v-else-if="embyLoading" size="x-small" color="primary" variant="tonal">
                        查询中
                      </v-chip>
                      <v-chip v-else-if="embyStatus" size="x-small" color="grey" variant="tonal">
                        未入库
                      </v-chip>
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      {{ season.episode_count }} 集
                      <span v-if="season.air_date"> · {{ season.air_date }}</span>
                    </div>
                  </div>
                </div>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-if="loadingSeasons.has(String(season.season_number))" class="pa-4 text-center">
                  <v-progress-circular indeterminate size="24" color="primary" />
                </div>
                <!-- 季度加载错误 -->
                <div v-else-if="getSeasonError(season.season_number)" class="pa-4 text-center">
                  <v-icon size="32" color="error" class="mb-2">mdi-alert-circle-outline</v-icon>
                  <div class="text-body-2 text-medium-emphasis mb-2">{{ getSeasonError(season.season_number) }}</div>
                  <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-refresh" @click.stop="toggleSeason(season.season_number)">
                    重新加载
                  </v-btn>
                </div>
                <template v-else>
                  <!-- 季度简介 -->
                  <div v-if="getSeasonInfo(season.season_number)?.overview" class="ep-season-overview mb-3">
                    {{ getSeasonInfo(season.season_number).overview }}
                  </div>

                  <!-- Emby 入库状态查询中提示 -->
                  <div v-if="loadingSeasonEmby.has(String(season.season_number))" class="d-flex align-center ga-2 mb-2 pa-2 emby-loading-hint">
                    <v-progress-circular indeterminate size="14" width="2" color="primary" />
                    <span class="text-caption text-medium-emphasis">正在查询 Emby 入库状态...</span>
                  </div>

                  <!-- 集列表 -->
                  <div v-if="getSeasonEpisodes(season.season_number).length" class="d-flex flex-column ga-2">
                    <v-card
                      v-for="ep in getSeasonEpisodes(season.season_number)"
                      :key="ep.episode"
                      variant="tonal"
                      rounded="lg"
                    >
                      <v-row no-gutters>
                        <!-- 缩略图：移动端 cols=12 全宽上图，桌面端 sm=4 左侧图 -->
                        <v-col cols="12" sm="4" md="3">
                          <v-img
                            v-if="ep.still_path"
                            :src="getPosterUrl(ep.still_path, 'w300')"
                            cover
                            :class="$vuetify.display.smAndUp ? 'rounded-l-lg' : 'rounded-t-lg'"
                            aspect-ratio="16/9"
                          />
                          <div v-else class="d-flex align-center justify-center bg-surface-variant" style="aspect-ratio:16/9" :class="$vuetify.display.smAndUp ? 'rounded-l-lg' : 'rounded-t-lg'">
                            <span class="text-h6 font-weight-bold text-medium-emphasis">E{{ ep.episode }}</span>
                          </div>
                        </v-col>

                        <!-- 信息 -->
                        <v-col cols="12" sm="8" md="9">
                          <div class="pa-3 d-flex flex-column ga-1">
                            <div class="d-flex align-center ga-2 flex-wrap">
                              <v-chip size="x-small" color="primary" variant="tonal" label>E{{ ep.episode }}</v-chip>
                              <span class="font-weight-medium text-truncate">{{ ep.name || '未命名' }}</span>
                              <v-chip v-if="ep.episode_type === 'finale'" size="x-small" color="error" variant="tonal">本季大结局</v-chip>
                              <v-chip v-else-if="ep.episode_type === 'mid_season'" size="x-small" color="warning" variant="tonal">季中结局</v-chip>
                              <v-chip v-if="getEpisodeEmbyInfo(season.season_number, ep.episode)?.exists" size="x-small" color="success" variant="tonal">
                                <v-icon start size="12">mdi-check-circle</v-icon>
                                已入库
                              </v-chip>
                              <v-chip v-else-if="!loadingSeasonEmby.has(String(season.season_number)) && seasonEmbyInfo.has(String(season.season_number))" size="x-small" color="grey" variant="tonal">
                                未入库
                              </v-chip>
                            </div>

                            <div class="d-flex ga-3 text-caption">
                              <span v-if="ep.vote_average" class="d-flex align-center ga-1">
                                <v-icon size="12" color="warning">mdi-star</v-icon>
                                {{ ep.vote_average.toFixed(1) }}
                              </span>
                              <span v-if="ep.runtime">{{ ep.runtime }}分钟</span>
                              <span v-if="ep.air_date">{{ ep.air_date }}</span>
                            </div>

                            <div v-if="ep.overview" class="text-body-2 text-medium-emphasis ep-overview">{{ ep.overview }}</div>

                            <!-- Emby 文件列表 -->
                            <div v-if="getEpisodeEmbyInfo(season.season_number, ep.episode)?.files?.length" class="ep-files">
                              <div v-for="(file, idx) in getEpisodeEmbyInfo(season.season_number, ep.episode).files" :key="idx" class="text-caption d-flex align-center">
                                <v-icon size="12" class="mr-1">mdi-file</v-icon>
                                <span class="text-medium-emphasis text-truncate">{{ file.name }}</span>
                                <span v-if="file.size" class="text-disabled ml-1">· {{ formatFileSize(file.size) }}</span>
                              </div>
                            </div>
                          </div>
                        </v-col>
                      </v-row>
                    </v-card>
                  </div>
                  <div v-else class="text-body-2 text-medium-emphasis pa-2">暂无集信息</div>
                </template>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>

        <!-- 推荐内容 -->
        <div v-if="recommendations.length > 0" class="mt-8">
          <div class="section-title text-subtitle-1 font-weight-bold mb-3">推荐内容</div>
          <div class="media-card-grid">
            <v-card v-for="item in recommendations.slice(0, 12)" :key="item.id" class="glass-card media-card cursor-pointer" @click="openRecommendation(item)">
              <div class="media-card__poster">
                <v-img
                  v-if="item.poster_path"
                  :src="getImg(item.poster_path)"
                  cover
                  class="rounded-t-xl"
                >
                  <template #placeholder>
                    <v-skeleton-loader type="image" />
                  </template>
                </v-img>
                <span class="media-card__type" :class="item.media_type === 'movie' ? 'media-card__type--tmdb-movie' : 'media-card__type--tmdb-tv'">
                  {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                </span>
                <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
              </div>
              <div class="media-card__info">
                <div class="media-card__title">{{ item.title || item.name }}</div>
                <div class="media-card__year">{{ (item.release_date || item.first_air_date || '').slice(0, 4) }}</div>
              </div>
            </v-card>
          </div>
        </div>
      </v-container>
    </template>

    <!-- 错误状态 -->
    <div v-else-if="error" class="text-center pa-8">
      <v-icon size="64" color="error" class="mb-4">mdi-alert-circle-outline</v-icon>
      <div class="text-h6 mb-2">加载失败</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ error }}</div>
      <v-btn color="primary" prepend-icon="mdi-refresh" @click="fetchDetail()">
        重新加载
      </v-btn>
    </div>

    <!-- 空状态 -->
    <div v-else class="text-center pa-8">
      <v-icon size="64" color="grey" class="mb-4">mdi-movie-off</v-icon>
      <div class="text-h6">暂无数据</div>
    </div>

  </div>
</template>

<style scoped>
/* ── 季度简介 ── */
.ep-season-overview {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.7);
  line-height: 1.6;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid rgb(var(--v-theme-primary));
}

/* ── 集简介：限制行数 ── */
.ep-overview {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

/* ── Emby 文件列表 ── */
.ep-files {
  border-radius: 6px;
  padding: 6px 8px;
}

/* ── Emby 查询中提示 ── */
.emby-loading-hint {
  border-radius: 8px;
}

/* 详情页 chip 文字使用默认色（白天黑/夜晚白），不使用 primary 蓝色 */
:deep(.v-chip--variant-tonal.text-primary) {
  color: rgba(var(--v-theme-on-surface), 0.88) !important;
}
:deep(.v-chip--variant-tonal.text-primary .v-chip__underlay) {
  background-color: rgba(var(--v-theme-on-surface), 0.08) !important;
}
</style>
