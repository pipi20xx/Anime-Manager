<script setup lang="ts">
import { defineProps } from 'vue'
import { NImage } from 'naive-ui'

const props = defineProps<{
  item: any
  isSubscribed?: boolean
}>()

const emit = defineEmits(['click'])

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const getImg = (path: string) => {
  if (!path) return ''
  // 如果已经是本地代理路径，直接返回
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
</script>

<template>
  <div class="tmdb-card" @click="emit('click', item)">
    <div class="poster-wrapper">
      <n-image 
        :src="getImg(item.poster_path)" 
        object-fit="cover" 
        lazy 
        preview-disabled 
        fallback-src="/favicon.svg" 
      />
      <!-- Badges overlay for TMDB style -->
      <div class="rating-badge" v-if="item.vote_average > 0">
         {{ item.vote_average.toFixed(1) }}
      </div>
      <div class="sub-badge" v-if="isSubscribed">已订阅</div>
    </div>
    <div class="media-info">
      <div class="media-title" :title="item.title || item.name">{{ item.title || item.name }}</div>
      <div class="media-date">
        {{ (item.first_air_date || item.release_date || '').slice(0, 4) }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.tmdb-card { 
  cursor: pointer; 
  transition: transform 0.2s; 
  display: flex; 
  flex-direction: column;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}
.tmdb-card:hover { 
  transform: translateY(-5px); 
}

.poster-wrapper { 
  width: 100%;
  aspect-ratio: 2/3; 
  border-radius: 12px; 
  overflow: hidden; 
  position: relative; 
  background: var(--bg-tertiary); 
  box-shadow: var(--shadow-md); 
  margin-bottom: 8px; 
}
.poster-wrapper :deep(.n-image) { width: 100%; height: 100%; display: flex; }
.poster-wrapper :deep(img) { 
  width: 100% !important; 
  height: 100% !important; 
  object-fit: cover !important; 
}

.rating-badge { 
  position: absolute; 
  top: 6px; 
  right: 6px; 
  background: var(--bg-overlay); 
  color: var(--color-warning); 
  padding: 2px 6px; 
  border-radius: 4px; 
  font-size: 11px; 
  font-weight: bold; 
  backdrop-filter: blur(4px); 
}

.sub-badge { 
  position: absolute; 
  top: 6px; 
  left: 6px; 
  background: var(--n-primary-color); 
  color: var(--text-primary); 
  padding: 2px 6px; 
  border-radius: 4px; 
  font-size: 10px; 
  font-weight: bold; 
}

.media-info { flex-grow: 1; display: flex; flex-direction: column; padding: 0 2px; }
.media-title { 
  font-size: 14px; 
  font-weight: 600; 
  overflow: hidden; 
  white-space: nowrap; 
  text-overflow: ellipsis; 
  color: var(--text-secondary);
}
.media-date { font-size: 12px; color: var(--n-text-color-3); }
</style>