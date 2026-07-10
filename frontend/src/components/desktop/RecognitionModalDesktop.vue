<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NSpin, NSpace, NGrid, NGi, NTag, NIcon, NButton, 
  NInput, NSelect, NScrollbar, NList, NListItem, NAvatar, NImage,
  NSwitch, NCollapse, NCollapseItem
} from 'naive-ui'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import AppSearchField from '../AppSearchField.vue'
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
  handleRecognize,
  isHashing,
  hashResult,
  calculateHash
} = useRecognitionModal(props, emit)
</script>

<template>
  <AppGlassModal
    appearance-key="recognition-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 850px"
    title="单文件识别"
  >
    <n-spin :show="loading">
      <div class="res-detail">
        <n-space vertical size="large">
          <!-- 强制参数调试 - 放在最前面，先设置再识别 -->
          <div class="forced-box">
            <div class="pl"><n-icon><BuildIcon /></n-icon> 识别参数配置 (仅本次生效)</div>
            
            <div class="strategy-list">
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">动漫识别优化</div>
                  <div class="strategy-desc">开启后提升动画匹配精度，过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="forcedParams.anime_priority" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">本地数据中心</div>
                  <div class="strategy-desc">优先碰撞本地数据库，实现毫秒级离线匹配</div>
                </div>
                <n-switch v-model:value="forcedParams.offline_priority" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">Bangumi 数据源优先</div>
                  <div class="strategy-desc">针对新番或缺失条目，优先尝试 BGM 镜像</div>
                </div>
                <n-switch v-model:value="forcedParams.bangumi_priority" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">Bangumi 故障转移</div>
                  <div class="strategy-desc">当 TMDB 搜索失败时，自动使用 BGM 补全</div>
                </div>
                <n-switch v-model:value="forcedParams.bangumi_failover" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">强制单文件模式</div>
                  <div class="strategy-desc">将完整输入作为文件名解析，无视路径干扰</div>
                </div>
                <n-switch v-model:value="forcedParams.force_filename" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">智能记忆</div>
                  <div class="strategy-desc">自动记住系列特征，后续文件实现秒级拦截</div>
                </div>
                <n-switch v-model:value="forcedParams.series_fingerprint" />
              </div>
              <div class="strategy-row">
                <div class="strategy-info">
                  <div class="strategy-title">合集识别增强</div>
                  <div class="strategy-desc">支持解析 01-12 等合集，自动计算集数区间</div>
                </div>
                <n-switch v-model:value="forcedParams.batch_enhancement" />
              </div>
            </div>

            <n-grid :cols="4" :x-gap="12" class="mb-4 mt-4">
              <n-gi><AppTextField v-model:value="forcedParams.tmdb_id" label="TMDB ID" placeholder="TMDB ID" /></n-gi>
              <n-gi><AppSelectField v-model:value="forcedParams.type" label="资源类型" :options="[{label:'自动',value:null},{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="资源类型" clearable /></n-gi>
              <n-gi><AppTextField v-model:value="forcedParams.season" label="指定季" placeholder="指定季" /></n-gi>
              <n-gi><AppTextField v-model:value="forcedParams.episode" label="指定集" placeholder="指定集" /></n-gi>
            </n-grid>

            <AppSearchField v-model:value="testSearch.keyword" placeholder="快捷搜索剧名找 ID..." :loading="testSearch.loading" @search="searchTmdbForTest" class="mt-4" />
            <n-scrollbar v-if="testSearch.results.length > 0" class="search-res-list mt-2">
              <div
                v-for="res in testSearch.results"
                :key="res.id"
                class="search-result-item"
                @click="forcedParams.tmdb_id = String(res.id); forcedParams.type = res.media_type || forcedParams.type; testSearch.results = []"
              >
                <n-image width="50" :src="getImg(res.poster_path)" preview-disabled />
                <div class="search-result-info">
                  <div class="search-result-title">{{ res.title }} ({{ res.year }})</div>
                  <div class="search-result-sub">ID: {{ res.id }} · {{ res.category }} · {{ res.original_title || '-' }}</div>
                  <div v-if="res.genres?.length" class="search-result-sub">流派：{{ res.genres.join(' / ') }}</div>
                </div>
              </div>
            </n-scrollbar>

            <n-button type="primary" block size="small" class="mt-4" :loading="loading" @click="handleRecognize">
              开始识别
            </n-button>
          </div>

          <!-- 识别结果 - 有数据时才显示 -->
          <div v-if="data" class="result-section">
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
                     <a v-if="data.final_result.tmdb_id && data.final_result.tmdb_id !== 'N/A'" 
                        :href="`https://www.themoviedb.org/${data.final_result.category?.includes('电影') ? 'movie' : 'tv'}/${data.final_result.tmdb_id}`" 
                        target="_blank" class="id-link">TMDB: {{ data.final_result.tmdb_id }}</a>
                     <span v-else class="id-text">TMDB: {{ data.final_result.tmdb_id || 'N/A' }}</span>
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
                     <div class="fig-item"><div class="fig-l">介质来源</div><div class="fig-v">{{ data.final_result.source || '-' }}</div></div>
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

            <div v-if="hashResult" class="hash-result-box">
              <div class="pl" style="color: var(--n-success-color)"><n-icon><CheckIcon /></n-icon> 哈希已计算并入库</div>
              <div class="hash-info-grid">
                <div class="hi-row"><span class="hi-label">SHA1</span><span class="hi-value mono">{{ hashResult.sha1 }}</span></div>
                <div class="hi-row"><span class="hi-label">ED2K</span><span class="hi-value mono">{{ hashResult.ed2k }}</span></div>
                <div class="hi-row"><span class="hi-label">ED2K链接</span><span class="hi-value mono" style="font-size: 11px">{{ hashResult.ed2k_link }}</span></div>
              </div>
            </div>

            <n-collapse arrow-placement="right">
              <n-collapse-item title="查看深度识别审计日志" name="logs">
                <template #header-extra><n-icon><SearchBtnIcon /></n-icon></template>
                <div class="audit-log-box">
                  <div v-for="(log, i) in data.logs" :key="i" :class="['log-line', getLogClass(log)]">
                    <span class="idx">{{ String(i+1).padStart(2, '0') }}</span>
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
      <n-space justify="end" style="width: 100%">
        <n-space>
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-if="data" type="warning" :loading="isHashing" @click="calculateHash">
            计算哈希
          </n-button>
          <n-button v-if="data" v-bind="getButtonStyle('primary')" :loading="isRenaming" @click="emit('rename')">
            确认重命名
          </n-button>
        </n-space>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.res-detail { color: var(--text-secondary); }
