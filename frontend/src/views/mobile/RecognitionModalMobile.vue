<script setup lang="ts">
import { 
  NModal, NSpin, NSpace, NTag, NIcon, NButton, 
  NInput, NSelect, NScrollbar, NList, NListItem, NAvatar, NImage,
  NSwitch, NCollapse, NCollapseItem
} from 'naive-ui'
import AppTextField from '../../components/AppTextField.vue'
import AppSelectField from '../../components/AppSelectField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import AppGlassModal from '../../components/AppGlassModal.vue'
import {
  CheckCircleOutlined as CheckIcon,
  SearchOutlined as SearchBtnIcon,
  BuildOutlined as BuildIcon,
  DriveFileMoveOutlined as DriveIcon,
  TagOutlined as HashIcon
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
  handleRecognize,
  isHashing,
  hashResult,
  calculateHash
} = useRecognitionModal(props, emit)
</script>

<template>
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    class="mobile-modal"
    title="单文件识别"
  >
    <n-spin :show="loading">
      <div class="res-detail">
        <n-space vertical>
          <!-- 识别参数配置 - 放在最前面 -->
          <div class="forced-box-mobile">
            <div class="pl"><n-icon><BuildIcon /></n-icon> 识别参数配置</div>
            
            <div class="strategy-list">
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">动漫识别优化</div>
                  <div class="strategy-desc-m">提升动画匹配精度，过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="forcedParams.anime_priority" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">本地数据中心</div>
                  <div class="strategy-desc-m">优先碰撞本地数据库，毫秒级离线匹配</div>
                </div>
                <n-switch v-model:value="forcedParams.offline_priority" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">Bangumi 数据源优先</div>
                  <div class="strategy-desc-m">针对新番或缺失条目，优先尝试 BGM</div>
                </div>
                <n-switch v-model:value="forcedParams.bangumi_priority" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">Bangumi 故障转移</div>
                  <div class="strategy-desc-m">TMDB 搜索失败时，自动使用 BGM 补全</div>
                </div>
                <n-switch v-model:value="forcedParams.bangumi_failover" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">强制单文件模式</div>
                  <div class="strategy-desc-m">将完整输入作为文件名解析，无视路径干扰</div>
                </div>
                <n-switch v-model:value="forcedParams.force_filename" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">智能记忆</div>
                  <div class="strategy-desc-m">自动记住系列特征，后续秒级拦截</div>
                </div>
                <n-switch v-model:value="forcedParams.series_fingerprint" size="small" />
              </div>
              <div class="strategy-row-m">
                <div class="strategy-info-m">
                  <div class="strategy-title-m">合集识别增强</div>
                  <div class="strategy-desc-m">支持解析 01-12 等合集，自动计算集数区间</div>
                </div>
                <n-switch v-model:value="forcedParams.batch_enhancement" size="small" />
              </div>
            </div>

            <n-space vertical :size="8" style="margin-top: 10px">
              <AppTextField v-model:value="forcedParams.tmdb_id" label="TMDB ID" placeholder="TMDB ID" />
              <AppSelectField v-model:value="forcedParams.type" label="资源类型" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="资源类型" />
              <div class="season-ep-row">
                <AppTextField v-model:value="forcedParams.season" label="季 (S)" placeholder="季 (S)" />
                <AppTextField v-model:value="forcedParams.episode" label="集 (E)" placeholder="集 (E)" />
              </div>
            </n-space>

            <div class="search-box-mobile" style="margin-top: 10px">
              <AppSearchField v-model:value="testSearch.keyword" placeholder="搜剧名找ID..." :loading="testSearch.loading" @search="searchTmdbForTest" />
              <n-scrollbar v-if="testSearch.results.length > 0" style="max-height: 120px" class="search-res-list mt-2">
                <n-list hoverable clickable>
                  <n-list-item v-for="res in testSearch.results" :key="res.id" @click="forcedParams.tmdb_id = String(res.id); forcedParams.type = res.media_type || forcedParams.type; testSearch.results = []">
                    <template #prefix><n-avatar :src="getImg(res.poster_path)" size="small" /></template>
                    <div style="font-size:11px; color: var(--text-secondary); line-height: 1.2"><b>{{ res.title }}</b> ({{ res.year }})<br>ID: {{ res.id }}</div>
                  </n-list-item>
                </n-list>
              </n-scrollbar>
            </div>

            <n-button type="primary" block size="small" style="margin-top: 12px" :loading="loading" @click="handleRecognize">
              开始识别
            </n-button>
          </div>

          <!-- 识别结果 - 有数据时才显示 -->
          <div v-if="data" class="result-section">
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
            
            <div class="preview-box-mobile">
              <div class="pl"><n-icon><DriveIcon /></n-icon> 重命名预览</div>
              <div class="pv">{{ previewPath || (loading ? '计算中...' : '无法预览') }}</div>
            </div>

            <div v-if="hashResult" class="hash-result-mobile">
              <div class="pl" style="color: var(--n-success-color)"><n-icon><CheckIcon /></n-icon> 哈希已入库</div>
              <div class="hash-rows">
                <div class="hr"><span class="hl">SHA1</span><span class="hv mono">{{ hashResult.sha1 }}</span></div>
                <div class="hr"><span class="hl">ED2K</span><span class="hv mono">{{ hashResult.ed2k }}</span></div>
              </div>
            </div>

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
          </div>
        </n-space>
      </div>
    </n-spin>
    <template #action>
      <n-space justify="space-between" style="width: 100%">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-space>
            <n-button v-if="data" type="warning" size="small" :loading="isHashing" @click="calculateHash">
              <template #icon><n-icon><HashIcon /></n-icon></template>
              哈希
            </n-button>
            <n-button v-if="data" v-bind="getButtonStyle('primary')" :loading="isRenaming" @click="emit('rename')" size="small">
              确认重命名
            </n-button>
          </n-space>
      </n-space>
    </template>
  </AppGlassModal>
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
.poster-placeholder-mobile { width: 80px; height: 120px; background: var(--app-surface-inner); display: flex; align-items: center; justify-content: center; font-size: 10px; color: var(--text-muted); border-radius: var(--button-border-radius, 6px); border: 1px solid var(--app-border-light); }

