<script setup lang="ts">
import { NCard, NTag, NIcon, NDivider } from 'naive-ui'
import { StorageOutlined as LocalIcon } from '@vicons/material'
import { useRecognitionRaw } from '../../composables/components/useRecognitionRaw'

const { raw, tags, safeGet } = useRecognitionRaw()
</script>

<template>
  <n-card bordered title="本地解析" size="small" class="sub-card-mobile">
    <template #header-extra><n-icon class="local-icon" size="18"><LocalIcon /></n-icon></template>
    
    <div class="raw-data-content">
      <div class="raw-title-box">
        <div class="raw-main">{{ raw.cn_name || raw.en_name || '未识别标题' }}</div>
      </div>

      <div class="raw-specs-grid mt-3">
        <div class="rs-item"><span class="rs-l">季/集:</span><span class="rs-v primary">S{{ raw.begin_season || 1 }} / E{{ raw.begin_episode || '-' }}</span></div>
        <div class="rs-item"><span class="rs-l">制作组:</span><span class="rs-v warning">{{ safeGet(raw.resource_team) }}</span></div>
        <div class="rs-item"><span class="rs-l">分辨率:</span><span class="rs-v success">{{ safeGet(raw.resource_pix) }}</span></div>
      </div>

      <n-divider dashed style="margin: 8px 0" />

      <div class="raw-tags-cloud">
        <n-tag v-for="tag in tags" :key="String(tag)" size="tiny" tertiary round class="m-tag">
          {{ String(tag) }}
        </n-tag>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.sub-card-mobile { background: var(--bg-surface); border-radius: 8px; }
.raw-main { font-weight: bold; font-size: 14px; color: var(--text-secondary); }

.raw-specs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.rs-item { display: flex; align-items: center; gap: 4px; font-size: 11px; }
.rs-l { color: var(--text-muted); }
.rs-v { color: var(--text-secondary); font-weight: 600; }
.rs-v.primary { color: var(--n-info-color); }
.rs-v.warning { color: var(--n-warning-color); }
.rs-v.success { color: var(--n-primary-color); }

.raw-tags-cloud { display: flex; flex-wrap: wrap; gap: 4px; }
.mt-3 { margin-top: 12px; }
.local-icon { color: var(--n-primary-color); }
</style>