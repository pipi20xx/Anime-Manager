<script setup lang="ts">
import { 
  NModal, NSpin, NSpace, NGrid, NGi, NTag, NIcon, NButton, 
  NInput, NSelect, NScrollbar, NList, NListItem, NAvatar, NImage,
  NCheckbox, NCollapse, NCollapseItem
} from 'naive-ui'
import {
  SuccessIcon, SearchIcon, TuneIcon, RenameIcon
} from '../../assets/icons' // Assuming icons might be centralized or re-import here
import {
  CheckCircleOutlined as CheckIcon,
  SearchOutlined as SearchBtnIcon,
  BuildOutlined as BuildIcon,
  DriveFileMoveOutlined as DriveIcon
} from '@vicons/material' // Direct import for simplicity in this file

import { useRecognitionModal } from '../../composables/components/useRecognitionModal'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  file: any
  data: any
  previewPath: string
  loading: boolean
  isRenaming: boolean
  apiBase: string
  availableRules: any[]
}>()

const emit = defineEmits(['update:show', 'recognize', 'rename'])

const {
  getImg,
  getLogClass,
  forcedParams,
  testSearch,
  searchTmdbForTest,
  handleRecognize
} = useRecognitionModal(props, emit)
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 850px" 
    title="识别详情与强制测试"
  >
    <n-spin :show="loading">
      <div v-if="data" class="res-detail">
        <n-space vertical size="large">
          <div class="main-layout">
             <div class="poster-box">
                <n-image v-if="data.final_result.poster_path" :src="getImg(data.final_result.poster_path)" width="120" class="poster-img" preview-disabled />
                <div v-else class="poster-placeholder">无海报</div>
             </div>
             <div class="details-box">
                <div class="title-line">{{ data.final_result.title }}</div>
                <div class="pure-tags-row">
                   <span class="p-tag tag-green">{{ data.final_result.category }}</span>
                   <span v-if="data.final_result.secondary_category" class="p-tag tag-blue">🏷️ {{ data.final_result.secondary_category }}</span>
                   <span class="id-text">TMDB: {{ data.final_result.tmdb_id || 'N/A' }}</span>
                   <span class="date-text" v-if="data.final_result.release_date">📅 {{ data.final_result.release_date }}</span>
                </div>
                <div class="pure-specs-row">
                   <span v-if="data.final_result.resolution" class="p-badge">{{ data.final_result.resolution }}</span>
                   <span v-if="data.final_result.video_encode" class="p-badge blue">{{ data.final_result.video_encode }}</span>
                   <span v-if="data.final_result.audio_encode" class="p-badge blue">{{ data.final_result.audio_encode }}</span>
                </div>
                <div class="flex-info-grid">
                   <div class="fig-item"><div class="fig-l">年份</div><div class="fig-v">{{ data.final_result.year || '-' }}</div></div>
                   <div class="fig-item"><div class="fig-l">季号</div><div class="fig-v">{{ data.final_result.season !== undefined ? 'S'+data.final_result.season : '-' }}</div></div>
                   <div class="fig-item"><div class="fig-l">集数</div><div class="fig-v">{{ data.final_result.episode !== undefined ? 'E'+data.final_result.episode : '-' }}</div></div>
                   <div class="fig-item"><div class="fig-l">来源</div><div class="fig-v">{{ data.final_result.source || '-' }}</div></div>
                </div>
                <div class="text-info-rows">
                   <div class="row"><span class="rl">原产地:</span><span class="rv">{{ data.final_result.origin_country || '-' }}</span></div>
                   <div class="row"><span class="rl">字幕语言:</span><span class="rv">{{ data.final_result.subtitle || '无' }}</span></div>
                   <div class="row"><span class="rl">制作组:</span><span class="rv team">{{ data.final_result.team || '未知' }}</span></div>
                   <div class="row"><span class="rl">发布平台:</span><span class="rv">{{ data.final_result.platform || '-' }}</span></div>
                   <div class="row"><span class="rl">视频特效:</span><span class="rv">{{ data.final_result.video_effect || '-' }}</span></div>
                   <div class="row"><span class="rl">处理后名:</span><span class="rv mono">{{ data.final_result.processed_name }}</span></div>
                </div>
             </div>
          </div>
          
          <div class="preview-box">
            <div class="pl"><n-icon><DriveIcon /></n-icon> 重命名路径预览</div>
            <div class="pv">{{ previewPath || (loading ? '正在计算...' : '无法生成预览') }}</div>
          </div>

          <n-collapse arrow-placement="right">
            <n-collapse-item title="查看深度识别审计日志" name="logs">
              <template #header-extra><n-icon><SearchBtnIcon /></n-icon></template>
              <n-scrollbar style="max-height: 250px" class="audit-log-box">
                <div v-for="(log, i) in data.logs" :key="i" :class="['log-line', getLogClass(log)]">
                  <span class="idx">{{ String(i+1).padStart(2, '0') }}</span>
                  <span class="txt">{{ log }}</span>
                </div>
              </n-scrollbar>
            </n-collapse-item>
          </n-collapse>

          <div class="forced-box">
            <div class="pl"><n-icon><BuildIcon /></n-icon> 强制参数调试 (仅本次生效)</div>
            
            <div class="preference-group">
              <n-checkbox v-model:checked="forcedParams.anime_priority"><span class="check-label">动漫识别优化</span></n-checkbox>
            </div>

            <n-grid :cols="4" :x-gap="12" class="mb-4">
              <n-gi><n-input v-model:value="forcedParams.tmdb_id" placeholder="TMDB ID" size="small" /></n-gi>
              <n-gi><n-select v-model:value="forcedParams.type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="资源类型" size="small" /></n-gi>
              <n-gi><n-input v-model:value="forcedParams.season" placeholder="指定季" size="small" /></n-gi>
              <n-gi><n-input v-model:value="forcedParams.episode" placeholder="指定集" size="small" /></n-gi>
            </n-grid>

            <n-input v-model:value="testSearch.keyword" placeholder="快捷搜索剧名找 ID..." size="small" class="mt-4" @keypress.enter="searchTmdbForTest">
              <template #suffix><n-button v-bind="getButtonStyle('icon')" size="small" @click="searchTmdbForTest" :loading="testSearch.loading"><template #icon><n-icon><SearchBtnIcon /></n-icon></template></n-button></template>
            </n-input>
            <n-scrollbar v-if="testSearch.results.length > 0" style="max-height: 120px" class="search-res-list mt-2">
              <n-list hoverable clickable>
                <n-list-item v-for="res in testSearch.results" :key="res.id" @click="forcedParams.tmdb_id = String(res.id); forcedParams.type = res.media_type || forcedParams.type; testSearch.results = []">
                  <template #prefix><n-avatar :src="getImg(res.poster_path)" size="small" /></template>
                  <div style="font-size:12px; color: #eee"><b>{{ res.title }}</b> ({{ res.year }}) - ID: {{ res.id }}</div>
                </n-list-item>
              </n-list>
            </n-scrollbar>
            <n-button type="warning" ghost block size="small" class="mt-4" @click="handleRecognize">应用参数并重试识别</n-button>
          </div>
        </n-space>
      </div>
    </n-spin>
    <template #action>
      <n-space justify="end" style="width: 100%">
        <n-space>
          <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" :loading="isRenaming" @click="emit('rename')">
            确认重命名
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.res-detail { color: var(--n-text-color-2); }
.main-layout { display: flex; gap: 20px; padding: 4px 0; align-items: flex-start; }
.poster-box { flex-shrink: 0; }
.poster-img :deep(img) { border-radius: var(--card-border-radius, 8px); box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
.poster-placeholder { width: 120px; height: 180px; background: #111; border: 1px dashed #333; border-radius: var(--card-border-radius, 8px); display: flex; align-items: center; justify-content: center; color: #555; font-size: 12px; }
.details-box { flex-grow: 1; min-width: 0; }
.title-line { font-size: 20px; font-weight: bold; color: var(--n-text-color-1); line-height: 1.3; margin-bottom: 8px; }
.pure-tags-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.p-tag { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; border: 1px solid transparent; }
.tag-green { color: var(--n-primary-color); background: color-mix(in srgb, var(--n-primary-color), transparent 90%); border-color: color-mix(in srgb, var(--n-primary-color), transparent 75%); }
.tag-blue { color: var(--n-info-color); background: color-mix(in srgb, var(--n-info-color), transparent 90%); border-color: color-mix(in srgb, var(--n-info-color), transparent 75%); }
.id-text { font-family: monospace; color: #666; font-size: 11px; margin-left: 4px; }
.date-text { color: var(--n-primary-color); font-size: 12px; margin-left: 4px; }
.pure-specs-row { display: flex; gap: 6px; margin-bottom: 12px; }
.p-badge { padding: 1px 6px; border-radius: 4px; font-size: 10px; background: rgba(255,255,255,0.08); color: #888; border: 1px solid rgba(255,255,255,0.1); }
.p-badge.blue { color: var(--n-info-color); border-color: color-mix(in srgb, var(--n-info-color), transparent 80%); }
.flex-info-grid { display: flex; gap: 1px; background: rgba(255,255,255,0.1); border-radius: 6px; margin-bottom: 16px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; background: #1a1a1e; padding: 8px 4px; }
.fig-l { font-size: 10px; color: #555; text-transform: uppercase; font-weight: bold; margin-bottom: 2px; }
.fig-v { font-weight: bold; font-size: 14px; color: var(--n-primary-color); }
.text-info-rows { font-size: 12px; display: flex; flex-direction: column; gap: 6px; }
.row { display: flex; gap: 12px; align-items: flex-start; }
.rl { color: #555; width: 80px; flex-shrink: 0; text-align: right; }
.rv { color: #eee; word-break: break-all; }
.rv.team { color: var(--n-success-color); font-weight: bold; }
.rv.mono { 
  font-family: var(--code-font); 
  color: var(--n-warning-color); 
  background: var(--app-surface-inner); 
  padding: 2px 6px; 
  border-radius: var(--button-border-radius, 4px);
  border: 1px solid var(--app-border-light);
}

.preview-box { 
  background: var(--app-surface-card); 
  padding: 14px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--app-border-light); 
  box-sizing: border-box;
}
.preview-box .pl { font-size: 12px; font-weight: bold; color: var(--n-info-color); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.preview-box .pv { 
  font-family: var(--code-font); 
  font-size: 13px; 
  color: var(--n-text-color-1); 
  word-break: break-all; 
  background: var(--app-surface-inner);
  padding: 10px;
  border-radius: 6px;
  border: 1px solid var(--app-border-light);
}

.forced-box { 
  background: var(--app-surface-card); 
  padding: 16px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--app-border-light); 
  box-sizing: border-box;
}
.forced-box .pl { font-size: 12px; font-weight: bold; color: var(--n-warning-color); margin-bottom: 16px; display: flex; align-items: center; gap: 6px; }
.preference-group { background: var(--app-surface-inner); padding: 10px; border-radius: 6px; border: 1px solid var(--app-border-light); margin-bottom: 16px; }
.check-label { font-size: 12px; color: var(--n-text-color-2); }
.search-res-list { background: var(--app-surface-inner); border: 1px solid var(--app-border-light); border-radius: 6px; }
.audit-log-box { background: #000; padding: 12px; border-radius: 8px; border: 1px solid var(--app-border-light); font-family: var(--code-font); font-size: 12px; line-height: 1.6; }
.log-line { display: flex; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.03); padding: 2px 0; }
.log-line .idx { color: #444; font-size: 10px; width: 20px; flex-shrink: 0; }
.log-line.p { color: var(--n-primary-color); font-weight: bold; margin-top: 8px; border-bottom: 1px solid var(--app-border-light); }
.log-line.d { color: var(--n-info-color); }
.log-line.s { color: var(--n-primary-color); }
.log-line.w { color: var(--n-warning-color); }
.log-line.i { color: var(--n-warning-color); font-weight: bold; background: color-mix(in srgb, var(--n-warning-color), transparent 92%); }
</style>
