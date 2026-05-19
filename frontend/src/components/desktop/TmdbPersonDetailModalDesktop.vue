<script setup lang="ts">
import { ref } from 'vue'
import { 
  NModal, NCard, NImage, NSpace, NTag, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as PersonIcon,
  MovieOutlined as MovieIcon
} from '@vicons/material'
import { useTmdbPersonDetail } from '../../composables/components/useTmdbPersonDetail'
import TmdbDetailModalDesktop from './TmdbDetailModalDesktop.vue'

const props = defineProps<{
  show: boolean
  personId: string | number
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  detail,
  credits,
  getProfile,
  getPoster,
  handleClose,
  openExternal,
  openImdb,
  genderText,
  calculateAge,
  renderReady
} = useTmdbPersonDetail(props, emit)

const tmdbDetailShow = ref(false)
const selectedTmdbId = ref<string | number | null>(null)
const selectedMediaType = ref<'movie' | 'tv'>('tv')
const selectedInitialData = ref<any>(null)

const openTmdbDetail = (item: any) => {
  if (!item?.id) return
  selectedTmdbId.value = item.id
  selectedMediaType.value = item.media_type || 'tv'
  selectedInitialData.value = item
  tmdbDetailShow.value = true
}
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="max-width: 1000px; width: 95%; height: 96vh;" display-directive="show">
    <n-card class="person-detail-modal" content-style="padding: 0; display: flex; flex-direction: column; height: 100%;" :bordered="false" size="huge" role="dialog">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="400px" width="100%" />
      </div>

      <div v-else-if="detail" class="detail-container" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <n-scrollbar style="flex: 1;">
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
                  <div v-for="c in detail.known_for" :key="c.id" class="credit-card" @click="openTmdbDetail(c)">
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
                  <div v-for="c in credits.cast" :key="c.id" class="credit-card" @click="openTmdbDetail(c)">
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
                  <div v-for="c in credits.crew" :key="c.id + c.job" class="credit-card" @click="openTmdbDetail(c)">
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
        </n-scrollbar>
      </div>
    </n-card>
  </n-modal>

  <TmdbDetailModalDesktop 
    v-model:show="tmdbDetailShow" 
    :tmdb-id="selectedTmdbId || 0" 
    :media-type="selectedMediaType"
    :initial-data="selectedInitialData"
  />
</template>

<style scoped>
.person-detail-modal { background: var(--app-bg-color); overflow: hidden; border-radius: var(--card-border-radius, 12px); }
.loading-box { padding: 40px; }

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
