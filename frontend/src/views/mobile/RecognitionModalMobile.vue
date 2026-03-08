<script setup lang="ts">
import { 
  NModal, NSpin, NSpace, NTag, NIcon, NButton, 
  NInput, NSelect, NScrollbar, NList, NListItem, NAvatar, NImage,
  NCheckbox, NCollapse, NCollapseItem
} from 'naive-ui'
import {
  CheckCircleOutlined as CheckIcon,
  SearchOutlined as SearchBtnIcon,
  BuildOutlined as BuildIcon,
  DriveFileMoveOutlined as DriveIcon
} from '@vicons/material'

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
    class="mobile-modal"
    title="识别详情与强制测试"
  >
    <n-spin :show="loading">
      <div v-if="data" class="res-detail">
        <n-space vertical>
          <!-- 移动端布局：海报在左上，信息在右 -->
          <div class="mobile-header-layout">
             <div class="poster-box-mobile">
                <n-image v-if="data.final_result.poster_path" :src="getImg(data.final_result.poster_path)" width="80" class="poster-img" preview-disabled />
                <div v-else class="poster-placeholder-mobile">无海报</div>
             </div>
             <div class="info-box-mobile">
                <div class="title-mobile">{{ data.final_result.title }}</div>
                <div class="tags-mobile">
                   <n-tag size="tiny" type="success" :bordered="false">{{ data.final_result.category }}</n-tag>
                   <n-tag v-if="data.final_result.secondary_category" size="tiny" type="info" :bordered="false">{{ data.final_result.secondary_category }}</n-tag>
                </div>
                <div class="meta-row">
                   <span v-if="data.final_result.release_date" class="date-text">📅 {{ data.final_result.release_date }}</span>
                   <span class="tmdb-id-text">ID: {{ data.final_result.tmdb_id || 'N/A' }}</span>
                </div>
                <div class="specs-mobile">
                   <span v-if="data.final_result.resolution" class="p-badge">{{ data.final_result.resolution }}</span>
                   <span v-if="data.final_result.video_encode" class="p-badge blue">{{ data.final_result.video_encode }}</span>
                </div>
             </div>
          </div>

          <!-- 详细列表 (移动端优化) -->
          <div class="mobile-details-list">
             <div class="fig-grid-mobile">
                <div class="fig-item"><div class="fig-l">年份</div><div class="fig-v">{{ data.final_result.year || '-' }}</div></div>
                <div class="fig-item"><div class="fig-l">季号</div><div class="fig-v">{{ data.final_result.season !== undefined ? 'S'+data.final_result.season : '-' }}</div></div>
                <div class="fig-item"><div class="fig-l">集数</div><div class="fig-v">{{ data.final_result.episode !== undefined ? 'E'+data.final_result.episode : '-' }}</div></div>
             </div>
             <div class="text-rows-mobile">
                <div class="tr"><span class="tl">制作组:</span><span class="tv team">{{ data.final_result.team || '未知' }}</span></div>
                <div class="tr"><span class="tl">平台/特效:</span><span class="tv">{{ data.final_result.platform || '-' }} / {{ data.final_result.video_effect || '-' }}</span></div>
                <div class="tr"><span class="tl">处理后名:</span><span class="tv mono">{{ data.final_result.processed_name }}</span></div>
             </div>
          </div>
          
          <!-- 预览路径 -->
          <div class="preview-box-mobile">
            <div class="pl"><n-icon><DriveIcon /></n-icon> 重命名预览</div>
            <div class="pv">{{ previewPath || (loading ? '计算中...' : '无法预览') }}</div>
          </div>

          <!-- 强制参数调试 (单列布局) -->
          <n-collapse arrow-placement="right" display-directive="show">
             <n-collapse-item title="强制参数调试" name="debug">
                <template #header-extra><n-icon><BuildIcon /></n-icon></template>
                <div class="debug-panel">
                   <n-checkbox v-model:checked="forcedParams.anime_priority" style="margin-bottom: 12px">
                      <span style="font-size: 13px">动漫识别优化</span>
                   </n-checkbox>
                   
                   <n-space vertical :size="8">
                      <n-input v-model:value="forcedParams.tmdb_id" placeholder="TMDB ID" size="small" />
                      <n-select v-model:value="forcedParams.type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="资源类型" size="small" />
                      <div class="season-ep-row">
                         <n-input v-model:value="forcedParams.season" placeholder="季 (S)" size="small" />
                         <n-input v-model:value="forcedParams.episode" placeholder="集 (E)" size="small" />
                      </div>
                   </n-space>

                   <div class="search-box-mobile">
                      <n-input v-model:value="testSearch.keyword" placeholder="搜剧名找ID..." size="small" @keypress.enter="searchTmdbForTest">
                        <template #suffix>
                           <n-button v-bind="getButtonStyle('icon')" size="small" @click="searchTmdbForTest" :loading="testSearch.loading">
                              <template #icon><n-icon><SearchBtnIcon /></n-icon></template>
                           </n-button>
                        </template>
                      </n-input>
                      <n-scrollbar v-if="testSearch.results.length > 0" style="max-height: 120px" class="search-res-list mt-2">
                        <n-list hoverable clickable>
                          <n-list-item v-for="res in testSearch.results" :key="res.id" @click="forcedParams.tmdb_id = String(res.id); forcedParams.type = res.media_type || forcedParams.type; testSearch.results = []">
                            <template #prefix><n-avatar :src="getImg(res.poster_path)" size="small" /></template>
                            <div style="font-size:11px; color: #eee; line-height: 1.2"><b>{{ res.title }}</b> ({{ res.year }})<br>ID: {{ res.id }}</div>
                          </n-list-item>
                        </n-list>
                      </n-scrollbar>
                   </div>

                   <n-button type="warning" ghost block size="small" class="mt-3" @click="handleRecognize">重试识别</n-button>
                </div>
             </n-collapse-item>
          </n-collapse>

          <!-- 审计日志 -->
          <n-collapse arrow-placement="right">
            <n-collapse-item title="审计日志" name="logs">
              <template #header-extra><n-icon><SearchBtnIcon /></n-icon></template>
              <div class="audit-log-mobile">
                <div v-for="(log, i) in data.logs" :key="i" :class="['log-line', getLogClass(log)]">
                  <span class="idx">{{ i+1 }}</span>
                  <span class="txt">{{ log }}</span>
                </div>
              </div>
            </n-collapse-item>
          </n-collapse>

        </n-space>
      </div>
    </n-spin>
    <template #action>
      <n-space justify="space-between" style="width: 100%">
          <n-button @click="emit('update:show', false)" size="small">取消</n-button>
          <n-button type="primary" :loading="isRenaming" @click="emit('rename')" size="small">
            <template #icon><n-icon><CheckIcon /></n-icon></template>
            确认重命名
          </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.mobile-modal {
  width: calc(100vw - 32px) !important;
  max-width: 400px;
  margin-top: 60px; /* Offset from top to avoid covering status bar/header too much */
}

