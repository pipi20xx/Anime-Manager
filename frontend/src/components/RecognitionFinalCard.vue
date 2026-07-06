<script setup lang="ts">
/**
 * RecognitionFinalCard - 最终识别结论卡片
 *
 * 合并自 RecognitionFinalCardDesktop + RecognitionFinalCardMobile
 * 以 Desktop 版为基准 (信息更完整), 通过 CSS 媒体查询适配移动端
 */
import { NCard, NIcon, NImage } from 'naive-ui'
import { FlagOutlined as FinalIcon } from '@vicons/material'
import { useRecognitionFinal } from '../composables/components/useRecognitionFinal'

const {
  title, poster, category, platform, tmdb_id, tmdbUrl, release_date, secondary_category, origin_country,
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
        <n-icon size="22" class="primary-icon"><FinalIcon /></n-icon>
        <span class="header-text">最终识别结论</span>
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
          <a v-if="tmdbUrl" :href="tmdbUrl" target="_blank" class="id-link">TMDB ID: {{ tmdb_id }}</a>
          <span v-else class="id-text">TMDB ID: {{ tmdb_id }}</span>
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
          <div class="fig-item"><div class="fig-l">介质来源</div><div class="fig-v">{{ source }}</div></div>
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
.final-card-container {
  border-radius: var(--card-border-radius, 12px);
  border: 1px solid var(--primary-medium);
  background: var(--bg-surface);
}
.header-content { display: flex; align-items: center; gap: var(--space-2); }
.primary-icon { color: var(--n-primary-color); }
.header-text { font-weight: bold; font-size: var(--text-lg); color: var(--text-primary); }

.main-layout { display: flex; gap: var(--space-6); padding: 4px 0; }
.poster-box { flex-shrink: 0; }
.poster-img :deep(img) { border-radius: var(--card-border-radius, 8px); box-shadow: 0 8px 24px var(--shadow-heavy); }
.poster-placeholder {
  width: 140px; height: 200px;
  background: var(--bg-primary);
  border: 1px dashed var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-weight: bold;
}

.details-box { flex-grow: 1; min-width: 0; }
.title-line { font-size: var(--text-3xl); font-weight: 900; color: var(--text-primary); line-height: 1.2; margin-bottom: var(--space-2); }

.pure-tags-row { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.p-tag { padding: 2px var(--space-2); border-radius: var(--button-border-radius, 10px); font-size: var(--text-sm); font-weight: 500; border: 1px solid transparent; color: #fff; }
.tag-green { background: #2e7d32; border-color: transparent; }
.tag-blue { background: #0288d1; border-color: transparent; }
.id-text { font-family: monospace; color: var(--text-muted); font-size: var(--text-sm); margin-left: var(--space-1); }
.id-link { font-family: monospace; color: var(--n-primary-color); font-size: var(--text-sm); margin-left: var(--space-1); text-decoration: none; cursor: pointer; transition: color 0.2s; }
.id-link:hover { color: var(--n-info-color); text-decoration: underline; }
.date-text { color: var(--n-primary-color); font-size: var(--text-base); margin-left: var(--space-1); }

.pure-specs-row { display: flex; gap: var(--space-1); margin-bottom: var(--space-4); }
.p-badge { padding: 1px var(--space-1); border-radius: var(--button-border-radius, 4px); font-size: var(--text-2xs); background: #e65100; color: #fff; border: 1px solid transparent; }
.p-badge.blue { color: #fff; background: #0288d1; border-color: transparent; }

.flex-info-grid {
  display: flex; gap: 1px;
  background: var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  margin-bottom: var(--space-5);
  overflow: hidden;
  border: 1px solid rgba(255,255,255, var(--border-light-alpha));
}
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; background: var(--bg-primary); padding: var(--space-3) var(--space-1); }
.fig-l { font-size: var(--text-2xs); color: var(--text-muted); text-transform: uppercase; font-weight: bold; margin-bottom: var(--space-1); }
.fig-v { font-weight: bold; font-size: var(--text-lg); color: var(--n-primary-color); }

.text-info-rows { font-size: var(--text-base); display: flex; flex-direction: column; gap: var(--space-2); }
.row { display: flex; gap: var(--space-3); align-items: flex-start; }
.rl { color: var(--text-muted); width: 160px; flex-shrink: 0; }
.rv { color: var(--text-secondary); word-break: break-all; }
.rv.team { color: var(--n-success-color); font-weight: bold; }
.rv.mono { font-family: monospace; color: var(--n-warning-color); background: var(--warning-subtle); padding: 0 var(--space-1); border-radius: var(--button-border-radius, 2px); }
.filename-text { font-size: var(--text-xs); opacity: var(--opacity-tertiary); }

/* === 移动端适配 === */
@media (max-width: 767px) {
  .header-text { font-size: var(--text-md); }
  .main-layout { gap: var(--space-3); }
  .poster-img :deep(img),
  .poster-placeholder { width: 100px !important; height: 140px; }
  .poster-placeholder { font-size: var(--text-2xs); }
  .title-line { font-size: var(--text-xl); }
  .p-tag { font-size: var(--text-xs); padding: 1px var(--space-1); }
  .id-text, .id-link, .date-text { font-size: var(--text-xs); }
  .p-badge { font-size: 9px; }
  .fig-item { padding: var(--space-2) 2px; }
  .fig-l { font-size: 9px; }
  .fig-v { font-size: var(--text-md); }
  .flex-info-grid { margin-bottom: var(--space-3); }
  .text-info-rows { font-size: var(--text-sm); gap: var(--space-1); }
  .rl { width: 50px; font-size: var(--text-xs); }
  .rv.mono { font-size: var(--text-xs); }
  .filename-text { font-size: var(--text-2xs); }
}
</style>
