<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as PersonIcon,
  MovieOutlined as MovieIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import { useMessage } from 'naive-ui'

const route = useRoute()
const router = useRouter()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const message = useMessage()

const personId = computed(() => route.params.id as string)

const loading = ref(false)
const detail = ref<any>(null)
const credits = ref<{ cast: any[], crew: any[] }>({ cast: [], crew: [] })

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

const getProfile = (path: string) => getImg(path)
const getPoster = (path: string) => getImg(path)

const fetchDetail = async () => {
  const id = personId.value
  if (!id) return
  
  loading.value = true
  try {
    const [detailRes, creditsRes] = await Promise.all([
      fetch(`${API_BASE}/api/tmdb/person/${id}`),
      fetch(`${API_BASE}/api/tmdb/person/${id}/credits`)
    ])
    
    if (detailRes.ok) {
      detail.value = await detailRes.json()
    } else {
      message.error('获取人物详情失败')
    }
    
    if (creditsRes.ok) {
      credits.value = await creditsRes.json()
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.back()
}

const openExternal = () => {
  window.open(`https://www.themoviedb.org/person/${personId.value}`, '_blank')
}

const openImdb = (imdbId: string) => {
  window.open(`https://www.imdb.com/name/${imdbId}`, '_blank')
}

const genderText = (gender: number) => {
  if (gender === 1) return '女'
  if (gender === 2) return '男'
  return '未知'
}

const calculateAge = (birthday: string, deathday?: string) => {
  if (!birthday) return ''
  const birth = new Date(birthday)
  const end = deathday ? new Date(deathday) : new Date()
  let age = end.getFullYear() - birth.getFullYear()
  const m = end.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && end.getDate() < birth.getDate())) {
    age--
  }
  return age
}

const handleTmdbClick = (item: any) => {
  if (!item?.id) return
  const mediaType = item.media_type || (item.title ? 'movie' : 'tv')
  router.push({ name: 'TmdbDetail', params: { id: item.id, type: mediaType } })
}

onMounted(() => {
  fetchDetail()
})
</script>

<template>
  <div class="person-detail-page">
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
          <div class="profile-col">
            <n-image :src="getProfile(detail.profile_path)" class="main-profile" object-fit="cover" />
          </div>
          <div class="info-col">
            <div class="title-row">
              <h1 class="title">{{ detail.name }}</h1>
              <n-tag v-if="detail.known_for_department" type="info" size="small" round>
                {{ detail.known_for_department }}
              </n-tag>
            </div>
            <div v-if="detail.original_name && detail.original_name !== detail.name" class="original-name">
              {{ detail.original_name }}
            </div>
            
            <n-space class="meta-tags" align="center">
              <n-tag v-if="detail.popularity" type="warning" round size="small">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.popularity.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="small" style="background: var(--app-surface-inner)">
                <template #icon><n-icon><PersonIcon /></n-icon></template>
                {{ genderText(detail.gender) }}
              </n-tag>
              <n-tag v-if="detail.birthday" :bordered="false" size="small" style="background: var(--app-surface-inner)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ calculateAge(detail.birthday, detail.deathday) }}岁
              </n-tag>
            </n-space>

            <div class="info-grid">
              <div class="info-item" @click="openExternal">
                <span class="info-label">TMDB ID</span>
                <span class="info-value link">{{ detail.id }}</span>
              </div>
              <div v-if="detail.imdb_id" class="info-item" @click="openImdb(detail.imdb_id)">
                <span class="info-label">IMDb ID</span>
                <span class="info-value link">{{ detail.imdb_id }}</span>
              </div>
              <div v-if="detail.birthday" class="info-item">
                <span class="info-label">生日</span>
                <span class="info-value">{{ detail.birthday }}</span>
              </div>
              <div v-if="detail.deathday" class="info-item">
                <span class="info-label">逝世</span>
                <span class="info-value">{{ detail.deathday }}</span>
              </div>
              <div v-if="detail.place_of_birth" class="info-item">
                <span class="info-label">出生地</span>
                <span class="info-value">{{ detail.place_of_birth }}</span>
              </div>
            </div>

            <div v-if="detail.also_known_as?.length" class="also-known">
              <span class="also-label">别名:</span>
              <span class="also-values">{{ detail.also_known_as.slice(0, 5).join(' / ') }}</span>
            </div>
          </div>
        </div>

        <div class="body-content">
          <div v-if="detail.biography" class="biography-section">
            <h3>简介</h3>
            <p class="biography-text">{{ detail.biography }}</p>
          </div>

          <div v-if="detail.known_for?.length" class="credits-section">
            <h3><n-icon><StarIcon /></n-icon> 知名作品</h3>
            <n-scrollbar x-scrollable>
              <div class="credits-scroller">
                <div v-for="c in detail.known_for" :key="c.id" class="credit-card" @click="handleTmdbClick(c)">
                  <div class="credit-poster">
                    <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
                  </div>
                  <div class="credit-info">
                    <div class="credit-title" :title="c.title || c.name">{{ c.title || c.name }}</div>
                    <div class="credit-year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
                  </div>
                </div>
              </div>
            </n-scrollbar>
          </div>

          <div v-if="credits.cast?.length" class="credits-section">
            <h3><n-icon><MovieIcon /></n-icon> 参演作品</h3>
            <n-scrollbar x-scrollable>
              <div class="credits-scroller">
                <div v-for="c in credits.cast" :key="c.id" class="credit-card" @click="handleTmdbClick(c)">
                  <div class="credit-poster">
                    <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
                  </div>
                  <div class="credit-info">
                    <div class="credit-title" :title="c.title || c.name">{{ c.title || c.name }}</div>
                    <div class="credit-character" v-if="c.character">{{ c.character }}</div>
                    <div class="credit-year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
                  </div>
                </div>
              </div>
            </n-scrollbar>
          </div>

          <div v-if="credits.crew?.length" class="credits-section">
            <h3><n-icon><PersonIcon /></n-icon> 制作作品</h3>
            <n-scrollbar x-scrollable>
              <div class="credits-scroller">
                <div v-for="c in credits.crew" :key="c.id + c.job" class="credit-card" @click="handleTmdbClick(c)">
                  <div class="credit-poster">
                    <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
                  </div>
                  <div class="credit-info">
                    <div class="credit-title" :title="c.title || c.name">{{ c.title || c.name }}</div>
                    <div class="credit-job" v-if="c.job">{{ c.job }}</div>
                    <div class="credit-year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
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
.person-detail-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--app-bg-color), transparent var(--app-layout-opacity, 0%));
}

