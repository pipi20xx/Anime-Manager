<script setup lang="ts">
/**
 * RecognitionRawCard - 本地解析元数据卡片
 *
 * 本地解析元数据卡片，通过 CSS 适配移动端
 */
import { NCard, NIcon, NDivider } from 'naive-ui'
import {
  ServerIcon as LocalIcon
} from '@heroicons/vue/24/outline'
import { useRecognitionRaw } from '../composables/components/useRecognitionRaw'

const { raw, safeGet } = useRecognitionRaw()
</script>

<template>
  <n-card bordered title="本地解析元数据" size="small" class="sub-card">
    <template #header-extra><n-icon class="local-icon" size="20"><LocalIcon /></n-icon></template>

    <div class="raw-data-content">
      <div class="raw-title-box">
        <div class="raw-main">{{ raw.cn_name || raw.en_name || '未识别标题' }}</div>
        <div v-if="raw.cn_name && raw.en_name" class="raw-sub">{{ raw.en_name }}</div>
      </div>

      <n-divider dashed style="margin: 12px 0" />

      <div class="raw-specs-grid">
        <div class="rs-item">
          <span class="rs-label">季 / 集</span>
          <span class="rs-value primary">S{{ raw.begin_season || 1 }} / E{{ raw.begin_episode || '-' }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">制作组</span>
          <span class="rs-value warning">{{ safeGet(raw.resource_team) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">介质来源</span>
          <span class="rs-value">{{ safeGet(raw.resource_type) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">分辨率</span>
          <span class="rs-value success">{{ safeGet(raw.resource_pix) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">视频编码</span>
          <span class="rs-value info">{{ safeGet(raw.video_encode) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">音频编码</span>
          <span class="rs-value info">{{ safeGet(raw.audio_encode) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">视频特效</span>
          <span class="rs-value">{{ safeGet(raw.video_effect) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">字幕语言</span>
          <span class="rs-value">{{ safeGet(raw.subtitle_lang) }}</span>
        </div>
        <div class="rs-item">
          <span class="rs-label">发布平台</span>
          <span class="rs-value warning">{{ safeGet(raw.resource_platform) }}</span>
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
.raw-main { font-weight: bold; font-size: var(--text-md); color: var(--text-secondary); }
.raw-sub { font-size: var(--text-sm); color: var(--text-tertiary); font-style: italic; font-family: monospace; margin-top: var(--space-1); }

.raw-specs-grid { display: flex; flex-direction: column; gap: var(--space-2); }
.rs-item { display: flex; align-items: center; justify-content: space-between; font-size: var(--text-base); }
.rs-label { color: var(--text-muted); }
.rs-value { font-weight: bold; color: var(--text-secondary); }
.rs-value.primary { color: var(--n-info-color); }
.rs-value.warning { color: var(--n-warning-color); }
.rs-value.success { color: var(--n-primary-color); }
.rs-value.info { color: var(--n-success-color); }

.local-icon { color: var(--n-primary-color); }

/* === 移动端适配: 规格 2 列网格 === */
@media (max-width: 767px) {
  .sub-card { background: var(--app-surface-inner); }
  .raw-main { font-size: var(--text-sm); }
  .raw-specs-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }
  .rs-item { font-size: var(--text-xs); }
}
</style>
