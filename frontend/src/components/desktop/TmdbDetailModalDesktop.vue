<script setup lang="ts">
import { 
  NModal, NCard, NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  AddCircleOutlined as SubIcon,
  PersonOutlined as CastIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import { useTmdbDetail } from '../../composables/components/useTmdbDetail'

const props = defineProps<{
  show: boolean
  tmdbId: string | number
  mediaType: 'movie' | 'tv' | string
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  detail,
  isSubscribed,
  displayGenres,
  getPoster,
  getBackdrop,
  handleClose,
  openExternal,
  handleSubscribe,
  handleSearch
} = useTmdbDetail(props, emit)
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="max-width: 1000px; width: 95%; height: 96vh;">
    <n-card class="tmdb-detail-modal" content-style="padding: 0; display: flex; flex-direction: column; height: 100%;" :bordered="false" size="huge" role="dialog">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="400px" width="100%" />
      </div>

      <div v-else-if="detail" class="detail-container" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <n-scrollbar style="flex: 1;">
          <!-- Header -->
          <div class="backdrop-box">
              <div class="backdrop-img" :style="{ backgroundImage: `url(${getBackdrop(detail.backdrop_path)})` }"></div>
              <div class="backdrop-gradient"></div>
              <div class="header-content">
                  <div class="poster-col">
                      <n-image :src="getPoster(detail.poster_path)" class="main-poster" object-fit="cover" />
                  </div>
                  <div class="info-col">
                      <h1 class="title">{{ detail.title || detail.name }}</h1>
                      <div class="original-title">{{ detail.original_title || detail.original_name }}</div>
                      <div v-if="detail.tagline" class="tagline">"{{ detail.tagline }}"</div>
                      
                      <n-space class="meta-tags" align="center">
                          <n-tag type="warning" round size="small">
                              <template #icon><n-icon><StarIcon /></n-icon></template>
                              {{ detail.vote_average?.toFixed(1) }}
                          </n-tag>
                          <n-tag :bordered="false" color="#333" size="small">
                              <template #icon><n-icon><DateIcon /></n-icon></template>
                              {{ detail.release_date || detail.first_air_date }}
                          </n-tag>
                          <n-tag v-if="detail.number_of_seasons" type="info" size="small" round>
                              {{ detail.number_of_seasons }} 季
                          </n-tag>
                      </n-space>

                      <div class="actions">
                          <n-button :type="isSubscribed ? 'secondary' : 'primary'" size="small" @click="handleSubscribe" :disabled="isSubscribed">
                              <template #icon><n-icon><SubIcon /></n-icon></template>
                              {{ isSubscribed ? '已在订阅中' : '订阅/追番' }}
                          </n-button>
                          <n-button secondary size="small" @click="handleSearch">
                              <template #icon><n-icon><SearchIcon /></n-icon></template>
                              搜资源
                          </n-button>
                          <n-button secondary circle size="small" @click="openExternal">
                              <template #icon><n-icon><LinkIcon /></n-icon></template>
                          </n-button>
                      </div>
                  </div>
              </div>
          </div>

          <!-- Body -->
          <div class="body-content">
              <div v-if="displayGenres.length > 0" class="genres-row">
                  <n-space>
                      <n-tag v-for="g in displayGenres" :key="g" type="primary" size="tiny" :bordered="false" round>
                          {{ g }}
                      </n-tag>
                  </n-space>
              </div>

              <div class="overview-section">
                  <h3>简介</h3>
                  <p class="overview-text">{{ detail.overview || '暂无简介' }}</p>
              </div>

              <div v-if="detail.cast?.length" class="cast-section">
                  <h3><n-icon><CastIcon /></n-icon> 演职员</h3>
                  <n-scrollbar x-scrollable>
                      <div class="cast-scroller">
                          <div v-for="c in detail.cast" :key="c.actor + c.character" class="cast-card">
                              <div class="cast-avatar">
                                  <n-image :src="getPoster(c.image)" object-fit="cover" preview-disabled />
                              </div>
                              <div class="cast-names">
                                  <div class="actor-name" :title="c.actor">{{ c.actor }}</div>
                              </div>
                          </div>
                      </div>
                  </n-scrollbar>
              </div>

              <div v-if="detail.seasons?.length" class="seasons-section">
                  <h3>季度信息</h3>
                  <n-scrollbar x-scrollable>
                      <div class="season-scroller">
                          <div v-for="s in detail.seasons" :key="s.id" class="season-card">
                              <div class="s-poster">
                                  <n-image :src="getPoster(s.poster_path)" object-fit="cover" preview-disabled />
                              </div>
                              <div class="s-info">
                                  <div class="s-name">{{ s.name }}</div>
                                  <div class="s-ep">{{ s.episode_count }} 集</div>
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
</template>

<style scoped>
.tmdb-detail-modal { background: var(--app-bg-color); overflow: hidden; border-radius: var(--card-border-radius, 12px); }
.loading-box { padding: 40px; }

.backdrop-box { position: relative; height: 220px; }
.backdrop-img { position: absolute; inset: 0; background-size: cover; background-position: center; opacity: 0.3; filter: blur(30px); transform: scale(1.2); }
.backdrop-gradient { position: absolute; inset: 0; background: linear-gradient(to top, var(--app-bg-color) 5%, transparent 100%); }

.header-content { position: relative; z-index: 2; padding: 30px 32px 0 32px; display: flex; gap: 20px; width: 100%; }
.main-poster { 
  width: 110px; aspect-ratio: 3/4; 
  border-radius: var(--card-border-radius, 6px); 
  box-shadow: 0 8px 24px rgba(0,0,0,0.5); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; background: #000; 
}
.main-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }

.info-col { flex-grow: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.8); }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--n-text-color-1); line-height: 1.2; }
.original-title { font-size: 13px; color: var(--n-text-color-3); margin-bottom: 4px; }
.tagline { font-size: 14px; font-style: italic; color: var(--n-primary-color); margin-bottom: 12px; opacity: 0.9; }
.meta-tags { margin-bottom: 15px; }
.actions { display: flex; gap: 10px; }

.body-content { padding: 30px 32px 32px 32px; }
.genres-row { margin-bottom: 16px; }
.overview-section { margin-bottom: 20px; }
.overview-section h3 { margin: 0 0 8px 0; color: var(--n-primary-color); font-size: 15px; }
.overview-text { color: var(--n-text-color-2); line-height: 1.6; font-size: 13px; text-align: justify; }

.cast-section { margin-bottom: 24px; }
.cast-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; display: flex; align-items: center; gap: 6px; }
.cast-scroller { display: flex; gap: 16px; padding-bottom: 8px; }
.cast-card { min-width: 80px; width: 80px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.cast-avatar { 
  width: 56px; height: 56px; 
  border-radius: 50%; overflow: hidden; 
  border: 1px solid var(--app-border-light); 
  margin-bottom: 6px; background: var(--app-surface-inner); 
}
.cast-avatar :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.actor-name { font-size: 10px; color: var(--n-text-color-3); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.seasons-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; }
.season-scroller { display: flex; gap: 16px; padding-bottom: 10px; }
.season-card { width: 100px; }
.s-poster { aspect-ratio: 2/3; border-radius: var(--button-border-radius, 6px); overflow: hidden; background: #000; margin-bottom: 6px; border: 1px solid var(--app-border-light); }
.s-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.s-name { font-size: 12px; font-weight: bold; color: var(--n-text-color-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-ep { font-size: 11px; color: var(--n-text-color-3); }
</style>