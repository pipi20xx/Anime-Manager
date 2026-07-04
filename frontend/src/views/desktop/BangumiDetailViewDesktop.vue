<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
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
  LiveTvOutlined as EpisodeIcon
} from '@vicons/material'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch, openTmdbDetail } from '../../store/navigationStore'

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
  // "00:23:40" -> "23:40"
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
  <div class="bangumi-detail-page">
    <div class="page-header">
      <n-button size="small" @click="goBack">
        <template #icon><n-icon><BackIcon /></n-icon></template>
        返回
      </n-button>
    </div>

    <div v-if="loading && !detail" class="loading-box">
      <n-skeleton height="300px" width="100%" />
    </div>

    <div v-else-if="detail" class="detail-container">
        <div class="header-content">
          <div class="poster-col">
            <n-image :src="getImg(detail.poster_path) || DEFAULT_POSTER" class="main-poster" object-fit="contain" :fallback-src="DEFAULT_POSTER" />
          </div>
          <div class="info-col">
            <h1 class="title">{{ detail.title || detail.name }}</h1>
            <div class="original-title">{{ detail.original_title }}</div>
            
            <n-space class="meta-tags" align="center">
              <n-tag type="warning" round size="small">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.vote_average?.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="small" style="background: var(--app-surface-card-mixed)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ detail.release_date }}
              </n-tag>
              <n-tag v-if="detail.total_episodes" type="success" size="small" round :bordered="false">
                共 {{ detail.total_episodes }} 集
              </n-tag>
              <span class="bangumi-id-text">Bangumi ID <span class="bangumi-id-value" @click="openExternal">{{ bangumiId }}</span></span>
            </n-space>

            <div class="actions">
              <n-button type="primary" size="small" @click="handleSubscribe" :disabled="isSubscribed">
                {{ isSubscribed ? '已在订阅中' : '订阅此番' }}
              </n-button>
              <n-button type="primary" size="small" :loading="matchingTmdb" @click="matchTmdb">
                <template #icon><n-icon><MatchIcon /></n-icon></template>
                查看 TMDB
              </n-button>
              <n-button type="primary" size="small" @click="triggerGlobalSearch(detail.original_title || detail.title || detail.name)">
                搜资源
              </n-button>
            </div>
          </div>
        </div>

        <div class="body-content">
          <div v-if="detail.genres?.length" class="genres-row">
            <n-space>
              <n-tag v-for="g in detail.genres" :key="g" type="primary" size="tiny" :bordered="false" round>
                {{ g }}
              </n-tag>
            </n-space>
          </div>

          <div class="overview-section">
            <h3>简介</h3>
            <p class="overview-text">{{ detail.overview || '暂无简介' }}</p>
          </div>

          <div v-if="detail.tags?.length" class="tags-section">
            <n-space>
              <n-tag v-for="t in detail.tags" :key="t" size="tiny" :bordered="false" round style="background: var(--bg-surface); color: var(--text-tertiary)">
                # {{ t }}
              </n-tag>
            </n-space>
          </div>

          <div v-if="detail.cast?.length" class="cast-section">
            <h3><n-icon><CastIcon /></n-icon> 角色与声优</h3>
            <n-scrollbar x-scrollable>
              <div class="cast-scroller">
                <div v-for="c in detail.cast" :key="c.character" class="cast-card">
                  <div class="cast-avatar">
                    <n-image :src="c.image || DEFAULT_AVATAR" object-fit="cover" preview-disabled :fallback-src="DEFAULT_AVATAR" />
                  </div>
                  <div class="cast-names">
                    <div class="char-name">{{ c.character }}</div>
                    <div class="actor-name">{{ c.actor }}</div>
                  </div>
                </div>
              </div>
            </n-scrollbar>
          </div>

          <div class="episodes-section">
            <h3>
              <n-icon><EpisodeIcon /></n-icon> 章节列表
              <span class="ep-count" v-if="episodesTotal">（共 {{ episodesTotal }} 集）</span>
            </h3>

            <div v-if="episodesLoading" class="ep-loading">
              <n-skeleton height="56px" width="100%" style="margin-bottom: 8px" />
              <n-skeleton height="56px" width="100%" style="margin-bottom: 8px" />
              <n-skeleton height="56px" width="100%" />
            </div>

            <div v-else-if="episodes.length" class="episode-list">
              <div v-for="ep in episodes" :key="ep.id" class="episode-item">
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
                    <n-tag v-if="ep.airdate" :bordered="false" size="tiny" style="background: var(--app-surface-card-mixed)">
                      <template #icon><n-icon><DateIcon /></n-icon></template>
                      {{ ep.airdate }}
                    </n-tag>
                    <span v-if="airedStatus(ep.airdate)" class="ep-status" :class="{ 'aired': airedStatus(ep.airdate) === '已播出' }">
                      {{ airedStatus(ep.airdate) }}
                    </span>
                    <span v-if="ep.duration" class="ep-duration">{{ formatDuration(ep.duration) }}</span>
                    <span v-if="ep.comment" class="ep-comments">{{ ep.comment }} 评论</span>
                  </div>
                  <div v-if="ep.desc" class="ep-desc">{{ ep.desc }}</div>
                </div>
              </div>
            </div>

            <div v-else class="ep-empty">暂无章节信息</div>
          </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.bangumi-detail-page {
  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--app-bg-color) var(--app-layout-opacity, 100%), transparent);
}

