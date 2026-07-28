<script setup lang="ts">
/**
 * SearchTab — 聚合搜索
 *
 * 对标旧前端 SearchTabDesktop:
 * - 不区分 BGM / TMDB，一个搜索框同时搜索三个源
 * - 结果分组展示: Bangumi (番剧) / TMDB (电影) / TMDB (剧集)
 * - 已订阅状态标记
 * - 记忆搜索关键词
 */
import { ref, onMounted } from 'vue'
import { exploreApi, subscriptionApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'SearchTab' })

const { error: showError } = useNotification()
const navStore = useNavigationStore()

const keyword = ref('')
const loading = ref(false)
const hasSearched = ref(false)
const subscriptions = ref<any[]>([])

const results = ref<{
  bangumi: any[]
  tmdb_movie: any[]
  tmdb_tv: any[]
}>({
  bangumi: [],
  tmdb_movie: [],
  tmdb_tv: [],
})

async function fetchSubscriptions() {
  try {
    subscriptions.value = (await subscriptionApi.getSubscriptions()) || []
  } catch { /* */ }
}

function isSubscribed(item: any, source: 'tmdb' | 'bangumi' = 'tmdb') {
  if (source === 'bangumi') {
    return subscriptions.value.some((s: any) => s.bangumi_id && String(s.bangumi_id) === String(item.id))
  }
  return subscriptions.value.some((s: any) => String(s.tmdb_id) === String(item.id))
}

async function doSearch() {
  if (!keyword.value.trim()) return
  if (loading.value) return

  loading.value = true
  hasSearched.value = true
  results.value = { bangumi: [], tmdb_movie: [], tmdb_tv: [] }

  // 记忆搜索关键词
  if (keyword.value) {
    localStorage.setItem('apm_explore_last_keyword', keyword.value)
  }

  try {
    await fetchSubscriptions()
    const data = await exploreApi.search(keyword.value)
    results.value = {
      bangumi: data?.bangumi || [],
      tmdb_movie: data?.tmdb_movie || [],
      tmdb_tv: data?.tmdb_tv || [],
    }
  } catch (e) {
    showError('搜索失败')
  } finally {
    loading.value = false
  }
}

function openTmdb(item: any, type: string) {
  navStore.openTmdbDetail(item.id, type)
}

function openBangumi(item: any) {
  navStore.openBangumiDetail(item.id)
}

function getTmdbPoster(item: any): string {
  if (!item.poster_path) return ''
  return getImg(item.poster_path)
}

function getBgmPoster(item: any): string {
  if (!item.image && !item.poster_path) return ''
  return getImg(item.image || item.poster_path)
}

onMounted(() => {
  // 恢复上次搜索状态
  const lastKeyword = localStorage.getItem('apm_explore_last_keyword')
  if (lastKeyword) {
    keyword.value = lastKeyword
    doSearch()
  } else if (navStore.searchKeyword) {
    keyword.value = navStore.searchKeyword
    doSearch()
  }
})
</script>

