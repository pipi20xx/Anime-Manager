<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  PersonOutlined as CastIcon,
  CompareArrowsOutlined as MatchIcon,
  ArrowBackOutlined as BackIcon,
  SearchOutlined as SearchIcon,
  LiveTvOutlined as EpisodeIcon
} from '@vicons/material'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch } from '../../store/navigationStore'

const route = useRoute()
const router = useRouter()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const message = useMessage()

const bangumiId = computed(() => route.params.id as string)

const loading = ref(false)
const detail = ref<any>(null)
const subscriptions = ref<any[]>([])
const matchingTmdb = ref(false)
const episodes = ref<any[]>([])
const episodesTotal = ref(0)
const episodesLoading = ref(false)

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

const fetchSubscriptions = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/subscriptions`)
    if (res.ok) subscriptions.value = await res.json()
  } catch (e) {}
}

const isSubscribed = computed(() => {
    if (!detail.value) return false
    if (subscriptions.value.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(bangumiId.value))) {
        return true
    }
    const title = detail.value.title || detail.value.name
    const orig = detail.value.original_title || detail.value.name
    return subscriptions.value.some((sub: any) => sub.title === title || sub.title === orig)
})

const fetchDetail = async () => {
  if (!bangumiId.value) return
  loading.value = true
  fetchSubscriptions()
  fetchEpisodes()
  try {
    const res = await fetch(`${API_BASE}/api/bangumi/subject/${bangumiId.value}`)
    if (res.ok) {
        detail.value = await res.json()
    } else {
        message.error('获取 Bangumi 详情失败')
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchEpisodes = async () => {
  if (!bangumiId.value) return
  episodesLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/bangumi/subject/${bangumiId.value}/episodes?type=0`)
    if (res.ok) {
        const data = await res.json()
        episodes.value = data?.data || []
        episodesTotal.value = data?.total || episodes.value.length
    } else {
        episodes.value = []
        episodesTotal.value = 0
    }
  } catch (e) {
    console.error(e)
    episodes.value = []
    episodesTotal.value = 0
  } finally {
    episodesLoading.value = false
  }
}

const formatDuration = (dur: string) => {
  if (!dur) return ''
  const parts = dur.split(':')
  if (parts.length === 3) {
    const h = parseInt(parts[0])
    const m = parseInt(parts[1])
    const s = parseInt(parts[2])
    if (h > 0) return `${h}时${m}分`
    return `${m}:${String(s).padStart(2, '0')}`
  }
  return dur
}

const airedStatus = (airdate: string) => {
  if (!airdate) return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(airdate)
  if (isNaN(d.getTime())) return ''
  d.setHours(0, 0, 0, 0)
  return d <= today ? '已播出' : '未播出'
}

const goBack = () => {
  router.back()
}

const openExternal = () => {
    window.open(`https://bangumi.tv/subject/${bangumiId.value}`, '_blank')
}

const handleSubscribe = async () => {
    if (!detail.value) return
    loading.value = true
    
    message.loading('正在尝试自动匹配并订阅...', { duration: 2000 })
    
    try {
        const res = await fetch(`${API_BASE}/api/bangumi/one_click_subscribe/${bangumiId.value}`, {
            method: 'POST'
        })
        const data = await res.json()
        
        if (res.ok && data.success) {
            message.success(data.message || '订阅成功')
            fetchSubscriptions()
        } else {
            message.info('匹配置信度不足，正在跳转至手动配置...')
            
            const mRes = await fetch(`${API_BASE}/api/bangumi/match_tmdb/${bangumiId.value}`)
            const mData = await mRes.json()
            
            setTimeout(() => {
                navigateToSubscription({
                    type: mData.success ? 'tmdb' : 'bangumi',
                    tmdbId: mData.tmdb_id,
                    mediaType: mData.media_type,
                    title: mData.title || detail.value.title || detail.value.name,
                    year: mData.year,
                    bangumiId: bangumiId.value,
                    season: mData.season,
                    totalEpisodes: mData.total_episodes || (mData.bgm_info?.total_episodes),
                    poster_path: mData.poster_path || (mData.bgm_info?.poster_path)
                })
            }, 300)
        }
    } catch (e) {
        console.error(e)
        message.error('订阅过程中发生错误')
    } finally {
        loading.value = false
    }
}

