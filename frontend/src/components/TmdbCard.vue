<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  item: any
  isSubscribed?: boolean
}>()

const emit = defineEmits(['click'])

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const imgError = ref(false)

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
      <img
        v-if="!imgError"
        :src="getImg(item.poster_path)"
        loading="lazy"
        decoding="async"
        @error="imgError = true"
      />
      <img v-else src="/favicon.svg" />
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
  transition: transform var(--transition-fast);
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
  /* 跳过不可见内容的渲染，大幅减少切换时的渲染开销 */
  content-visibility: auto;
  contain-intrinsic-size: 225px;
}
.tmdb-card:hover {
  transform: translateY(-5px);
}
.tmdb-card:active {
  transform: scale(0.95);
}

.poster-wrapper {
  width: 100%;
  aspect-ratio: 2/3;
  border-radius: var(--radius-xl);
  overflow: hidden;
  position: relative;
  background: var(--bg-tertiary);
  box-shadow: var(--shadow-md);
  margin-bottom: var(--space-2);
}
.poster-wrapper img { 
  width: 100%; 
  height: 100%; 
  object-fit: cover; 
}

.rating-badge { 
  position: absolute; 
  top: 6px; 
  right: 6px; 
  background: var(--bg-overlay); 
  color: var(--color-warning); 
  padding: 2px 6px; 
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
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
  font-size: var(--text-xs);
  font-weight: bold;
}

.media-info { flex-grow: 1; display: flex; flex-direction: column; padding: 0 2px; }
.media-title {
  font-size: var(--text-lg);
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--text-secondary);
}
.media-date { font-size: var(--text-base); color: var(--text-tertiary); }
</style>