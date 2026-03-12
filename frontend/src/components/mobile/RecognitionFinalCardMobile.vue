<script setup lang="ts">
import { NCard, NIcon, NImage, NText, NDivider } from 'naive-ui'
import { FlagOutlined as FinalIcon } from '@vicons/material'
import { useRecognitionFinal } from '../../composables/components/useRecognitionFinal'

const {
  title, poster, category, tmdb_id, release_date, secondary_category, origin_country,
  resolution, v_encode, v_effect, a_encode,
  year, season, episode, source,
  subtitle, team, processed_name, filename,
  getImg
} = useRecognitionFinal()
</script>

<template>
  <n-card bordered class="final-card-mobile">
    <template #header>
      <div class="header-content">
        <n-icon size="20" class="primary-icon"><FinalIcon /></n-icon>
        <span class="header-text">识别结论</span>
      </div>
    </template>

    <div class="mobile-layout">
      <!-- 顶部标题与海报并排 -->
      <div class="top-row">
        <div class="poster-side">
          <n-image v-if="poster" :src="getImg(poster)" width="100" class="poster-img" preview-disabled />
          <div v-else class="poster-placeholder">无海报</div>
        </div>
        <div class="title-side">
          <div class="title-text">{{ title }}</div>
          <div class="meta-row">
            <span class="p-tag tag-green">{{ category }}</span>
            <span v-if="secondary_category && secondary_category !== '-'" class="p-tag tag-blue">{{ secondary_category }}</span>
          </div>
          <div class="date-id-row">
            <span v-if="release_date" class="date">📅 {{ release_date }}</span>
            <span class="tmdb-id">ID: {{ tmdb_id }}</span>
          </div>
        </div>
      </div>

      <n-divider dashed style="margin: 12px 0" />

      <!-- 核心参数 Grid -->
      <div class="flex-info-grid">
        <div class="fig-item"><div class="fig-l">年份</div><div class="fig-v">{{ year }}</div></div>
        <div class="fig-item"><div class="fig-l">季号</div><div class="fig-v">{{ season }}</div></div>
        <div class="fig-item"><div class="fig-l">集数</div><div class="fig-v">{{ episode }}</div></div>
        <div class="fig-item"><div class="fig-l">来源</div><div class="fig-v">{{ source }}</div></div>
      </div>

      <!-- 技术规格 -->
      <div class="specs-row">
        <span v-if="resolution" class="p-badge">{{ resolution }}</span>
        <span v-if="v_encode" class="p-badge blue">{{ v_encode }}</span>
        <span v-if="a_encode" class="p-badge blue">{{ a_encode }}</span>
      </div>

      <!-- 详细信息列表 -->
      <div class="details-list">
        <div class="d-row"><span class="d-l">制作组:</span><span class="d-v team">{{ team }}</span></div>
        <div class="d-row"><span class="d-l">字幕:</span><span class="d-v">{{ subtitle }}</span></div>
        <div class="d-row"><span class="d-l">原产地:</span><span class="d-v">{{ origin_country || '-' }}</span></div>
        <div class="d-row"><span class="d-l">平台:</span><span class="d-v">{{ platform || '-' }}</span></div>
        <div class="d-row"><span class="d-l">特效:</span><span class="d-v">{{ v_effect || '-' }}</span></div>
        <div class="d-row"><span class="d-l">处理后:</span><span class="d-v mono">{{ processed_name }}</span></div>
        <div class="d-row"><span class="d-l">原始名:</span><span class="d-v mono filename">{{ filename }}</span></div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.final-card-mobile { border-radius: 12px; background: var(--bg-surface); }
.header-content { display: flex; align-items: center; gap: 8px; }
.primary-icon { color: var(--n-primary-color); }
.header-text { font-weight: bold; font-size: 14px; }

.top-row { display: flex; gap: 12px; }
.poster-side { flex-shrink: 0; }
.poster-img :deep(img) { border-radius: 6px; }
.poster-placeholder { width: 100px; height: 140px; background: var(--bg-primary); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 10px; color: var(--text-muted); }

.title-side { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.title-text { font-size: 18px; font-weight: 900; color: var(--text-primary); line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

.meta-row { display: flex; gap: 4px; flex-wrap: wrap; }
.p-tag { padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.tag-green { color: var(--color-success); background: var(--color-success-bg); border: 1px solid var(--success-strong); }
.tag-blue { color: var(--color-info); background: var(--color-info-bg); border: 1px solid var(--info-strong); }

.date-id-row { display: flex; flex-direction: column; gap: 2px; }
.date { font-size: 10px; color: var(--n-primary-color); font-weight: 500; }
.tmdb-id { font-family: monospace; font-size: 10px; color: var(--text-muted); }

.flex-info-grid { display: flex; border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255, var(--border-light-alpha)); margin-bottom: 12px; }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; background: var(--bg-primary); padding: 8px 2px; border-right: 1px solid rgba(255,255,255, var(--border-light-alpha)); }
.fig-item:last-child { border-right: none; }
.fig-l { font-size: 9px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 2px; }
.fig-v { font-weight: bold; font-size: 14px; color: var(--n-primary-color); }

.specs-row { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 12px; }
.p-badge { padding: 1px 4px; border-radius: 3px; font-size: 10px; background: var(--bg-surface); color: var(--text-tertiary); border: 1px solid rgba(255,255,255, var(--border-medium-alpha)); }
.p-badge.blue { color: var(--n-info-color); }

.details-list { display: flex; flex-direction: column; gap: 6px; }
.d-row { display: flex; gap: 8px; font-size: 12px; }
.d-l { color: var(--text-muted); width: 50px; flex-shrink: 0; }
.d-v { color: var(--text-secondary); word-break: break-all; }
.d-v.team { color: var(--n-success-color); font-weight: bold; }
.d-v.mono { font-family: monospace; font-size: 11px; color: var(--n-warning-color); }
.d-v.filename { opacity: var(--opacity-secondary); }
</style>