const matchTmdb = async () => {
    if (!bangumiId.value) return
    matchingTmdb.value = true
    
    try {
        const res = await fetch(`${API_BASE}/api/bangumi/match_tmdb/${bangumiId.value}`)
        const data = await res.json()
        
        if (data.success && data.tmdb_id) {
            message.success(`已匹配到 TMDB: ${data.title}`)
            setTimeout(() => {
                router.push({ name: 'TmdbDetail', params: { id: data.tmdb_id, type: data.media_type || 'tv' } })
            }, 200)
        } else {
            message.warning('未能找到匹配的 TMDB 条目')
        }
    } catch (e) {
        console.error(e)
        message.error('匹配 TMDB 失败')
    } finally {
        matchingTmdb.value = false
    }
}

onMounted(() => {
  fetchDetail()
})
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- Header -->
    <div class="m-header m-header-plain">
      <div class="m-header-left">
        <n-button text size="small" @click="goBack">
          <template #icon><n-icon size="22"><BackIcon /></n-icon></template>
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
            <n-image :src="getImg(detail.poster_path) || DEFAULT_POSTER" object-fit="cover" preview-disabled :fallback-src="DEFAULT_POSTER" style="width: 100%; aspect-ratio: 3/4;" />
          </div>
          <div class="m-detail-info">
            <h1 class="m-detail-title">{{ detail.title || detail.name }}</h1>
            <div v-if="detail.original_title" style="font-size: var(--m-text-sm); color: var(--text-muted); margin-top: var(--m-spacing-xs);">
              {{ detail.original_title }}
            </div>
            <div class="m-detail-meta" style="flex-wrap: wrap;">
              <span class="m-bangumi-id-text">Bangumi ID <span class="m-bangumi-id-value" @click="openExternal">{{ bangumiId }}</span></span>
              <n-tag type="warning" round size="tiny">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.vote_average?.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="tiny" style="background: var(--app-surface-card-mixed)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ detail.release_date }}
              </n-tag>
              <n-tag v-if="detail.total_episodes" type="success" size="tiny" round :bordered="false">
                共 {{ detail.total_episodes }} 集
              </n-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="m-detail-actions" style="padding: 0 var(--m-spacing-lg) var(--m-spacing-lg); display: flex; flex-direction: column; gap: var(--m-spacing-md);">
        <n-button type="primary" block size="large" @click="handleSubscribe" :disabled="isSubscribed">
          {{ isSubscribed ? '已在订阅中' : '订阅此番' }}
        </n-button>
        <n-button type="primary" ghost block size="large" :loading="matchingTmdb" @click="matchTmdb">
          查看 TMDB
        </n-button>
        <n-button block size="large" @click="triggerGlobalSearch(detail.original_title || detail.title || detail.name)">
          搜资源
        </n-button>
      </div>

      <div class="m-detail-body">
        <!-- Genres -->
        <div v-if="detail.genres?.length" class="m-detail-section">
          <n-space>
            <n-tag v-for="g in detail.genres" :key="g" type="primary" size="small" :bordered="false" round>
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

        <!-- Tags -->
        <div v-if="detail.tags?.length" class="m-detail-section">
          <h3 class="m-detail-section-title">标签</h3>
          <n-space>
            <n-tag v-for="t in detail.tags" :key="t" size="small" :bordered="false" round style="background: var(--bg-surface); color: var(--text-tertiary)">
              # {{ t }}
            </n-tag>
          </n-space>
        </div>

        <!-- Cast -->
        <div v-if="detail.cast?.length" class="m-detail-section">
          <h3 class="m-detail-section-title"><n-icon><CastIcon /></n-icon> 角色与声优</h3>
          <div class="m-h-scroll">
            <div v-for="c in detail.cast" :key="c.character" class="cast-card-mobile">
              <div class="cast-avatar-mobile">
                <n-image :src="c.image || DEFAULT_AVATAR" object-fit="cover" preview-disabled :fallback-src="DEFAULT_AVATAR" />
              </div>
              <div class="cast-name-mobile" style="font-weight: 600;">{{ c.character }}</div>
              <div class="cast-name-mobile" style="color: var(--text-muted);">{{ c.actor }}</div>
            </div>
          </div>
        </div>

        <!-- Episodes -->
        <div class="m-detail-section">
          <h3 class="m-detail-section-title">
            <n-icon><EpisodeIcon /></n-icon> 章节列表
            <span v-if="episodesTotal" style="font-size: var(--m-text-sm); color: var(--text-muted); font-weight: normal;">（共 {{ episodesTotal }} 集）</span>
          </h3>

          <div v-if="episodesLoading" class="m-ep-loading">
            <n-skeleton height="64px" width="100%" style="margin-bottom: 8px; border-radius: var(--m-radius-md);" />
            <n-skeleton height="64px" width="100%" style="margin-bottom: 8px; border-radius: var(--m-radius-md);" />
            <n-skeleton height="64px" width="100%" style="border-radius: var(--m-radius-md);" />
          </div>

          <div v-else-if="episodes.length" class="m-ep-list">
            <div v-for="ep in episodes" :key="ep.id" class="m-ep-item">
              <div class="m-ep-number">
                <span class="m-ep-num">{{ ep.ep ?? ep.sort }}</span>
                <span v-if="ep.sort !== ep.ep" class="m-ep-sort">排序{{ ep.sort }}</span>
              </div>
              <div class="m-ep-body">
                <div class="m-ep-title">{{ ep.name_cn || ep.name || `第 ${ep.ep ?? ep.sort} 集` }}</div>
                <div v-if="ep.name && ep.name_cn && ep.name !== ep.name_cn" class="m-ep-orig">{{ ep.name }}</div>
                <div class="m-ep-meta">
                  <span v-if="ep.airdate" class="m-ep-date">{{ ep.airdate }}</span>
                  <span v-if="airedStatus(ep.airdate)" class="m-ep-status" :class="{ 'aired': airedStatus(ep.airdate) === '已播出' }">
                    {{ airedStatus(ep.airdate) }}
                  </span>
                  <span v-if="ep.duration" class="m-ep-dur">{{ formatDuration(ep.duration) }}</span>
                  <span v-if="ep.comment" class="m-ep-cmt">{{ ep.comment }}评</span>
                </div>
                <div v-if="ep.desc" class="m-ep-desc">{{ ep.desc }}</div>
              </div>
            </div>
          </div>

          <div v-else style="color: var(--text-muted); font-size: var(--m-text-md);">暂无章节信息</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  background: var(--app-surface-card-mixed);
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