.main-layout { display: flex; gap: 20px; padding: 4px 0; align-items: flex-start; }
.poster-box { flex-shrink: 0; }
.poster-img :deep(img) { border-radius: var(--card-border-radius, 8px); box-shadow: var(--shadow-md); }
.poster-placeholder { width: 120px; height: 180px; background: var(--bg-secondary); border: 1px dashed var(--border-dashed); border-radius: var(--card-border-radius, 8px); display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 12px; }
.details-box { flex-grow: 1; min-width: 0; }
.title-line { font-size: 20px; font-weight: bold; color: var(--text-primary); line-height: 1.3; margin-bottom: 8px; }
.pure-tags-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.p-tag { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; border: 1px solid transparent; }
.tag-green { color: var(--n-primary-color); background: var(--primary-light); border-color: var(--primary-medium); }
.tag-blue { color: var(--n-info-color); background: var(--info-light); border-color: var(--info-medium); }
.id-text { font-family: monospace; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
.id-link { font-family: monospace; color: var(--n-primary-color); font-size: 11px; margin-left: 4px; text-decoration: none; cursor: pointer; transition: color 0.2s; }
.id-link:hover { color: var(--n-info-color); text-decoration: underline; }
.date-text { color: var(--n-primary-color); font-size: 12px; margin-left: 4px; }
.pure-specs-row { display: flex; gap: 6px; margin-bottom: 12px; }
.p-badge { padding: 1px 6px; border-radius: 4px; font-size: 10px; background: var(--bg-surface); color: var(--text-muted); border: 1px solid var(--border-light); }
.p-badge.blue { color: var(--n-info-color); border-color: var(--info-medium); }
.flex-info-grid { display: flex; gap: 0; border-radius: 6px; margin-bottom: 16px; overflow: hidden; border: 1px solid var(--border-light); }
.fig-item { flex: 1; display: flex; flex-direction: column; align-items: center; padding: 8px 4px; }
.fig-item:not(:last-child) { border-right: 1px solid var(--border-light); }
.fig-l { font-size: 10px; color: var(--text-hint); text-transform: uppercase; font-weight: bold; margin-bottom: 2px; }
.fig-v { font-weight: bold; font-size: 14px; color: var(--n-primary-color); }
.text-info-rows { font-size: 12px; display: flex; flex-direction: column; gap: 6px; }
.row { display: flex; gap: 12px; align-items: flex-start; }
.rl { color: var(--text-hint); width: 80px; flex-shrink: 0; text-align: right; }
.rv { color: var(--text-secondary); word-break: break-all; }
.rv.team { color: var(--n-success-color); font-weight: bold; }
.rv.mono { 
  font-family: var(--code-font); 
  color: var(--n-warning-color); 
}

.preview-box { 
  background: var(--app-surface-card-mixed); 
  padding: 14px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--app-border-light); 
  box-sizing: border-box;
}
.preview-box .pl { font-size: 12px; font-weight: bold; color: var(--n-info-color); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.preview-box .pv { 
  font-family: var(--code-font); 
  font-size: 13px; 
  color: var(--text-primary); 
  word-break: break-all; 
  padding: 10px 0;
}

.hash-result-box { 
  background: var(--app-surface-card-mixed); 
  padding: 14px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--n-success-color); 
  box-sizing: border-box;
}
.hash-result-box .pl { font-size: 12px; font-weight: bold; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.hash-info-grid { display: flex; flex-direction: column; gap: 4px; }
.hi-row { display: flex; gap: 8px; align-items: baseline; }
.hi-label { font-size: 11px; color: var(--text-hint); width: 60px; flex-shrink: 0; text-align: right; }
.hi-value { font-size: 12px; color: var(--text-secondary); word-break: break-all; }
.hi-value.mono { font-family: var(--code-font); }

.forced-box { 
  background: var(--app-surface-card-mixed); 
  padding: 16px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--app-border-light); 
  box-sizing: border-box;
}
.forced-box .pl { font-size: 14px; font-weight: bold; color: var(--n-warning-color); margin-bottom: 16px; display: flex; align-items: center; gap: 6px; }