.mobile-header-layout {
  display: flex;
  gap: 12px;
}

.poster-img :deep(img) { border-radius: var(--button-border-radius, 6px); }
.poster-placeholder-mobile { width: 80px; height: 120px; background: var(--app-surface-inner); display: flex; align-items: center; justify-content: center; font-size: 10px; color: #666; border-radius: var(--button-border-radius, 6px); border: 1px solid var(--app-border-light); }

.info-box-mobile { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.title-mobile { font-weight: bold; font-size: 15px; line-height: 1.3; }
.tags-mobile { display: flex; gap: 4px; flex-wrap: wrap; }
.meta-row { font-size: 11px; color: #888; display: flex; flex-direction: column; gap: 2px; }
.date-text { color: var(--n-primary-color); }
.tmdb-id-text { font-family: monospace; color: #555; }

.specs-mobile { display: flex; gap: 4px; margin-top: 4px; }
.p-badge { padding: 0 4px; border-radius: 3px; font-size: 9px; background: rgba(255,255,255,0.05); color: #666; border: 1px solid rgba(255,255,255,0.1); }
.p-badge.blue { color: var(--n-info-color); border-color: rgba(112, 192, 232, 0.2); }

.mobile-details-list { margin-top: 8px; }
.fig-grid-mobile { display: flex; background: rgba(0,0,0,0.2); border-radius: 6px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 10px; }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; padding: 6px 2px; border-right: 1px solid rgba(255,255,255,0.05); }
.fig-item:last-child { border-right: none; }
.fig-l { font-size: 9px; color: #555; text-transform: uppercase; margin-bottom: 2px; }
.fig-v { font-weight: bold; font-size: 13px; color: var(--n-primary-color); }

.text-rows-mobile { display: flex; flex-direction: column; gap: 6px; }
.tr { display: flex; gap: 8px; font-size: 11px; }
.tl { color: #555; width: 60px; flex-shrink: 0; }
.tv { color: #aaa; word-break: break-all; }
.tv.team { color: var(--n-success-color); font-weight: bold; }
.tv.mono { font-family: monospace; color: var(--n-warning-color); }

.preview-box-mobile {
  background: var(--app-surface-inner);
  padding: 10px;
  border-radius: var(--button-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.pl { font-size: 11px; font-weight: bold; color: var(--n-info-color); margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.pv { font-family: monospace; font-size: 11px; word-break: break-all; color: var(--n-text-color-1); }

.debug-panel { background: var(--app-surface-inner); padding: 12px; border-radius: var(--button-border-radius, 8px); border: 1px solid var(--app-border-light); }
.season-ep-row { display: flex; gap: 8px; }
.search-box-mobile { margin-top: 12px; }
.mt-3 { margin-top: 12px; }

.audit-log-mobile { 
  background: #000; 
  padding: 8px; 
  border-radius: var(--button-border-radius, 6px); 
  border: 1px solid var(--app-border-light);
  font-family: monospace; 
  font-size: 10px; 
  max-height: 200px; 
  overflow-y: auto; 
}
.log-line { display: flex; gap: 6px; margin-bottom: 2px; }
.idx { color: #555; min-width: 16px; text-align: right; }
.txt { word-break: break-all; flex: 1; }

.log-line.p { color: var(--n-primary-color); font-weight: bold; border-top: 1px solid #333; margin-top: 4px; padding-top: 4px; }
.log-line.d { color: var(--n-info-color); }
.log-line.s { color: var(--n-primary-color); }
.log-line.w { color: var(--n-warning-color); }
.log-line.i { color: var(--n-warning-color); font-weight: bold; }
</style>