.m-ep-loading { padding: 0; }
.m-ep-list {
  display: flex; flex-direction: column; gap: var(--m-spacing-sm);
}
.m-ep-item {
  display: flex; gap: var(--m-spacing-sm); padding: var(--m-spacing-sm);
  background: var(--app-surface-card-mixed); border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-md);
}
.m-ep-number {
  flex-shrink: 0; min-width: 44px; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: var(--app-surface-card-mixed); border-radius: var(--m-radius-sm);
  padding: 4px 2px;
}
.m-ep-num { font-size: 18px; font-weight: 900; color: var(--n-primary-color); line-height: 1; }
.m-ep-sort { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.m-ep-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.m-ep-title {
  font-size: var(--m-text-md); font-weight: 600; color: var(--text-primary);
  line-height: 1.3; word-break: break-word;
}
.m-ep-orig { font-size: var(--m-text-xs); color: var(--text-muted); }
.m-ep-meta {
  display: flex; align-items: center; gap: var(--m-spacing-xs); flex-wrap: wrap;
  font-size: var(--m-text-xs); color: var(--text-muted);
}
.m-ep-date { color: var(--text-muted); }
.m-ep-dur { color: var(--text-muted); }
.m-ep-cmt { color: var(--text-muted); }
.m-ep-status {
  padding: 1px 5px; border-radius: 3px; font-size: 10px;
  background: var(--app-surface-card-mixed); color: var(--text-muted);
}
.m-ep-status.aired { color: var(--n-success-color); }
.m-ep-desc {
  font-size: var(--m-text-xs); color: var(--text-secondary); line-height: 1.55;
  white-space: pre-line;
  padding-top: 4px; border-top: 1px dashed var(--app-border-light); margin-top: 2px;
}
.m-bangumi-id-text { font-size: var(--m-text-xs); color: var(--text-muted); }
.m-bangumi-id-value { color: #3B82F6; cursor: pointer; }
.m-bangumi-id-value:hover { text-decoration: underline; }
</style>
