<script setup lang="ts">
/**
 * BangumiDetailView — Bangumi 条目详情页
 *
 * 对标旧前端 BangumiDetailViewDesktop:
 * - 封面 + 元数据标签 + Bangumi ID 跳转
 * - 一键订阅（自动匹配，匹配置信度不足时跳转手动配置）
 * - 查看 TMDB（匹配后跳转 TMDB 详情页）
 * - 搜资源（跳转 Jackett 搜索页）
 * - 已订阅状态判断
 * - 角色信息横向滚动
 * - 章节列表（含播出状态）
 * - 关联条目
 *
 * 注意：后端 get_subject_details 返回统一格式：
 *   title, original_title, overview, poster_path, vote_average,
 *   total_episodes, release_date, genres, tags, cast, source
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { bangumiApi, subscriptionApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'BangumiDetailView' })

const route = useRoute()
const router = useRouter()
const { success, error: showError, warning, info: showInfo } = useNotification()
const navStore = useNavigationStore()

const detail = ref<any>(null)
const episodes = ref<any[]>([])
const episodesTotal = ref(0)
const subscriptions = ref<any[]>([])
const loading = ref(false)
const episodesLoading = ref(false)
const matchingTmdb = ref(false)
const showAllEpisodes = ref(false)

const bangumiId = computed(() => route.params.id as string)

const isSubscribed = computed(() => {
  if (!detail.value) return false
  if (subscriptions.value.some((s: any) => s.bangumi_id && String(s.bangumi_id) === String(bangumiId.value))) {
    return true
  }
  const title = detail.value.title
  const orig = detail.value.original_title
  return subscriptions.value.some((s: any) => s.title === title || s.title === orig)
})

async function fetchSubscriptions() {
  try {
    subscriptions.value = (await subscriptionApi.getSubscriptions()) || []
  } catch { /* */ }
}

async function fetchDetail() {
  const id = route.params.id as string
  if (!id) return

  loading.value = true
  fetchSubscriptions()
  try {
    detail.value = await bangumiApi.getSubject(id)
    // 加载章节信息
    episodesLoading.value = true
    try {
      const epData = await bangumiApi.getSubjectEpisodes(id)
      // 后端 get_episodes 返回 { data: [...], total: N } 格式
      episodes.value = epData?.data || (Array.isArray(epData) ? epData : [])
      episodesTotal.value = epData?.total || episodes.value.length
    } catch {
      episodes.value = []
      episodesTotal.value = 0
    } finally {
      episodesLoading.value = false
    }
  } catch (e) {
    showError('加载条目详情失败')
  } finally {
    loading.value = false
  }
}

/** 一键订阅 — 与旧前端逻辑一致：先尝试自动匹配，匹配置信度不足时跳转手动配置 */
async function handleOneClickSubscribe() {
  if (!detail.value) return
  loading.value = true
  showInfo('正在尝试自动匹配并订阅...')

  try {
    const res = await bangumiApi.oneClickSubscribe(detail.value.id)
    if (res?.success) {
      success(res.message || '订阅成功')
      fetchSubscriptions()
    } else {
      // 匹配置信度不足，跳转手动配置
      warning('匹配置信度不足，正在跳转至手动配置...')
      const mData = await bangumiApi.matchTmdb(detail.value.id)
      setTimeout(() => {
        navStore.navigateToSubscription({
          type: mData?.success ? 'tmdb' : 'bangumi',
          tmdbId: mData?.tmdb_id,
          mediaType: mData?.media_type,
          title: mData?.title || detail.value.title,
          year: mData?.year,
          bangumiId: bangumiId.value,
          season: mData?.season,
          totalEpisodes: mData?.total_episodes || mData?.bgm_info?.total_episodes,
          poster_path: mData?.poster_path || mData?.bgm_info?.poster_path,
        })
      }, 300)
    }
  } catch (e: any) {
    showError(e?.message || '订阅过程中发生错误')
  } finally {
    loading.value = false
  }
}

