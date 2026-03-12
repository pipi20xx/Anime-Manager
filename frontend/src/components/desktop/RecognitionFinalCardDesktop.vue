<script setup lang="ts">
import { NCard, NIcon, NImage, NText } from 'naive-ui'
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
  <n-card bordered class="final-card-container">
    <template #header>
      <div class="header-content">
        <div class="title-wrap">
          <n-icon size="22" class="primary-icon"><FinalIcon /></n-icon>
          <span class="header-text">最终识别结论</span>
        </div>
      </div>
    </template>

    <div class="main-layout">
      <!-- 海报区 -->
      <div class="poster-box">
        <n-image v-if="poster" :src="getImg(poster)" width="140" class="poster-img" preview-disabled />
        <div v-else class="poster-placeholder">暂无海报</div>
      </div>

      <!-- 内容区 -->
      <div class="details-box">
        <div class="title-line">{{ title }}</div>
        
        <div class="pure-tags-row">
          <span class="p-tag tag-green">{{ category }}</span>
          <span v-if="secondary_category && secondary_category !== '-'" class="p-tag tag-blue">🏷️ {{ secondary_category }}</span>
          <span class="id-text">TMDB ID: {{ tmdb_id }}</span>
          <span class="date-text">📅 {{ release_date }}</span>
        </div>

        <div class="pure-specs-row">
          <span v-if="resolution" class="p-badge">{{ resolution }}</span>
          <span v-if="v_encode" class="p-badge blue">{{ v_encode }}</span>
          <span v-if="a_encode" class="p-badge blue">{{ a_encode }}</span>
        </div>

        <div class="flex-info-grid">
          <div class="fig-item"><div class="fig-l">上映年份</div><div class="fig-v">{{ year }}</div></div>
          <div class="fig-item"><div class="fig-l">季号</div><div class="fig-v">{{ season }}</div></div>
          <div class="fig-item"><div class="fig-l">集数</div><div class="fig-v">{{ episode }}</div></div>
          <div class="fig-item"><div class="fig-l">来源</div><div class="fig-v">{{ source }}</div></div>
        </div>

        <div class="text-info-rows">
          <div class="row"><span class="rl">二级分类:</span><span class="rv" style="color: var(--n-info-color)">{{ secondary_category || '-' }}</span></div>
          <div class="row"><span class="rl">原产地:</span><span class="rv">{{ origin_country || '-' }}</span></div>
          <div class="row"><span class="rl">字幕语言:</span><span class="rv">{{ subtitle }}</span></div>
          <div class="row"><span class="rl">制作组:</span><span class="rv team">{{ team }}</span></div>
          <div class="row"><span class="rl">发布平台:</span><span class="rv">{{ platform || '-' }}</span></div>
          <div class="row"><span class="rl">视频特效:</span><span class="rv">{{ v_effect || '-' }}</span></div>
          <div class="row"><span class="rl">处理后名:</span><span class="rv mono">{{ processed_name }}</span></div>
          <div class="row"><span class="rl">原始文件:</span><span class="rv mono filename-text">{{ filename }}</span></div>
        </div>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.final-card-container { border-radius: var(--card-border-radius, 12px); border: 1px solid var(--primary-medium); background: var(--bg-surface); }
.header-content { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.title-wrap { display: flex; align-items: center; gap: 8px; }
.primary-icon { color: var(--n-primary-color); }
.header-text { font-weight: bold; font-size: 16px; color: var(--text-primary); }

.main-layout { display: flex; gap: 24px; padding: 4px 0; }
.poster-box { flex-shrink: 0; }
.poster-img :deep(img) { border-radius: var(--card-border-radius, 8px); box-shadow: 0 8px 24px var(--shadow-heavy); }
.poster-placeholder { width: 140px; height: 200px; background: var(--bg-primary); border: 1px dashed var(--app-border-light); border-radius: var(--card-border-radius, 8px); display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-weight: bold; }

.details-box { flex-grow: 1; min-width: 0; }
.title-line { font-size: 26px; font-weight: 900; color: var(--text-primary); line-height: 1.2; margin-bottom: 8px; }

.pure-tags-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.p-tag { padding: 2px 8px; border-radius: var(--button-border-radius, 10px); font-size: 12px; font-weight: 500; border: 1px solid transparent; }
.tag-green { color: var(--n-primary-color); border-color: var(--primary-strong); background: var(--primary-light); }
.tag-blue { color: var(--n-info-color); border-color: var(--info-strong); background: var(--info-light); }
.id-text { font-family: monospace; color: var(--text-muted); font-size: 12px; margin-left: 4px; }
.date-text { color: var(--n-primary-color); font-size: 13px; margin-left: 4px; }

.pure-specs-row { display: flex; gap: 6px; margin-bottom: 16px; }
.p-badge { padding: 1px 6px; border-radius: var(--button-border-radius, 4px); font-size: 10px; background: var(--bg-surface); color: var(--text-tertiary); border: 1px solid rgba(255,255,255, var(--border-medium-alpha)); }
.p-badge.blue { color: var(--n-info-color); border-color: var(--info-medium); }

.flex-info-grid { display: flex; gap: 1px; background: var(--app-border-light); border-radius: var(--card-border-radius, 8px); margin-bottom: 20px; overflow: hidden; border: 1px solid rgba(255,255,255, var(--border-light-alpha)); }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; background: var(--bg-primary); padding: 12px 4px; }
.fig-l { font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: bold; margin-bottom: 4px; }
.fig-v { font-weight: bold; font-size: 16px; color: var(--n-primary-color); }

.text-info-rows { font-size: 13px; display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; gap: 12px; align-items: flex-start; }
.rl { color: var(--text-muted); width: 160px; flex-shrink: 0; }
.rv { color: var(--text-secondary); word-break: break-all; }
.rv.team { color: var(--n-success-color); font-weight: bold; }
.rv.mono { font-family: monospace; color: var(--n-warning-color); background: var(--warning-subtle); padding: 0 4px; border-radius: var(--button-border-radius, 2px); }
.filename-text { font-size: 11px; opacity: var(--opacity-tertiary); }
</style>