.strategy-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.strategy-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(0,0,0,0.05));
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.strategy-info { min-width: 0; }
.strategy-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.strategy-desc { font-size: 13px; color: var(--text-hint); line-height: 1.45; }
.search-res-list { border: 1px solid var(--app-border-light); border-radius: 6px; }
.search-result-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid var(--app-border-light); transition: background var(--transition-fast); }
.search-result-item:last-child { border-bottom: none; }
.search-result-item:hover { background: var(--app-surface-card-mixed); }
.search-result-item :deep(img) { border-radius: var(--button-border-radius, 4px); object-fit: cover; flex-shrink: 0; }
.search-result-info { flex: 1; min-width: 0; }
.search-result-title { font-size: 14px; font-weight: 600; color: var(--text-primary); line-height: 1.4; }
.search-result-sub { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; line-height: 1.4; }
.audit-log-box { padding: 12px; border-radius: 8px; border: 1px solid var(--app-border-light); font-family: var(--code-font); font-size: 12px; line-height: 1.6; }
.log-line { display: flex; gap: 8px; border-bottom: 1px solid var(--border-light); padding: 2px 0; }
.log-line .idx { color: var(--text-hint); font-size: 10px; width: 20px; flex-shrink: 0; }
.log-line.p { color: var(--n-primary-color); font-weight: bold; margin-top: 8px; border-bottom: 1px solid var(--app-border-light); }
.log-line.d { color: var(--n-info-color); }
.log-line.s { color: var(--n-primary-color); }
.log-line.w { color: var(--n-warning-color); }
.log-line.i { color: var(--n-warning-color); font-weight: bold; }
</style>
