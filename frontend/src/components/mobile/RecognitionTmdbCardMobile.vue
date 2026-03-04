<script setup lang="ts">
import { NCard, NIcon, NImage, NTag } from 'naive-ui'
import { CloudQueueOutlined as RemoteIcon } from '@vicons/material'
import { useRecognitionTmdb } from '../../composables/components/useRecognitionTmdb'

const { tmdb, getImg } = useRecognitionTmdb()
</script>

<template>
  <n-card v-if="tmdb" bordered title="TMDB 详情" size="small" class="sub-card-mobile">
    <template #header-extra><n-icon style="color: var(--n-warning-color)" size="18"><RemoteIcon /></n-icon></template>
    
    <div class="tmdb-main-layout">
      <div class="tmdb-poster-side">
        <n-image v-if="tmdb.poster_path" :src="getImg(String(tmdb.poster_path))" width="60" class="small-poster" preview-disabled />
      </div>

      <div class="tmdb-info-side">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 4px;">
          <div class="tmdb-title">{{ String(tmdb.title || '无标题') }}</div>
          <n-tag v-if="tmdb.category" size="tiny" type="primary" round ghost>{{ tmdb.category }}</n-tag>
        </div>
        <div class="tmdb-meta">
          <span class="tmdb-date">{{ String(tmdb.release_date || '').slice(0,4) }}</span>
          <span class="tmdb-id">ID: {{ tmdb.id }}</span>
        </div>
        <div class="overview-text">{{ String(tmdb.overview || '暂无简介') }}</div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.sub-card-mobile { background: rgba(255,255,255,0.01); border-radius: 8px; }
.tmdb-main-layout { display: flex; gap: 12px; }
.tmdb-poster-side { flex-shrink: 0; }
.small-poster { border-radius: 4px; }

.tmdb-info-side { flex: 1; min-width: 0; }
.tmdb-title { font-weight: bold; font-size: 14px; color: var(--n-warning-color); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tmdb-meta { display: flex; gap: 8px; font-size: 10px; color: #555; margin-bottom: 4px; }
.overview-text { font-size: 11px; color: #777; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-style: italic; }
</style>