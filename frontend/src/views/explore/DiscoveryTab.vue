<script setup lang="ts">
/**
 * DiscoveryTab — 探索索引
 *
 * 对标旧前端 DiscoveryTabDesktop:
 * - 数据源切换 (TMDB / Bangumi)
 * - TMDB: 类型 / 语言 / 流派 / 年份 / 排序
 * - Bangumi: 分类 / 地区 / 来源 / 受众 / 标签 / 年份 / 排序
 * - 无限滚动加载
 * - 已订阅状态标记
 */
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { exploreApi, subscriptionApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'DiscoveryTab' })

const { error: showError } = useNotification()
const navStore = useNavigationStore()

// --- 配置 ---
const config = reactive({
  genres: [] as any[],
  years: [] as string[],
  languages: [] as any[],
  sort_options: [] as any[],
  bangumi_types: [] as any[],
  bangumi_sources: [] as any[],
  bangumi_regions: [] as any[],
  bangumi_audiences: [] as any[],
})

// --- 筛选器 ---
const filters = reactive({
  source: 'bangumi' as 'tmdb' | 'bangumi',
  media_type: 'tv' as 'movie' | 'tv',
  genre: null as string | null,
  year: null as string | null,
  language: null as string | null,
  sort_by: 'popularity.desc',
  page: 1,
  subtype: null as string | null,
  story_source: null as string | null,
  region: null as string | null,
  audience: null as string | null,
})

// --- 数据 ---
const items = ref<any[]>([])
const loading = ref(false)
const hasMore = ref(true)
const subscriptions = ref<any[]>([])

// --- 无限滚动 ---
const loadTrigger = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

async function loadConfig() {
  try {
    const data = await exploreApi.getConfig(filters.source)
    config.genres = data?.genres || []
    config.years = data?.years || []
    config.languages = data?.languages || []
    config.sort_options = data?.sort_options || []
    config.bangumi_types = data?.bangumi_types || []
    config.bangumi_sources = data?.bangumi_sources || []
    config.bangumi_regions = data?.bangumi_regions || []
    config.bangumi_audiences = data?.bangumi_audiences || []
    // 如果当前排序方式不在可选列表中，重置为默认
    if (!config.sort_options.some((o: any) => o.value === filters.sort_by)) {
      filters.sort_by = config.sort_options[0]?.value || 'popularity.desc'
    }
  } catch { /* */ }
}

async function fetchSubscriptions() {
  try {
    subscriptions.value = (await subscriptionApi.getSubscriptions()) || []
  } catch { /* */ }
}

function isSubscribed(item: any) {
  if (filters.source === 'bangumi') {
    return subscriptions.value.some((s: any) => s.bangumi_id && String(s.bangumi_id) === String(item.id))
  }
  return subscriptions.value.some((s: any) => String(s.tmdb_id) === String(item.id))
}

async function fetchData(mode: 'replace' | 'append' = 'replace') {
  if (loading.value) return
  if (mode === 'append' && !hasMore.value) return

  loading.value = true
  try {
    const params: Record<string, any> = {
      source: filters.source,
      media_type: filters.media_type,
      sort_by: filters.sort_by,
      page: filters.page,
    }
    if (filters.genre) params.with_genres = filters.genre
    if (filters.year) params.year = filters.year
    if (filters.language) params.language = filters.language
    if (filters.subtype) params.subtype = filters.subtype
    if (filters.story_source) params.story_source = filters.story_source
    if (filters.region) params.region = filters.region
    if (filters.audience) params.audience = filters.audience

    const data = await exploreApi.getList(params)
    const newItems = data?.results || []

    if (mode === 'replace') {
      items.value = newItems
    } else {
      const existingIds = new Set(items.value.map(i => i.id))
      for (const item of newItems) {
        if (!existingIds.has(item.id)) items.value.push(item)
      }
    }

    const totalPages = Math.min(data?.total_pages || 0, 500)
    hasMore.value = filters.page < totalPages
  } catch (e) {
    showError('加载探索数据失败')
  } finally {
    loading.value = false
  }
}

function resetAndReload() {
  filters.page = 1
  hasMore.value = true
  fetchData('replace')
}

function openDetail(item: any) {
  if (filters.source === 'bangumi') {
    navStore.openBangumiDetail(item.id)
  } else {
    navStore.openTmdbDetail(item.id, item.media_type || filters.media_type)
  }
}