/** 查看 TMDB — 匹配后跳转 TMDB 详情页 */
async function handleMatchTmdb() {
  if (!detail.value) return
  matchingTmdb.value = true

  try {
    const data = await bangumiApi.matchTmdb(detail.value.id)
    if (data?.success && data.tmdb_id) {
      success(`已匹配到 TMDB: ${data.title}`)
      setTimeout(() => {
        navStore.openTmdbDetail(data.tmdb_id, data.media_type || 'tv')
      }, 200)
    } else {
      warning('未能找到匹配的 TMDB 条目')
    }
  } catch (e: any) {
    showError(e?.message || '匹配 TMDB 失败')
  } finally {
    matchingTmdb.value = false
  }
}

/** 搜资源 — 跳转 Jackett 搜索页 */
function handleSearchResource() {
  const keyword = detail.value?.title || detail.value?.original_title || ''
  if (keyword) navStore.triggerGlobalSearch(keyword)
}

/** 打开 Bangumi 官网页面 */
function openExternal() {
  window.open(`https://bangumi.tv/subject/${bangumiId.value}`, '_blank')
}

/** 章节播出状态 */
function airedStatus(airdate: string): string {
  if (!airdate) return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(airdate)
  if (isNaN(d.getTime())) return ''
  d.setHours(0, 0, 0, 0)
  return d <= today ? '已播出' : '未播出'
}

