<script setup lang="ts">
/**
 * RecognitionTmdbCard - TMDB 原始详情卡片
 *
 * TMDB 原始详情卡片，通过 CSS 适配移动端
 */
import { NCard, NIcon, NImage, NTag } from 'naive-ui'
import {
  CloudIcon as RemoteIcon
} from '@heroicons/vue/24/outline'
import { useRecognitionTmdb } from '../composables/components/useRecognitionTmdb'

const { tmdb, getImg } = useRecognitionTmdb()
</script>

<template>
  <n-card v-if="tmdb" bordered title="TMDB 原始详情" size="small" class="sub-card">
    <template #header-extra><n-icon style="color: var(--n-warning-color)" size="20"><RemoteIcon /></n-icon></template>

    <div class="tmdb-main-layout">
      <div class="tmdb-poster-side">
        <n-image v-if="tmdb.poster_path" :src="getImg(String(tmdb.poster_path))" width="80" class="small-poster" preview-disabled />
        <div v-else class="small-no-poster">N/A</div>
      </div>

      <div class="tmdb-info-side">
        <div class="tmdb-info-top">
          <span class="tmdb-title">{{ String(tmdb.title || '无标题') }}</span>
          <n-tag v-if="tmdb.category" size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">{{ tmdb.category }}</n-tag>
        </div>

        <div class="tmdb-meta-line">
          <span class="tmdb-date">{{ String(tmdb.release_date || '未知日期') }}</span>
          <span class="tmdb-id-badge">ID: {{ tmdb.id }}</span>
        </div>

        <div class="tmdb-overview-box">
          <div class="overview-text">{{ String(tmdb.overview || '暂无剧情简介') }}</div>
        </div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.sub-card {
  flex: 1;
  min-width: 0;
  background: var(--bg-surface);
  border-radius: var(--card-border-radius, 8px);
}
.tmdb-main-layout { display: flex; gap: var(--space-4); }
.tmdb-poster-side { flex-shrink: 0; }
.small-poster { border-radius: var(--radius-sm); box-shadow: 0 4px 12px var(--shadow-medium); }
.small-no-poster {
  width: 80px; height: 120px;
  background: var(--bg-primary);
  display: flex; align-items: center; justify-content: center;
  font-size: var(--text-2xs); color: var(--text-muted);
  border-radius: var(--radius-sm);
  border: 1px dashed var(--app-border-light);
}
.tmdb-info-side { flex-grow: 1; min-width: 0; display: flex; flex-direction: column; }
.tmdb-info-top { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-2); margin-bottom: var(--space-1); }
.tmdb-title { font-weight: bold; font-size: var(--text-lg); color: var(--n-warning-color); line-height: 1.2; }
.tmdb-meta-line { font-size: var(--text-xs); color: var(--text-muted); display: flex; gap: var(--space-3); margin-bottom: var(--space-2); }
.tmdb-id-badge { font-family: monospace; opacity: var(--opacity-primary); }
.tmdb-overview-box { background: var(--bg-primary); padding: var(--space-2); border-radius: var(--radius-sm); flex-grow: 1; }
.overview-text {
  font-size: var(--text-sm); color: var(--text-tertiary); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
  font-style: italic;
}

/* === 移动端适配 === */
@media (max-width: 767px) {
  .sub-card { background: var(--app-surface-inner); }
  .tmdb-main-layout { gap: var(--space-3); }
  .small-poster :deep(img),
  .small-no-poster { width: 60px !important; }
  .small-no-poster { height: 90px; }
  .tmdb-title { font-size: var(--text-md); }
  .tmdb-meta-line { font-size: var(--text-2xs); gap: var(--space-2); }
  .overview-text { font-size: var(--text-xs); -webkit-line-clamp: 3; line-height: 1.3; }
}
</style>
