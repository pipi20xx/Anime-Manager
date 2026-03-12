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
import { useBangumiDetail } from '../../composables/components/useBangumiDetail'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  subjectId: string | number
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  detail,
  isSubscribed,
  getImg,
  handleClose,
  openExternal,
  handleSubscribe,
  triggerGlobalSearch
} = useBangumiDetail(props, emit)
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="max-width: 1000px; width: 95%; height: 96vh;">
    <n-card class="bgm-detail-modal" content-style="padding: 0; display: flex; flex-direction: column; height: 100%;" :bordered="false" size="huge" role="dialog">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="300px" width="100%" />
      </div>

      <div v-else-if="detail" class="detail-container" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <n-scrollbar style="flex: 1;">
          <!-- Header -->
          <div class="backdrop-box">
              <div class="backdrop-img" :style="{ backgroundImage: `url(${getImg(detail.backdrop_path)})` }"></div>
              <div class="backdrop-gradient"></div>
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
                          <n-button :type="isSubscribed ? 'secondary' : 'primary'" size="small" @click="handleSubscribe" :disabled="isSubscribed">
                              <template #icon><n-icon><SubIcon /></n-icon></template>
                              {{ isSubscribed ? '已在订阅中' : '订阅此番' }}
                          </n-button>
                          <n-button secondary size="small" @click="triggerGlobalSearch(detail.original_title || detail.title || detail.name)">
                              <template #icon><n-icon><SearchIcon /></n-icon></template>
                              搜资源
                          </n-button>
                          <n-button v-bind="getButtonStyle('icon')" size="small" @click="openExternal">
                              <template #icon><n-icon><LinkIcon /></n-icon></template>
                          </n-button>
                      </div>
                  </div>
              </div>
          </div>

          <!-- Body -->
          <div class="body-content">
              <!-- Genres -->
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

              <!-- Cast -->
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
        </n-scrollbar>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
.bgm-detail-modal { background: var(--app-bg-color); overflow: hidden; border-radius: var(--card-border-radius, 12px); }
.loading-box { padding: 40px; }

.backdrop-box { position: relative; height: 220px; }
.backdrop-img { position: absolute; inset: 0; background-size: cover; background-position: center; opacity: var(--opacity-tertiary); filter: blur(30px); transform: scale(1.2); }
.backdrop-gradient { position: absolute; inset: 0; background: linear-gradient(to top, var(--app-bg-color) 5%, transparent 100%); }

.header-content { position: relative; z-index: 2; padding: 30px 32px 0 32px; display: flex; gap: 20px; width: 100%; }
.main-poster { 
  width: 110px; aspect-ratio: 3/4; 
  border-radius: var(--card-border-radius, 6px); 
  box-shadow: 0 8px 24px var(--shadow-heavy); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; background: var(--bg-primary); 
}
.main-poster :deep(img) { width: 100%; height: 100%; object-fit: contain; }

.info-col { flex-grow: 1; text-shadow: 0 2px 4px var(--shadow-xheavy); }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--n-text-color-1); line-height: 1.2; }
.original-title { font-size: 13px; color: var(--n-text-color-3); margin-bottom: 10px; }
.meta-tags { margin-bottom: 15px; }
.actions { display: flex; gap: 10px; }

.body-content { padding: 30px 32px 32px 32px; }
.genres-row { margin-bottom: 16px; }
.overview-section { margin-bottom: 20px; }
.overview-section h3 { margin: 0 0 8px 0; color: var(--n-primary-color); font-size: 15px; }
.overview-text { color: var(--n-text-color-2); line-height: 1.6; font-size: 13px; text-align: justify; }

.tags-section { margin-bottom: 24px; }

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
.char-name { font-size: 11px; font-weight: bold; color: var(--n-text-color-1); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actor-name { font-size: 10px; color: var(--n-text-color-3); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>