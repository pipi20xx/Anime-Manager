<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  NImage, NSpace, NTag, NButton, NIcon, NSkeleton
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
  <div class="m-page m-page-safe-bottom">
    <!-- Header -->
    <div class="m-header m-header-plain">
      <div class="m-header-left">
        <n-button text size="small" @click="goBack">
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
      <n-skeleton height="200px" width="100%" style="border-radius: var(--m-radius-lg); margin-bottom: var(--m-spacing-lg)" />
      <n-skeleton height="20px" width="60%" style="margin-bottom: var(--m-spacing-md)" />
      <n-skeleton height="16px" width="40%" style="margin-bottom: var(--m-spacing-lg)" />
      <n-skeleton height="80px" width="100%" style="border-radius: var(--m-radius-lg)" />
    </div>

    <!-- Content -->
    <div v-else-if="detail" class="m-page-scrollable">
      <!-- Hero -->
      <div class="m-detail-hero" style="min-height: auto; padding: var(--m-spacing-lg) 0;">
        <div class="m-detail-hero-content" style="padding: 0 var(--m-spacing-lg); align-items: flex-start;">
          <div class="m-detail-poster" style="width: 110px;">
            <n-image :src="getProfile(detail.profile_path)" object-fit="cover" preview-disabled style="width: 100%; aspect-ratio: 2/3;" />
          </div>
          <div class="m-detail-info">
            <h1 class="m-detail-title">{{ detail.name }}</h1>
            <div v-if="detail.original_name && detail.original_name !== detail.name" style="font-size: var(--m-text-sm); color: var(--text-muted); margin-top: var(--m-spacing-xs);">
              {{ detail.original_name }}
            </div>
            <div class="m-detail-meta" style="flex-wrap: wrap;">
              <n-tag v-if="detail.known_for_department" type="info" size="tiny" round>
                {{ detail.known_for_department }}
              </n-tag>
              <n-tag v-if="detail.popularity" type="warning" round size="tiny">
                <template #icon><n-icon><StarIcon /></n-icon></template>
                {{ detail.popularity.toFixed(1) }}
              </n-tag>
              <n-tag :bordered="false" size="tiny" style="background: var(--app-surface-card-mixed)">
                <template #icon><n-icon><PersonIcon /></n-icon></template>
                {{ genderText(detail.gender) }}
              </n-tag>
              <n-tag v-if="detail.birthday" :bordered="false" size="tiny" style="background: var(--app-surface-card-mixed)">
                <template #icon><n-icon><DateIcon /></n-icon></template>
                {{ calculateAge(detail.birthday, detail.deathday) }}岁
              </n-tag>
            </div>
          </div>
        </div>
      </div>

      <div class="m-detail-body">
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
            <div v-if="detail.birthday" class="meta-row">
              <span class="meta-label">生日</span>
              <span class="meta-value">{{ detail.birthday }}</span>
            </div>
            <div v-if="detail.deathday" class="meta-row">
              <span class="meta-label">逝世</span>
              <span class="meta-value">{{ detail.deathday }}</span>
            </div>
            <div v-if="detail.place_of_birth" class="meta-row">
              <span class="meta-label">出生地</span>
              <span class="meta-value">{{ detail.place_of_birth }}</span>
            </div>
            <div v-if="detail.also_known_as?.length" class="meta-row">
              <span class="meta-label">别名</span>
              <span class="meta-value">{{ detail.also_known_as.slice(0, 3).join(' / ') }}</span>
            </div>
          </div>
        </div>

        <!-- Biography -->
        <div v-if="detail.biography" class="m-detail-section">
          <h3 class="m-detail-section-title">简介</h3>
          <p style="color: var(--text-secondary); line-height: 1.8; font-size: var(--m-text-md); margin: 0; white-space: pre-wrap;">
            {{ detail.biography }}
          </p>
        </div>

        <!-- Known For -->
        <div v-if="detail.known_for?.length" class="m-detail-section">
          <h3 class="m-detail-section-title"><n-icon><StarIcon /></n-icon> 知名作品</h3>
          <div class="m-h-scroll">
            <div v-for="c in detail.known_for" :key="c.id" class="credit-card-mobile" @click="handleTmdbClick(c)">
              <div class="credit-poster-mobile">
                <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
              </div>
              <div class="credit-title-mobile">{{ c.title || c.name }}</div>
              <div class="credit-year-mobile">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
            </div>
          </div>
        </div>

        <!-- Cast Credits -->
        <div v-if="credits.cast?.length" class="m-detail-section">
          <h3 class="m-detail-section-title"><n-icon><MovieIcon /></n-icon> 参演作品</h3>
          <div class="m-h-scroll">
            <div v-for="c in credits.cast" :key="c.id" class="credit-card-mobile" @click="handleTmdbClick(c)">
              <div class="credit-poster-mobile">
                <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
              </div>
              <div class="credit-title-mobile">{{ c.title || c.name }}</div>
              <div v-if="c.character" class="credit-role-mobile">{{ c.character }}</div>
              <div class="credit-year-mobile">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
            </div>
          </div>
        </div>

        <!-- Crew Credits -->
        <div v-if="credits.crew?.length" class="m-detail-section">
          <h3 class="m-detail-section-title"><n-icon><PersonIcon /></n-icon> 制作作品</h3>
          <div class="m-h-scroll">
            <div v-for="c in credits.crew" :key="c.id + c.job" class="credit-card-mobile" @click="handleTmdbClick(c)">
              <div class="credit-poster-mobile">
                <n-image :src="getPoster(c.poster_path)" object-fit="cover" preview-disabled />
              </div>
              <div class="credit-title-mobile">{{ c.title || c.name }}</div>
              <div v-if="c.job" class="credit-role-mobile credit-job">{{ c.job }}</div>
              <div class="credit-year-mobile">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
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

.credit-card-mobile {
  min-width: 110px;
  width: 110px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
}

.credit-poster-mobile {
  width: 110px;
  aspect-ratio: 2/3;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  margin-bottom: var(--m-spacing-sm);
  background: var(--app-surface-card-mixed);
}

.credit-poster-mobile :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.credit-title-mobile {
  font-size: var(--m-text-sm);
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.credit-role-mobile {
  font-size: var(--m-text-xs);
  color: var(--n-primary-color);
  margin-top: var(--m-spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.credit-role-mobile.credit-job {
  color: var(--n-warning-color);
}

.credit-year-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  margin-top: var(--m-spacing-xs);
}
</style>
