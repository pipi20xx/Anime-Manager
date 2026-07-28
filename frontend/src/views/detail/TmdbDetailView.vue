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
const recommendations = ref<any[]>([])
const subscriptions = ref<any[]>([])
const embyStatus = ref<any>(null)

// 季度展开状态
const expandedSeasons = ref<Set<number>>(new Set())
const seasonEpisodes = ref<Map<string, any>>(new Map())
const seasonEmbyInfo = ref<Map<string, any>>(new Map())
const loadingSeasons = ref<Set<string>>(new Set())

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

const isInLibrary = computed(() => embyStatus.value?.exists || false)

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

async function fetchDetail() {
  const type = (route.params.type as string) || 'tv'
  const id = route.params.id as string
  if (!id) return

  loading.value = true
  // 重置状态
  expandedSeasons.value = new Set()
  seasonEpisodes.value = new Map()
  seasonEmbyInfo.value = new Map()
  embyStatus.value = null

  try {
    const [detailData, recData, subData] = await Promise.allSettled([
      tmdbApi.getDetail(type, id),
      tmdbApi.getRecommendations(type, id),
      subscriptionApi.getSubscriptions(),
    ])

    if (detailData.status === 'fulfilled') {
      detail.value = detailData.value
      // 后台异步获取 Emby 状态（不阻塞详情展示）
      tmdbApi.getEmbyStatus(type, id).then(data => {
        embyStatus.value = data
      }).catch(() => {})
    }

    if (recData.status === 'fulfilled') {
      const rec = recData.value
      recommendations.value = rec?.results || rec || []
    }

    if (subData.status === 'fulfilled') {
      subscriptions.value = subData.value || []
    }
  } catch {
    showError('加载详情失败')
  } finally {
    loading.value = false
  }
}

