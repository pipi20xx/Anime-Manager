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
  SearchOutlined as SearchIcon,
  ArrowBackOutlined as BackIcon
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
  <n-modal :show="show" @update:show="handleClose" style="width: 100%; height: 100vh; margin: 0; border-radius: 0;">
    <div class="mobile-detail-page">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="300px" width="100%" />
      </div>

      <div v-else-if="detail" class="content-wrapper">
        <div class="sticky-header">
           <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="handleClose" class="back-btn">
             <template #icon><n-icon><BackIcon /></n-icon></template>
           </n-button>
        </div>

        <n-scrollbar style="flex: 1;">
          <div class="hero-section">
             <div class="backdrop-layer" :style="{ backgroundImage: `url(${getImg(detail.backdrop_path)})` }"></div>
             <div class="gradient-overlay"></div>
             
             <div class="hero-content">
                <div class="poster-wrapper">
                   <n-image :src="getImg(detail.poster_path)" object-fit="cover" class="hero-poster" />
                </div>
                <div class="hero-info">
                   <h1 class="hero-title">{{ detail.title || detail.name }}</h1>
                   <div class="hero-meta">
                      <n-tag type="warning" size="tiny" round :bordered="false" class="rating-tag">
                         <template #icon><n-icon><StarIcon/></n-icon></template>
                         {{ detail.vote_average?.toFixed(1) }}
                      </n-tag>
                      <span class="meta-date">{{ detail.release_date }}</span>
                   </div>
                </div>
             </div>
          </div>

          <div class="actions-bar">
             <n-button block type="primary" :secondary="isSubscribed" @click="handleSubscribe">
                <template #icon><n-icon><SubIcon/></n-icon></template>
                {{ isSubscribed ? '已订阅' : '订阅此番' }}
             </n-button>
             <n-space justify="space-between" style="width: 100%; margin-top: 12px;">
                <n-button flex="1" secondary @click="triggerGlobalSearch(detail.original_title || detail.title || detail.name)">
                   <template #icon><n-icon><SearchIcon/></n-icon></template> 搜资源
                </n-button>
                <n-button flex="1" secondary @click="openExternal">
                   <template #icon><n-icon><LinkIcon/></n-icon></template> Bangumi
                </n-button>
             </n-space>
          </div>

          <div class="detail-body">
             <div class="genres-scroll" v-if="detail.genres?.length">
                <n-tag v-for="g in detail.genres" :key="g" size="small" round :bordered="false" class="genre-tag">{{ g }}</n-tag>
             </div>

             <div class="section">
                <h3>简介</h3>
                <p class="overview">{{ detail.overview || '暂无简介' }}</p>
             </div>

             <div v-if="detail.tags?.length" class="section">
                <h3>标签</h3>
                <n-space size="small">
                    <n-tag v-for="t in detail.tags" :key="t" size="tiny" :bordered="false" round style="background: rgba(255,255,255,0.05); color: #888">
                        # {{ t }}
                    </n-tag>
                </n-space>
             </div>

             <div class="section" v-if="detail.cast?.length">
                <h3>角色</h3>
                <div class="h-scroller">
                   <div v-for="c in detail.cast" :key="c.character" class="cast-item">
                      <div class="avatar">
                         <img :src="c.image" loading="lazy" />
                      </div>
                      <div class="name">{{ c.character }}</div>
                      <div class="char">{{ c.actor }}</div>
                   </div>
                </div>
             </div>
          </div>
          
          <div style="height: 40px;"></div>
        </n-scrollbar>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.mobile-detail-page { background: var(--app-bg-color); height: 100%; display: flex; flex-direction: column; position: relative; }
.loading-box { padding: 40px; }
.content-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.sticky-header { position: absolute; top: 16px; left: 16px; z-index: 10; }
.back-btn { background: rgba(0,0,0,0.5) !important; color: #fff !important; border: none; backdrop-filter: blur(4px); }

.hero-section { position: relative; height: 320px; display: flex; align-items: flex-end; }
.backdrop-layer { position: absolute; inset: 0; background-size: cover; background-position: center; opacity: 0.6; }
.gradient-overlay { position: absolute; inset: 0; background: linear-gradient(to bottom, transparent 0%, var(--app-bg-color) 100%); }

.hero-content { position: relative; z-index: 2; padding: 0 20px 20px; display: flex; gap: 16px; align-items: flex-end; width: 100%; }
.poster-wrapper { width: 100px; flex-shrink: 0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); }
.hero-poster :deep(img) { width: 100%; display: block; aspect-ratio: 2/3; object-fit: cover; }

.hero-info { flex: 1; min-width: 0; margin-bottom: 4px; }
.hero-title { margin: 0; font-size: 20px; font-weight: 900; color: #fff; line-height: 1.2; text-shadow: 0 2px 4px rgba(0,0,0,0.8); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.hero-meta { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.meta-date { font-size: 12px; color: rgba(255,255,255,0.8); text-shadow: 0 1px 2px rgba(0,0,0,0.8); }
.rating-tag { background: rgba(245, 166, 35, 0.9); color: #000; font-weight: bold; }

.actions-bar { padding: 0 20px 20px; }

.detail-body { padding: 0 20px; }
.genres-scroll { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 16px; margin-bottom: 8px; }
.genre-tag { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); }

.section { margin-bottom: 24px; }
.section h3 { margin: 0 0 12px; font-size: 16px; font-weight: bold; color: var(--n-text-color-1); }
.overview { font-size: 14px; line-height: 1.6; color: var(--n-text-color-2); text-align: justify; }

.h-scroller { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 4px; }
.cast-item { width: 70px; flex-shrink: 0; text-align: center; }
.cast-item .avatar { width: 60px; height: 60px; border-radius: 50%; overflow: hidden; margin: 0 auto 6px; background: #333; }
.cast-item .avatar img { width: 100%; height: 100%; object-fit: cover; }
.cast-item .name { font-size: 11px; color: var(--n-text-color-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.cast-item .char { font-size: 10px; color: var(--n-text-color-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