function getPoster(item: any): string {
  const path = filters.source === 'bangumi' ? (item.image || item.poster_path) : item.poster_path
  if (!path) return ''
  return getImg(path)
}

// --- 筛选器变化监听 ---
watch(() => filters.source, async () => {
  filters.genre = null
  filters.language = null
  filters.year = null
  filters.subtype = null
  filters.story_source = null
  filters.region = null
  filters.audience = null
  await loadConfig()
  resetAndReload()
})
watch(() => filters.media_type, resetAndReload)
watch(() => filters.genre, resetAndReload)
watch(() => filters.year, resetAndReload)
watch(() => filters.language, resetAndReload)
watch(() => filters.subtype, resetAndReload)
watch(() => filters.story_source, resetAndReload)
watch(() => filters.region, resetAndReload)
watch(() => filters.audience, resetAndReload)
watch(() => filters.sort_by, resetAndReload)

function setupObserver() {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      filters.page++
      fetchData('append')
    }
  }, { root: null, rootMargin: '200px', threshold: 0.1 })
  if (loadTrigger.value) observer.observe(loadTrigger.value)
}

onMounted(async () => {
  await loadConfig()
  await fetchSubscriptions()
  await fetchData('replace')
  nextTick(() => setupObserver())
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="discovery-tab pa-4">
    <!-- 筛选栏 -->
    <div class="filter-bar mb-6 pa-4 rounded-lg" style="background: rgba(var(--v-theme-on-surface), 0.03); border: 1px solid rgba(var(--v-theme-on-surface), 0.06);">
      <!-- 数据源 -->
      <div class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">数据源</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.source === 'tmdb' ? 'primary' : undefined" :variant="filters.source === 'tmdb' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.source = 'tmdb'">TMDB (全球)</v-chip>
          <v-chip :color="filters.source === 'bangumi' ? 'primary' : undefined" :variant="filters.source === 'bangumi' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.source = 'bangumi'">Bangumi (番剧)</v-chip>
        </div>
      </div>

      <!-- TMDB 类型 -->
      <div v-if="filters.source === 'tmdb'" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">类型</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.media_type === 'tv' ? 'primary' : undefined" :variant="filters.media_type === 'tv' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.media_type = 'tv'">剧集 (TV)</v-chip>
          <v-chip :color="filters.media_type === 'movie' ? 'primary' : undefined" :variant="filters.media_type === 'movie' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.media_type = 'movie'">剧场版 (Movie)</v-chip>
        </div>
      </div>

      <!-- Bangumi 分类 -->
      <div v-if="filters.source === 'bangumi' && config.bangumi_types.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">分类</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.subtype === null ? 'primary' : undefined" :variant="filters.subtype === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.subtype = null">全部</v-chip>
          <v-chip v-for="t in config.bangumi_types" :key="t.id" :color="filters.subtype === t.id ? 'primary' : undefined" :variant="filters.subtype === t.id ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.subtype = t.id">{{ t.name }}</v-chip>
        </div>
      </div>

      <!-- TMDB 语言 -->
      <div v-if="filters.source === 'tmdb' && config.languages.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">语言</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.language === null ? 'primary' : undefined" :variant="filters.language === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.language = null">全部</v-chip>
          <v-chip v-for="l in config.languages" :key="l.value" :color="filters.language === l.value ? 'primary' : undefined" :variant="filters.language === l.value ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.language = l.value">{{ l.label }}</v-chip>
        </div>
      </div>

      <!-- Bangumi 地区 -->
      <div v-if="filters.source === 'bangumi' && config.bangumi_regions.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">地区</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.region === null ? 'primary' : undefined" :variant="filters.region === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.region = null">全部</v-chip>
          <v-chip v-for="r in config.bangumi_regions" :key="r.id" :color="filters.region === r.id ? 'primary' : undefined" :variant="filters.region === r.id ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.region = r.id">{{ r.name }}</v-chip>
        </div>
      </div>

      <!-- Bangumi 来源 -->
      <div v-if="filters.source === 'bangumi' && config.bangumi_sources.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">来源</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.story_source === null ? 'primary' : undefined" :variant="filters.story_source === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.story_source = null">全部</v-chip>
          <v-chip v-for="s in config.bangumi_sources" :key="s.id" :color="filters.story_source === s.id ? 'primary' : undefined" :variant="filters.story_source === s.id ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.story_source = s.id">{{ s.name }}</v-chip>
        </div>
      </div>

      <!-- Bangumi 受众 -->
      <div v-if="filters.source === 'bangumi' && config.bangumi_audiences.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">受众</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.audience === null ? 'primary' : undefined" :variant="filters.audience === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.audience = null">全部</v-chip>
          <v-chip v-for="a in config.bangumi_audiences" :key="a.id" :color="filters.audience === a.id ? 'primary' : undefined" :variant="filters.audience === a.id ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.audience = a.id">{{ a.name }}</v-chip>
        </div>
      </div>

      <!-- 标签/流派 -->
      <div v-if="config.genres.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">{{ filters.source === 'bangumi' ? '标签' : '流派' }}</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.genre === null ? 'primary' : undefined" :variant="filters.genre === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.genre = null">全部</v-chip>
          <v-chip v-for="g in config.genres" :key="g.id" :color="filters.genre === String(g.id) ? 'primary' : undefined" :variant="filters.genre === String(g.id) ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.genre = String(g.id)">{{ g.name }}</v-chip>
        </div>
      </div>

      <!-- 年份 -->
      <div v-if="config.years.length > 0" class="filter-row d-flex align-center mb-3">
        <div class="filter-label text-caption font-weight-bold text-medium-emphasis mr-3" style="width: 48px; flex-shrink: 0;">年份</div>
        <div class="d-flex ga-1 flex-wrap">
          <v-chip :color="filters.year === null ? 'primary' : undefined" :variant="filters.year === null ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.year = null">全部</v-chip>
          <v-chip v-for="y in config.years" :key="y" :color="filters.year === y ? 'primary' : undefined" :variant="filters.year === y ? 'flat' : 'outlined'" size="small" label class="cursor-pointer" @click="filters.year = y">{{ y }}</v-chip>
        </div>
      </div>

      <!-- 排序 + 结果数 -->
      <div class="d-flex align-center justify-space-between mt-4 pt-3" style="border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);">
        <v-select
          v-model="filters.sort_by"
          label="排序方式"
          :items="config.sort_options.map((o: any) => ({ title: o.label, value: o.value }))"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 280px"
        />
        <v-chip size="small" variant="tonal" color="primary">共 {{ items.length }} 条结果</v-chip>
      </div>
    </div>

    <!-- 加载骨架屏 -->
    <template v-if="loading && items.length === 0">
      <div class="media-card-grid">
        <v-skeleton-loader v-for="i in 12" :key="i" type="card" />
      </div>
    </template>

    <!-- 卡片网格 -->
    <template v-else>
      <div class="media-card-grid">
        <v-card v-for="item in items" :key="item.id" class="glass-card media-card cursor-pointer" @click="openDetail(item)">
          <div class="media-card__poster">
            <v-img
              v-if="getPoster(item)"
              :src="getPoster(item)"
              cover
              class="rounded-t-xl"
            >
              <template #placeholder>
                <v-skeleton-loader type="image" />
              </template>
            </v-img>
            <!-- 左上角类型标识 -->
            <span v-if="filters.source === 'bangumi' ? item.platform : true" class="media-card__type" :class="filters.source === 'bangumi' ? 'media-card__type--bgm' : filters.media_type === 'movie' ? 'media-card__type--tmdb-movie' : 'media-card__type--tmdb-tv'">
              {{ filters.source === 'bangumi' ? item.platform : filters.media_type === 'movie' ? '电影' : '剧集' }}
            </span>
            <!-- 右上角评分 -->
            <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
            <!-- 已订阅角标 -->
            <div v-if="isSubscribed(item)" class="media-card__sub-badge">
              <v-icon size="14" color="white">mdi-check-circle</v-icon>
            </div>
          </div>
          <div class="media-card__info">
            <div class="media-card__title">{{ item.title || item.name }}</div>
            <div class="media-card__year">{{ (item.release_date || item.first_air_date || item.air_date || '').slice(0, 4) }}</div>
          </div>
        </v-card>
      </div>

      <!-- 无限滚动触发器 -->
      <div ref="loadTrigger" class="text-center pa-4">
        <v-progress-circular v-if="loading && items.length > 0" indeterminate size="24" color="primary" />
        <span v-else-if="!hasMore && items.length > 0" class="text-caption text-medium-emphasis">已经到底啦 ~</span>
      </div>

      <!-- 空状态 -->
      <div v-if="items.length === 0 && !loading" class="text-center pa-8">
        <v-icon size="48" color="primary" class="mb-3">mdi-compass-off-outline</v-icon>
        <div class="text-body-1">什么都没找到...</div>
      </div>
    </template>
  </div>
</template>


