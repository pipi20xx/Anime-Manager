<script setup lang="ts">
import { defineProps } from 'vue'
import { NImage } from 'naive-ui'

const props = defineProps<{
  item: any
  isSubscribed?: boolean
}>()

const emit = defineEmits(['click'])

// 处理图片 URL (兼容 http/https 和 403 代理)
const getImg = (path: string) => {
  if (!path) return ''
  if (path.startsWith('//')) return `https:${path}`
  // 如果已经是本地代理路径（TMDB 或 Bangumi）
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  
  // 强制 HTTPS
  let url = path
  if (path.startsWith('http:')) url = path.replace('http:', 'https:')
  
  return url
}
</script>

<template>
  <div class="bgm-card" @click="emit('click', item)">
    <div class="bgm-cover">
      <n-image 
        :src="getImg(item.image || item.poster_path)" 
        object-fit="cover" 
        lazy 
        preview-disabled 
        fallback-src="/favicon.svg" 
      />
    </div>
    <div class="bgm-info">
      <div class="bgm-title" :title="item.title || item.name">{{ item.title || item.name }}</div>
      <div class="bgm-orig">
        {{ item.original_title || item.original_name || (item.first_air_date || item.release_date || '').slice(0, 10) }}
      </div>
      <div class="bgm-footer">
        <div class="bgm-score" v-if="(item.rating || item.vote_average) > 0">
          ⭐ {{ typeof item.rating === 'object' ? item.rating?.score : (item.rating || item.vote_average)?.toFixed(1) }}
        </div>
        <div v-else></div>
        <div class="bgm-sub-label" v-if="isSubscribed">已订阅</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bgm-card { 
  background: transparent; 
  transition: all 0.3s ease; 
  cursor: pointer; 
  display: flex; 
  flex-direction: column;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}
.bgm-card:hover { 
  transform: translateY(-6px); 
}
.bgm-cover { 
  width: 100%;
  aspect-ratio: 2/3; 
  border-radius: 12px; 
  overflow: hidden; 
  margin-bottom: 8px; 
  background: var(--bg-primary); 
  position: relative; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-light);
}
.bgm-cover :deep(.n-image) { width: 100%; height: 100%; display: flex; }
.bgm-cover :deep(img) { 
  width: 100% !important; 
  height: 100% !important; 
  object-fit: cover !important; 
}

.bgm-info { flex-grow: 1; display: flex; flex-direction: column; padding: 0 2px; }

.bgm-title { 
  font-size: 14px; 
  font-weight: 600; 
  color: var(--text-secondary); 
  white-space: nowrap; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  line-height: 1.4; 
}
.bgm-orig { 
  font-size: 11px; 
  color: var(--n-text-color-3); 
  white-space: nowrap; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  margin-top: 2px; 
}

.bgm-footer { 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    margin-top: auto; 
    padding-top: 6px; 
    height: 24px;
}
.bgm-score { font-size: 11px; color: var(--color-warning); font-weight: bold; }
.bgm-sub-label {
    background: var(--bg-primary); color: var(--n-primary-color); 
    padding: 1px 6px; border-radius: 4px; 
    font-size: 10px; font-weight: bold;
    border: 1px solid var(--border-medium);
}
</style>