.page-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--app-border-light);
}

.loading-box { padding: 40px; }

.detail-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header-content { position: relative; z-index: 2; padding: 30px 32px; display: flex; gap: 24px; width: 100%; }
.main-profile { 
  width: 180px; aspect-ratio: 2/3; 
  border-radius: var(--card-border-radius, 8px); 
  box-shadow: 0 8px 24px var(--shadow-heavy); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; background: var(--bg-primary); 
}
.main-profile :deep(img) { width: 100%; height: 100%; object-fit: cover; }

.info-col { flex-grow: 1; text-shadow: 0 2px 4px var(--shadow-xheavy); }
.title-row { display: flex; align-items: center; gap: 12px; }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--text-primary); line-height: 1.2; }
.original-name { font-size: 14px; color: var(--text-tertiary); margin-bottom: 8px; }
.meta-tags { margin-bottom: 15px; }
.info-grid { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 15px; }
.info-item { display: flex; align-items: center; gap: 6px; cursor: default; }
.info-label { font-size: 12px; color: var(--text-tertiary); }
.info-value { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.info-value.link { color: var(--n-primary-color); cursor: pointer; }
.info-value.link:hover { text-decoration: underline; }

.also-known { font-size: 12px; color: var(--text-tertiary); margin-top: 8px; }
.also-label { margin-right: 4px; }
.also-values { color: var(--text-secondary); }

.body-content { padding: 0 32px 32px 32px; }
.biography-section { margin-bottom: 24px; }
.biography-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; }
.biography-text { color: var(--text-secondary); line-height: 1.8; font-size: 14px; text-align: justify; white-space: pre-wrap; }

.credits-section { margin-bottom: 24px; }
.credits-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; display: flex; align-items: center; gap: 6px; }
.credits-scroller { display: flex; gap: 16px; padding-bottom: 8px; }
.credit-card { min-width: 120px; width: 120px; display: flex; flex-direction: column; cursor: pointer; transition: transform 0.2s; }
.credit-card:hover { transform: translateY(-4px); }
.credit-poster { 
  width: 120px; aspect-ratio: 2/3;
  border-radius: var(--card-border-radius, 6px); overflow: hidden; 
  border: 1px solid var(--app-border-light); 
  margin-bottom: 8px; background: var(--app-surface-inner); 
}
.credit-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.credit-info { text-align: center; }
.credit-title { font-size: 13px; color: var(--text-primary); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.credit-character { font-size: 11px; color: var(--n-primary-color); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.credit-job { font-size: 11px; color: var(--n-warning-color); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.credit-year { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }
</style>
