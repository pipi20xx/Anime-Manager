<script setup lang="ts">
/**
 * RecognitionRawCard - 本地解析元数据卡片
 *
 * 本地解析元数据卡片，通过 CSS 适配移动端
 */
import { NCard, NTag, NIcon, NDivider } from 'naive-ui'
import { StorageOutlined as LocalIcon } from '@vicons/material'
import { useRecognitionRaw } from '../composables/components/useRecognitionRaw'

const { raw, tags, safeGet } = useRecognitionRaw()
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
      </div>

      <n-divider dashed style="margin: 12px 0" />

      <div class="raw-tags-section">
        <div class="section-mini-title">解析到的标签</div>
        <div class="raw-tags-cloud">
          <n-tag v-for="tag in tags" :key="String(tag)" size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#616161', borderColor: 'transparent' }">
            {{ String(tag) }}
          </n-tag>
          <div v-if="tags.length === 0" class="no-tags">未提取到额外标签</div>
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

.section-mini-title { font-size: var(--text-xs); font-weight: bold; color: var(--text-muted); text-transform: uppercase; margin-bottom: var(--space-2); }
.raw-tags-cloud { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.no-tags { font-size: var(--text-xs); color: var(--text-tertiary); font-style: italic; }
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
  .section-mini-title { font-size: var(--text-2xs); }
}
</style>