function openRelatedItem(item: any) {
  navStore.openBangumiDetail(item.id)
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
  <div class="bangumi-detail-view">
    <!-- 加载骨架屏 -->
    <template v-if="loading && !detail">
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
      <v-container fluid class="pa-4 pa-md-6">
        <!-- 返回按钮 -->
        <div class="mb-4">
          <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-arrow-left" @click="router.back()">返回</v-btn>
        </div>

        <v-row>
          <!-- 封面 -->
          <v-col cols="12" sm="3" md="2">
            <v-img
              v-if="detail.poster_path"
              :src="getImg(detail.poster_path)"
              cover
              rounded="xl"
              aspect-ratio="3/4"
              class="elevation-4"
            />
          </v-col>

          <!-- 信息 -->
          <v-col cols="12" sm="9" md="10">
            <h1 class="page-title text-h4 font-weight-bold">{{ detail.title }}</h1>
            <div v-if="detail.original_title && detail.original_title !== detail.title" class="page-subtitle text-body-1 mt-1">
              {{ detail.original_title }}
            </div>

            <!-- 标签 -->
            <v-chip-group class="mt-3" column>
              <v-chip v-if="detail.source === 'bangumi'" size="small" variant="tonal" color="info">
                动画
              </v-chip>
              <v-chip v-if="detail.release_date" size="small" variant="tonal">
                <v-icon start size="x-small">mdi-calendar</v-icon>
                {{ detail.release_date }}
              </v-chip>
              <v-chip v-if="detail.total_episodes" size="small" variant="tonal" color="info">
                共 {{ detail.total_episodes }} 集
              </v-chip>
              <v-chip v-if="detail.vote_average" size="small" variant="tonal" color="info">
                ⭐ {{ detail.vote_average.toFixed(1) }}
              </v-chip>
              <v-chip size="small" variant="tonal" color="info">
                <span class="cursor-pointer" @click="openExternal">Bangumi ID: {{ bangumiId }}</span>
              </v-chip>
            </v-chip-group>

            <!-- 评分分布 -->
            <div v-if="detail.vote_average" class="mt-3">
              <v-progress-linear
                :model-value="detail.vote_average * 10"
                color="info"
                height="6"
                rounded
                style="max-width: 200px"
              />
            </div>

            <!-- 操作按钮 -->
            <div class="mt-4 d-flex ga-2 flex-wrap">
              <v-btn
                variant="tonal" color="primary"
                prepend-icon="mdi-rss"
                :disabled="isSubscribed"
                @click="handleOneClickSubscribe"
              >
                {{ isSubscribed ? '已在订阅中' : '订阅此番' }}
              </v-btn>
              <v-btn
                variant="tonal"
                color="primary"
                prepend-icon="mdi-link-variant"
                :loading="matchingTmdb"
                @click="handleMatchTmdb"
              >
                查看 TMDB
              </v-btn>
              <v-btn
                variant="tonal"
                color="primary"
                prepend-icon="mdi-magnify"
                @click="handleSearchResource"
              >
                搜资源
              </v-btn>
            </div>

            <!-- 简介 -->
            <div v-if="detail.overview" class="mt-4">
              <div class="section-title text-subtitle-2 font-weight-medium mb-1">简介</div>
              <div class="page-subtitle text-body-2" style="line-height: 1.8">{{ detail.overview }}</div>
            </div>

            <!-- 分类标签 -->
            <div v-if="detail.genres?.length" class="mt-4">
              <v-chip
                v-for="g in detail.genres"
                :key="g"
                size="small"
                variant="tonal"
                color="primary"
                class="mr-1 mb-1"
              >
                {{ g }}
              </v-chip>
            </div>

            <!-- 用户标签 -->
            <div v-if="detail.tags?.length" class="mt-3">
              <v-chip
                v-for="tag in detail.tags.slice(0, 15)"
                :key="tag.name || tag"
                size="small"
                variant="tonal"
                color="primary"
                class="mr-1 mb-1"
              >
                {{ tag.name || tag }}
                <span v-if="tag.count" class="ml-1 text-caption">{{ tag.count }}</span>
              </v-chip>
            </div>
          </v-col>
        </v-row>

        <!-- 角色信息 -->
        <div v-if="detail.cast?.length" class="mt-8">
          <div class="section-title text-subtitle-1 font-weight-bold mb-3">
            <v-icon start size="small">mdi-account-group</v-icon>
            角色与声优
          </div>
          <div class="cast-card-grid">
            <v-card
              v-for="c in detail.cast.slice(0, 20)"
              :key="c.character"
              class="glass-card media-card cursor-pointer"
              variant="flat"
            >
              <div class="cast-card__poster">
                <v-img
                  v-if="c.image"
                  :src="getImg(c.image)"
                  contain
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
                <div class="media-card__title">{{ c.character }}</div>
                <div v-if="c.actor" class="media-card__subtitle">{{ c.actor }}</div>
              </div>
            </v-card>
          </div>
        </div>

        <!-- 章节列表 -->
        <div class="mt-8">
          <div class="d-flex align-center justify-space-between mb-3">
            <div class="section-title text-subtitle-1 font-weight-bold">
              <v-icon start size="small">mdi-television-classic</v-icon>
              章节列表
              <span v-if="episodesTotal" class="text-caption font-weight-normal ml-2">（共 {{ episodesTotal }} 集）</span>
            </div>
            <v-btn
              v-if="episodes.length > 24"
              size="small"
              variant="text"
              @click="showAllEpisodes = !showAllEpisodes"
            >
              {{ showAllEpisodes ? '收起' : `查看全部 (${episodes.length})` }}
            </v-btn>
          </div>

          <!-- 加载中 -->
          <div v-if="episodesLoading">
            <v-skeleton-loader type="list-item@3" />
          </div>

          <!-- 章节列表 -->
          <div v-else-if="episodes.length > 0" class="episode-list">
            <v-card
              v-for="ep in (showAllEpisodes ? episodes : episodes.slice(0, 24))"
              :key="ep.id || ep.sort"
              class="glass-card hover-lift episode-item"
              variant="flat"
            >
              <div class="ep-number">
                <span class="ep-num-main">{{ ep.ep ?? ep.sort }}</span>
                <span v-if="ep.sort !== ep.ep" class="ep-num-sort">排序 {{ ep.sort }}</span>
              </div>
              <div class="ep-body">
                <div class="ep-headline">
                  <span class="ep-title-text">{{ ep.name_cn || ep.name || `第 ${ep.ep ?? ep.sort} 集` }}</span>
                  <span v-if="ep.name && ep.name_cn && ep.name !== ep.name_cn" class="ep-title-orig">{{ ep.name }}</span>
                </div>
                <div class="ep-meta">
                  <v-chip v-if="ep.airdate" size="x-small" variant="tonal" prepend-icon="mdi-calendar" class="mr-2">
                    {{ ep.airdate }}
                  </v-chip>
                  <span v-if="airedStatus(ep.airdate)" class="ep-status" :class="{ 'aired': airedStatus(ep.airdate) === '已播出' }">
                    {{ airedStatus(ep.airdate) }}
                  </span>
                  <span v-if="ep.duration" class="ml-2 text-caption text-medium-emphasis">{{ ep.duration }}</span>
                  <span v-if="ep.comment" class="ml-2 text-caption text-medium-emphasis">{{ ep.comment }} 评论</span>
                </div>
                <div v-if="ep.desc" class="ep-desc">{{ ep.desc }}</div>
              </div>
            </v-card>
          </div>

          <div v-else class="text-center pa-4 text-medium-emphasis text-body-2">暂无章节信息</div>
        </div>

        <!-- 关联条目 -->
        <div v-if="detail.related?.length" class="mt-8">
          <div class="section-title text-subtitle-1 font-weight-bold mb-3">关联条目</div>
          <div class="media-card-grid">
            <v-card
              v-for="item in detail.related.slice(0, 12)"
              :key="item.id"
              class="glass-card media-card cursor-pointer"
              @click="openRelatedItem(item)"
            >
              <div class="media-card__poster">
                <v-img
                  v-if="item.image"
                  :src="getImg(item.image)"
                  cover
                />
                <span v-if="item.platform" class="media-card__type media-card__type--bgm">{{ item.platform }}</span>
              </div>
              <div class="media-card__info">
                <div class="media-card__title">{{ item.name_cn || item.name }}</div>
                <div v-if="item.relation" class="media-card__subtitle">{{ item.relation }}</div>
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
.bangumi-detail-view {
  width: 100%;
  min-height: 100%;
}

.episode-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.episode-item {
  display: flex;
  gap: 14px;
  padding: 10px 12px;
  border-radius: 12px !important;
}

.ep-number {
  flex-shrink: 0;
  min-width: 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 8px;
  padding: 6px 4px;
}
.ep-num-main {
  font-size: 18px;
  font-weight: 900;
  color: rgb(var(--v-theme-primary));
  line-height: 1;
}
.ep-num-sort {
  font-size: 10px;
  color: rgba(var(--v-theme-on-surface), 0.87);
  margin-top: 2px;
}

.ep-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ep-headline {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.ep-title-text {
  font-size: 14px;
  font-weight: 600;
}
.ep-title-orig {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.87);
}
.ep-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  font-size: 12px;
}
.ep-status {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.87);
}
.ep-status.aired {
  color: rgba(var(--v-theme-on-surface), 0.87);
  background: rgba(var(--v-theme-on-surface), 0.1);
}
.ep-desc {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.87);
  line-height: 1.6;
  white-space: pre-line;
  padding-top: 4px;
  border-top: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
  margin-top: 2px;
}

/* 详情页 chip 文字使用默认色（白天黑/夜晚白），不使用 primary 蓝色 */
:deep(.v-chip--variant-tonal.text-primary) {
  color: rgba(var(--v-theme-on-surface), 0.88) !important;
}
:deep(.v-chip--variant-tonal.text-primary .v-chip__underlay) {
  background-color: rgba(var(--v-theme-on-surface), 0.08) !important;
}
</style>