<template>
  <div class="search-tab pa-4">
    <!-- 搜索栏 -->
    <div class="d-flex ga-2 mb-6 justify-center">
      <v-text-field
        v-model="keyword"
        placeholder="输入名称搜索 TMDB 和 Bangumi..."
        prepend-inner-icon="mdi-magnify"
        variant="outlined"
        density="comfortable"
        hide-details
        clearable
        style="max-width: 600px"
        class="flex-grow-1"
        @keydown.enter="doSearch()"
      >
        <template #append-inner>
          <v-btn color="primary" variant="flat" size="small" :loading="loading" @click="doSearch()">
            搜索
          </v-btn>
        </template>
      </v-text-field>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="text-center pa-12">
      <v-progress-circular indeterminate size="48" color="primary" />
      <div class="text-body-2 text-medium-emphasis mt-4">正在搜索 TMDB 和 Bangumi...</div>
    </div>

    <!-- 搜索结果 -->
    <div v-else-if="hasSearched">
      <!-- 无结果 -->
      <div v-if="!results.bangumi.length && !results.tmdb_movie.length && !results.tmdb_tv.length" class="text-center pa-12">
        <v-icon size="64" color="primary" class="mb-4">mdi-magnify-close</v-icon>
        <div class="text-h6">未找到相关结果</div>
        <div class="text-body-2 text-medium-emphasis mt-2">换个关键词试试？</div>
      </div>

      <!-- Bangumi 结果 -->
      <div v-if="results.bangumi.length > 0" class="mb-8">
        <div class="d-flex align-center mb-3">
          <v-icon start size="small" color="info">mdi-star-outline</v-icon>
          <span class="text-subtitle-1 font-weight-bold">Bangumi (番剧)</span>
          <span class="text-caption text-medium-emphasis ml-2">({{ results.bangumi.length }})</span>
        </div>
        <div class="media-card-grid">
          <v-card v-for="item in results.bangumi" :key="'bgm-' + item.id" class="glass-card media-card cursor-pointer" @click="openBangumi(item)">
              <div class="media-card__poster">
                <v-img
                  v-if="getBgmPoster(item)"
                  :src="getBgmPoster(item)"
                  cover
                  class="rounded-t-xl"
                >
                  <template #placeholder>
                    <v-skeleton-loader type="image" />
                  </template>
                </v-img>
                <span v-if="item.platform" class="media-card__type media-card__type--bgm">{{ item.platform }}</span>
                <span v-if="item.vote_average || item.rating" class="media-card__rating">⭐ {{ Number(item.vote_average || item.rating).toFixed(1) }}</span>
                <div v-if="isSubscribed(item, 'bangumi')" class="media-card__sub-badge">
                  <v-icon size="14" color="white">mdi-check-circle</v-icon>
                </div>
              </div>
              <div class="media-card__info">
                <div class="media-card__title">{{ item.title || item.name }}</div>
                <div class="media-card__year">{{ (item.air_date || '').slice(0, 4) }}</div>
              </div>
            </v-card>
        </div>
      </div>

      <!-- TMDB 电影结果 -->
      <div v-if="results.tmdb_movie.length > 0" class="mb-8">
        <div class="d-flex align-center mb-3">
          <v-icon start size="small" color="primary">mdi-movie-open-outline</v-icon>
          <span class="text-subtitle-1 font-weight-bold">TMDB (电影)</span>
          <span class="text-caption text-medium-emphasis ml-2">({{ results.tmdb_movie.length }})</span>
        </div>
        <div class="media-card-grid">
          <v-card v-for="item in results.tmdb_movie" :key="'mv-' + item.id" class="glass-card media-card cursor-pointer" @click="openTmdb(item, 'movie')">
            <div class="media-card__poster">
              <v-img
                v-if="getTmdbPoster(item)"
                :src="getTmdbPoster(item)"
                cover
                class="rounded-t-xl"
              >
                <template #placeholder>
                  <v-skeleton-loader type="image" />
                </template>
              </v-img>
              <span class="media-card__type media-card__type--tmdb-movie">电影</span>
              <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
              <div v-if="isSubscribed(item, 'tmdb')" class="media-card__sub-badge">
                <v-icon size="14" color="white">mdi-check-circle</v-icon>
              </div>
            </div>
            <div class="media-card__info">
              <div class="media-card__title">{{ item.title || item.name }}</div>
              <div class="media-card__year">{{ (item.release_date || '').slice(0, 4) }}</div>
            </div>
          </v-card>
        </div>
      </div>

      <!-- TMDB 剧集结果 -->
      <div v-if="results.tmdb_tv.length > 0" class="mb-8">
        <div class="d-flex align-center mb-3">
          <v-icon start size="small" color="info">mdi-television-classic</v-icon>
          <span class="text-subtitle-1 font-weight-bold">TMDB (剧集)</span>
          <span class="text-caption text-medium-emphasis ml-2">({{ results.tmdb_tv.length }})</span>
        </div>
        <div class="media-card-grid">
          <v-card v-for="item in results.tmdb_tv" :key="'tv-' + item.id" class="glass-card media-card cursor-pointer" @click="openTmdb(item, 'tv')">
            <div class="media-card__poster">
              <v-img
                v-if="getTmdbPoster(item)"
                :src="getTmdbPoster(item)"
                cover
                class="rounded-t-xl"
              >
                <template #placeholder>
                  <v-skeleton-loader type="image" />
                </template>
              </v-img>
              <span class="media-card__type media-card__type--tmdb-tv">剧集</span>
              <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
              <div v-if="isSubscribed(item, 'tmdb')" class="media-card__sub-badge">
                <v-icon size="14" color="white">mdi-check-circle</v-icon>
              </div>
            </div>
            <div class="media-card__info">
              <div class="media-card__title">{{ item.title || item.name }}</div>
              <div class="media-card__year">{{ (item.first_air_date || item.release_date || '').slice(0, 4) }}</div>
            </div>
          </v-card>
        </div>
      </div>
    </div>

    <!-- 初始空状态 -->
    <div v-else class="text-center pa-12">
      <v-icon size="64" color="primary" class="mb-4">mdi-magnify</v-icon>
      <div class="text-h6 font-weight-medium">输入关键词搜索</div>
      <div class="text-body-2 text-medium-emphasis mt-2">同时搜索 TMDB 和 Bangumi 的番剧、电影数据</div>
    </div>
  </div>
</template>