.info-box-mobile { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.title-mobile { font-weight: bold; font-size: 15px; line-height: 1.3; }
.tags-mobile { display: flex; gap: 4px; flex-wrap: wrap; }
.meta-row { font-size: 11px; color: var(--text-muted); display: flex; flex-direction: column; gap: 2px; }
.date-text { color: var(--n-primary-color); }
.tmdb-id-text { font-family: monospace; color: var(--text-hint); }

.specs-mobile { display: flex; gap: 4px; margin-top: 4px; }
.p-badge { padding: 0 4px; border-radius: 3px; font-size: 9px; background: var(--bg-surface); color: var(--text-muted); border: 1px solid var(--border-light); }
.p-badge.blue { color: var(--n-info-color); border-color: var(--color-info-bg); }

.mobile-details-list { margin-top: 8px; }
.fig-grid-mobile { display: flex; background: var(--app-surface-inner); border-radius: 6px; overflow: hidden; border: 1px solid var(--border-light); margin-bottom: 10px; }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; padding: 6px 2px; border-right: 1px solid var(--border-light); }
.fig-item:last-child { border-right: none; }
.fig-l { font-size: 9px; color: var(--text-hint); text-transform: uppercase; margin-bottom: 2px; }
.fig-v { font-weight: bold; font-size: 13px; color: var(--n-primary-color); }

.text-rows-mobile { display: flex; flex-direction: column; gap: 6px; }
.tr { display: flex; gap: 8px; font-size: 11px; }
.tl { color: var(--text-hint); width: 60px; flex-shrink: 0; }
.tv { color: var(--text-tertiary); word-break: break-all; }
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

.hash-result-mobile {
  background: var(--app-surface-inner);
  padding: 10px;
  border-radius: var(--button-border-radius, 8px);
  border: 1px solid var(--n-success-color);
}
.hash-rows { display: flex; flex-direction: column; gap: 4px; }
.hr { display: flex; gap: 6px; align-items: baseline; }
.hl { font-size: 10px; color: var(--text-hint); width: 36px; flex-shrink: 0; }
.hv { font-size: 10px; color: var(--text-secondary); word-break: break-all; }
.hv.mono { font-family: monospace; }

.debug-panel { background: var(--app-surface-inner); padding: 12px; border-radius: var(--button-border-radius, 8px); border: 1px solid var(--app-border-light); }
.season-ep-row { display: flex; gap: 8px; }
.search-box-mobile { margin-top: 12px; }
.mt-3 { margin-top: 12px; }

.forced-box-mobile {
  background: var(--app-surface-card);
  padding: 12px;
  border-radius: var(--button-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.forced-box-mobile .pl { font-size: 13px; }
.strategy-list { display: flex; flex-direction: column; gap: 6px; }
.strategy-row-m {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--app-surface-inner);
  padding: 10px 11px;
  border-radius: 6px;
  border: 1px solid var(--app-border-light);
}
.strategy-info-m { min-width: 0; }
.strategy-title-m { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.strategy-desc-m { font-size: 11px; color: var(--text-hint); line-height: 1.35; }

.audit-log-mobile { 
  background: var(--bg-primary); 
  padding: 8px; 
  border-radius: var(--button-border-radius, 6px); 
  border: 1px solid var(--app-border-light);
  font-family: monospace; 
  font-size: 10px; 
  max-height: 200px; 
  overflow-y: auto; 
}
.log-line { display: flex; gap: 6px; margin-bottom: 2px; }
.idx { color: var(--text-hint); min-width: 16px; text-align: right; }
.txt { word-break: break-all; flex: 1; }

.log-line.p { color: var(--n-primary-color); font-weight: bold; border-top: 1px solid var(--border-medium); margin-top: 4px; padding-top: 4px; }
.log-line.d { color: var(--n-info-color); }
.log-line.s { color: var(--n-primary-color); }
.log-line.w { color: var(--n-warning-color); }
.log-line.i { color: var(--n-warning-color); font-weight: bold; }
</style>