async function toggleSeason(seasonNumber: number) {
  const key = String(seasonNumber)
  if (expandedSeasons.value.has(seasonNumber)) {
    expandedSeasons.value.delete(seasonNumber)
    return
  }

  expandedSeasons.value.add(seasonNumber)

  if (!seasonEpisodes.value.has(key) && detail.value?.id) {
    loadingSeasons.value.add(key)
    try {
      // 同时拉取 TMDB 集信息 + Emby 入库信息
      const [seasonData, embyData] = await Promise.allSettled([
        tmdbApi.getSeason(detail.value.id, seasonNumber),
        tmdbApi.getSeasonEmby(detail.value.id, seasonNumber),
      ])

      if (seasonData.status === 'fulfilled') {
        seasonEpisodes.value.set(key, seasonData.value)
      }

      if (embyData.status === 'fulfilled') {
        seasonEmbyInfo.value.set(key, embyData.value?.episodes || {})
      }
    } catch {
      seasonEpisodes.value.set(key, { episodes: [] })
    } finally {
      loadingSeasons.value.delete(key)
    }
  }
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
    detail.value.original_title || detail.value.original_name || detail.value.title || detail.value.name
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
  if (route.params.id) fetchDetail()
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
              <div class="text-h4 font-weight-bold">{{ detail.title || detail.name }}</div>
              <v-chip v-if="isInLibrary" size="small" color="success" variant="tonal">
                <v-icon start size="14">mdi-check-circle</v-icon>
                已入库
              </v-chip>
            </div>
            <div v-if="detail.original_title || detail.original_name" class="text-body-1 text-medium-emphasis mt-1">
              {{ detail.original_title || detail.original_name }}
            </div>
            <div v-if="detail.tagline" class="text-body-2 font-italic mt-1" style="opacity: 0.7">
              "{{ detail.tagline }}"
            </div>

            <!-- 标签 -->
            <v-chip-group class="mt-3">
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
              <v-chip v-if="detail.original_language_zh" size="small" variant="outlined">
                {{ detail.original_language_zh }}
              </v-chip>
              <v-chip v-if="detail.origin_country_zh?.length" size="small" variant="outlined">
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
            <div class="mt-3 d-flex ga-4 flex-wrap align-center text-caption">
              <span><span class="text-medium-emphasis">TMDB ID:</span> <span class="font-weight-medium cursor-pointer" style="color: rgb(var(--v-theme-primary))" @click="openExternal">{{ detail.id }}</span></span>
              <span v-if="detail.imdb_id"><span class="text-medium-emphasis">IMDb ID:</span> <span class="font-weight-medium cursor-pointer" style="color: rgb(var(--v-theme-primary))" @click="openImdb(detail.imdb_id)">{{ detail.imdb_id }}</span></span>
            </div>

            <!-- 操作按钮 -->
            <div class="mt-4 d-flex ga-2 flex-wrap">
              <v-btn color="primary" variant="flat" prepend-icon="mdi-rss" @click="handleSubscribe">
                {{ isSubscribed ? '已订阅 · 编辑' : '快速订阅' }}
              </v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-magnify" @click="handleSearch">
                搜资源
              </v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-open-in-new" @click="openExternal">
                TMDB
              </v-btn>
              <v-btn v-if="detail.imdb_id" variant="tonal" prepend-icon="mdi-open-in-new" @click="openImdb(detail.imdb_id)">
                IMDb
              </v-btn>
            </div>

            <!-- 简介 -->
            <div v-if="detail.overview" class="mt-4">
              <div class="text-subtitle-2 font-weight-medium mb-1">简介</div>
              <div class="text-body-2" style="line-height: 1.6">{{ detail.overview }}</div>
            </div>
          </v-col>
        </v-row>

        <!-- 演员阵容 -->
        <div v-if="detail.cast?.length" class="mt-8">
          <div class="text-subtitle-1 font-weight-bold mb-3">演员阵容</div>
          <div class="cast-scroll d-flex ga-3 overflow-x-auto pb-2">
            <div
              v-for="c in detail.cast.slice(0, 20)"
              :key="c.id || c.actor"
              class="cast-card flex-shrink-0 cursor-pointer"
              @click="openPerson(c.id)"
            >
              <v-avatar size="64" rounded="lg" class="mb-2">
                <v-img
                  v-if="c.image"
                  :src="c.image"
                  cover
                />
                <v-icon v-else icon="mdi-account" size="32" color="grey" />
              </v-avatar>
              <div class="text-body-2 font-weight-medium text-center text-truncate" style="max-width: 80px">
                {{ c.actor }}
              </div>
              <div v-if="c.character" class="text-caption text-medium-emphasis text-center text-truncate" style="max-width: 80px">
                {{ c.character }}
              </div>
            </div>
          </div>
        </div>

        <!-- 季度列表 (TV) -->
        <div v-if="detail.seasons?.length" class="mt-8">
          <div class="text-subtitle-1 font-weight-bold mb-3">季度信息</div>
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
                <template v-else>
                  <!-- 季度简介 -->
                  <div v-if="getSeasonInfo(season.season_number)?.overview" class="ep-season-overview mb-3">
                    {{ getSeasonInfo(season.season_number).overview }}
                  </div>

                  <!-- 集列表 -->
                  <div v-if="getSeasonEpisodes(season.season_number).length" class="ep-list">
                    <div
                      v-for="ep in getSeasonEpisodes(season.season_number)"
                      :key="ep.episode"
                      class="ep-item"
                    >
                      <!-- 缩略图 -->
                      <div class="ep-item__still">
                        <v-img
                          v-if="ep.still_path"
                          :src="getPosterUrl(ep.still_path, 'w300')"
                          cover
                          class="rounded"
                        />
                        <div v-else class="ep-item__still-placeholder">
                          <span>E{{ ep.episode }}</span>
                        </div>
                      </div>

                      <!-- 内容 -->
                      <div class="ep-item__content">
                        <div class="ep-item__header">
                          <div class="d-flex align-center ga-2 flex-wrap">
                            <span class="ep-item__num">E{{ ep.episode }}</span>
                            <span class="ep-item__name">{{ ep.name || '未命名' }}</span>
                            <v-chip v-if="ep.episode_type === 'finale'" size="x-small" color="error" variant="tonal">本季大结局</v-chip>
                            <v-chip v-else-if="ep.episode_type === 'mid_season'" size="x-small" color="warning" variant="tonal">季中结局</v-chip>
                            <v-chip v-if="getEpisodeEmbyInfo(season.season_number, ep.episode)?.exists" size="x-small" color="success" variant="tonal">
                              <v-icon start size="12">mdi-check-circle</v-icon>
                              已入库
                            </v-chip>
                          </div>
                          <div class="d-flex ga-3 text-caption text-medium-emphasis">
                            <span v-if="ep.vote_average" class="d-flex align-center ga-1">
                              <v-icon size="12" color="warning">mdi-star</v-icon>
                              {{ ep.vote_average.toFixed(1) }}
                            </span>
                            <span v-if="ep.runtime">{{ ep.runtime }}分钟</span>
                            <span v-if="ep.air_date">{{ ep.air_date }}</span>
                          </div>
                        </div>
                        <div v-if="ep.overview" class="ep-item__overview">{{ ep.overview }}</div>
                        <!-- Emby 文件列表 -->
                        <div v-if="getEpisodeEmbyInfo(season.season_number, ep.episode)?.files?.length" class="ep-item__files">
                          <div v-for="(file, idx) in getEpisodeEmbyInfo(season.season_number, ep.episode).files" :key="idx" class="ep-file">
                            <v-icon size="12" class="mr-1">mdi-file</v-icon>
                            <span class="ep-file__name">{{ file.name }}</span>
                            <span v-if="file.size" class="ep-file__size"> · {{ formatFileSize(file.size) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else class="text-body-2 text-medium-emphasis pa-2">暂无集信息</div>
                </template>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>

        <!-- 推荐内容 -->
        <div v-if="recommendations.length > 0" class="mt-8">
          <div class="text-subtitle-1 font-weight-bold mb-3">推荐内容</div>
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

    <!-- 空状态 -->
    <div v-else class="text-center pa-8">
      <v-icon size="64" color="error" class="mb-4">mdi-alert-circle-outline</v-icon>
      <div class="text-h6">加载失败</div>
    </div>

  </div>
</template>

<style scoped>
/* ── 季度简介 ── */
.ep-season-overview {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  line-height: 1.6;
  padding: 10px 12px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-radius: 8px;
  border-left: 3px solid rgb(var(--v-theme-primary));
}

/* ── 集列表 ── */
.ep-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ep-item {
  display: flex;
  gap: 12px;
  padding: 10px;
  border-radius: 8px;
  transition: background 0.15s ease;
}
.ep-item:hover {
  background: rgba(var(--v-theme-on-surface), 0.03);
}

/* 缩略图 */
.ep-item__still {
  width: 160px;
  min-width: 160px;
  aspect-ratio: 16 / 9;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.06);
  flex-shrink: 0;
}
.ep-item__still-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: rgba(var(--v-theme-on-surface), 0.3);
  background: rgba(var(--v-theme-on-surface), 0.04);
}

/* 内容区 */
.ep-item__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ep-item__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.ep-item__num {
  font-size: 11px;
  font-weight: 700;
  color: rgb(var(--v-theme-primary));
  padding: 2px 6px;
  background: rgba(var(--v-theme-primary), 0.1);
  border-radius: 4px;
  flex-shrink: 0;
}
.ep-item__name {
  font-size: 13px;
  font-weight: 600;
}
.ep-item__overview {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  line-height: 1.5;
}

/* Emby 文件列表 */
.ep-item__files {
  margin-top: 4px;
  padding: 6px 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-radius: 4px;
}
.ep-file {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-bottom: 2px;
}
.ep-file:last-child {
  margin-bottom: 0;
}
.ep-file__name {
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.ep-file__size {
  color: rgba(var(--v-theme-on-surface), 0.4);
}
</style>
