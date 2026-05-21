<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as CastIcon,
  CompareArrowsOutlined as MatchIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import { useMessage } from 'naive-ui'
import { navigateToSubscription, triggerGlobalSearch, openTmdbDetail, bangumiDetailState, currentViewKey } from '../store/navigationStore'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const message = useMessage()

const loading = ref(false)
const detail = ref<any>(null)
const subscriptions = ref<any[]>([])
const matchingTmdb = ref(false)

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
    if (subscriptions.value.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(bangumiDetailState.value.id))) {
        return true
    }
    const title = detail.value.title || detail.value.name
    const orig = detail.value.original_title || detail.value.name
    return subscriptions.value.some((sub: any) => sub.title === title || sub.title === orig)
})

const fetchDetail = async () => {
  if (!bangumiDetailState.value.id) return
  loading.value = true
  fetchSubscriptions() 
  try {
    const res = await fetch(`${API_BASE}/api/bangumi/subject/${bangumiDetailState.value.id}`)
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

const goBack = () => {
  currentViewKey.value = 'ExploreView'
}

const openExternal = () => {
    window.open(`https://bgm.tv/subject/${bangumiDetailState.value.id}`, '_blank')
}

const handleSubscribe = async () => {
    if (!detail.value) return
    loading.value = true
    
    message.loading('正在尝试自动匹配并订阅...', { duration: 2000 })
    
    try {
        const res = await fetch(`${API_BASE}/api/bangumi/one_click_subscribe/${bangumiDetailState.value.id}`, {
            method: 'POST'
        })
        const data = await res.json()
        
        if (res.ok && data.success) {
            message.success(data.message || '订阅成功')
            fetchSubscriptions()
        } else {
            message.info('匹配置信度不足，正在跳转至手动配置...')
            
            const mRes = await fetch(`${API_BASE}/api/bangumi/match_tmdb/${bangumiDetailState.value.id}`)
            const mData = await mRes.json()
            
            setTimeout(() => {
                navigateToSubscription({
                    type: mData.success ? 'tmdb' : 'bangumi',
                    tmdbId: mData.tmdb_id,
                    mediaType: mData.media_type,
                    title: mData.title || detail.value.title || detail.value.name,
                    year: mData.year,
                    bangumiId: bangumiDetailState.value.id,
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
    if (!bangumiDetailState.value.id) return
    matchingTmdb.value = true
    
    try {
        const res = await fetch(`${API_BASE}/api/bangumi/match_tmdb/${bangumiDetailState.value.id}`)
        const data = await res.json()
        
        if (data.success && data.tmdb_id) {
            message.success(`已匹配到 TMDB: ${data.title}`)
            setTimeout(() => {
                openTmdbDetail(data.tmdb_id, data.media_type || 'tv', {
                    title: data.title,
                    poster_path: data.poster_path,
                    vote_average: null,
                    year: data.year
                })
                currentViewKey.value = 'TmdbDetailView'
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
  if (bangumiDetailState.value.initial) {
    detail.value = bangumiDetailState.value.initial
  }
  fetchDetail()
})

watch(() => bangumiDetailState.value.id, () => {
  detail.value = bangumiDetailState.value.initial || null
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
            <n-image :src="getImg(detail.poster_path)" class="main-poster" object-fit="contain" />
          </div>
          <div class="info-col">
            <h1 class="title">{{ detail.title || detail.name }}</h1>
            <div class="original-title">{{ detail.original_title }}</div>
            
            <n-space class="meta-tags" align="center">
              <n-tag type="warning" round size="small">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.vote_average?.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="small" style="background: var(--app-surface-inner)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ detail.release_date }}
              </n-tag>
              <n-tag v-if="detail.total_episodes" type="success" size="small" round :bordered="false">
                共 {{ detail.total_episodes }} 集
              </n-tag>
              <n-tag type="error" size="small" :bordered="false">Bangumi</n-tag>
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
              <n-button type="primary" ghost circle size="small" @click="openExternal">
                <template #icon><n-icon><LinkIcon /></n-icon></template>
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
                    <n-image :src="c.image" object-fit="cover" preview-disabled />
                  </div>
                  <div class="cast-names">
                    <div class="char-name">{{ c.character }}</div>
                    <div class="actor-name">{{ c.actor }}</div>
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
.bangumi-detail-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--app-bg-color);
}

.page-header {
  padding: 16px 32px;
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface-card);
}

.loading-box { padding: 40px; }

.detail-container { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.header-content { position: relative; z-index: 2; padding: 30px 32px; display: flex; gap: 20px; width: 100%; }
.main-poster { 
  width: 130px; aspect-ratio: 3/4; 
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
  margin-bottom: 6px; background: var(--app-surface-inner); 
}
.cast-avatar :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.char-name { font-size: 12px; font-weight: bold; color: var(--text-primary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actor-name { font-size: 12px; color: var(--text-tertiary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