.page-header {
  padding: 16px 32px;
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface-card-mixed);
}

.loading-box { padding: 40px; }

.detail-container { flex: 1; display: flex; flex-direction: column; }

.header-content { position: relative; z-index: 2; padding: 30px 32px; display: flex; gap: 20px; width: 100%; }
.main-poster {
  width: 260px; aspect-ratio: 3/4;
  border-radius: var(--card-border-radius, 6px);
  box-shadow: 0 8px 24px var(--shadow-heavy);
  border: 1px solid var(--app-border-light);
  overflow: hidden; background: var(--bg-primary);
}
.main-poster :deep(img) { width: 100%; height: 100%; object-fit: contain; }

.info-col { flex-grow: 1; }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--text-primary); line-height: 1.2; }
.original-title { font-size: 13px; color: var(--text-tertiary); margin-bottom: 10px; }
.meta-tags { margin-bottom: 15px; }
.bangumi-id-text { font-size: 13px; color: var(--text-tertiary); }
.bangumi-id-value { color: #3B82F6; cursor: pointer; }
.bangumi-id-value:hover { text-decoration: underline; }
.actions { display: flex; gap: 10px; }

.body-content { padding: 30px 32px 32px 32px; }
.genres-row { margin-bottom: 16px; }
.overview-section { margin-bottom: 20px; }
.overview-section h3 { margin: 0 0 8px 0; color: var(--n-primary-color); font-size: 15px; }
.overview-text { color: var(--text-secondary); line-height: 1.6; font-size: 14px; text-align: justify; }

.tags-section { margin-bottom: 24px; }

.cast-section { margin-bottom: 24px; }
.cast-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; display: flex; align-items: center; gap: 6px; }
.cast-scroller { display: flex; gap: 16px; padding-bottom: 8px; }
.cast-card { min-width: 90px; width: 90px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.cast-avatar {
  width: 64px; height: 64px;
  border-radius: 50%; overflow: hidden;
  border: 1px solid var(--app-border-light);
  margin-bottom: 6px; background: var(--app-surface-card-mixed);
}
.cast-avatar :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.char-name { font-size: 12px; font-weight: bold; color: var(--text-primary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actor-name { font-size: 12px; color: var(--text-tertiary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.episodes-section { margin-bottom: 24px; }
.episodes-section h3 {
  margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px;
  display: flex; align-items: center; gap: 6px;
}
.ep-count { font-size: 12px; color: var(--text-tertiary); font-weight: normal; }
.ep-loading { padding: 0; }
.episode-list {
  display: flex; flex-direction: column; gap: 8px;
}
.episode-item {
  display: flex; gap: 14px; padding: 10px 12px;
  background: var(--app-surface-card-mixed); border: 1px solid var(--app-border-light);
  border-radius: 6px; transition: border-color 0.15s;
}
.episode-item:hover { border-color: var(--n-primary-color); }
.ep-number {
  flex-shrink: 0; min-width: 52px; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.1)); border-radius: 6px; padding: 6px 4px;
}
.ep-num-main { font-size: 18px; font-weight: 900; color: var(--n-primary-color); line-height: 1; }
.ep-num-sort { font-size: 10px; color: var(--text-tertiary); margin-top: 2px; }
.ep-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.ep-headline { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ep-title-text { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.ep-title-orig { font-size: 12px; color: var(--text-tertiary); }
.ep-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--text-tertiary); }
.ep-duration { color: var(--text-tertiary); }
.ep-comments { color: var(--text-tertiary); }
.ep-status { padding: 1px 6px; border-radius: 4px; font-size: 11px; background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.1)); color: var(--text-tertiary); }
.ep-status.aired { color: var(--n-success-color); }
.ep-desc {
  font-size: 12px; color: var(--text-secondary); line-height: 1.6;
  white-space: pre-line;
  padding-top: 4px; border-top: 1px dashed var(--app-border-light); margin-top: 2px;
}
.ep-empty { color: var(--text-tertiary); font-size: 13px; padding: 16px 0; }
</style>
