<script setup lang="ts">
import { 
  NGrid, NGi, NInput, NButton, NSwitch, NCollapse, NCollapseItem,
  NCard, NSpace, NAvatar, NList, NListItem, NIcon, NScrollbar, NFormItem, 
  NSelect, NDivider, NTabs, NTabPane, NInputGroup
} from 'naive-ui'
import {
  PlayCircleOutlined as PlayIcon,
  TuneOutlined as TuneIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import RecognitionLogsView from '../../views/RecognitionLogsView.vue'
import RecognitionResult from '../../components/RecognitionResult.vue'
import { useHome } from '../../composables/views/useHome'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  API_BASE,
  sandboxSearch,
  recognitionState,
  getImg,
  handleRecognize,
  searchTmdbForSandbox,
  selectSandboxResult
} = useHome()
</script>

<template>
  <div class="home-view">
    <div class="page-header">
      <div>
        <h1>识别控制台</h1>
        <div class="subtitle">DASHBOARD & RECOGNITION</div>
      </div>
    </div>

    <n-grid x-gap="12" y-gap="12" cols="1 1000:4" class="mb-4">
      <n-gi span="3">
         <n-card content-style="padding: 0;" bordered>
            <n-tabs type="line" size="large" justify-content="start" tab-style="padding: 12px 24px;">
              <n-tab-pane name="dashboard" tab="识别仪表盘">
                <div style="padding: 20px;">
                  <n-space vertical size="large">
                    <!-- Search Hero -->
                    <div class="search-hero">
                      <n-input-group>
                        <n-input 
                          v-model:value="recognitionState.filename" 
                          size="large" 
                          placeholder="粘贴文件名或完整路径进行深度解析..." 
                          clearable 
                          @keypress.enter="handleRecognize"
                          style="flex: 1; font-family: monospace;"
                        >
                          <template #prefix>
                            <n-icon :component="SearchIcon" />
                          </template>
                        </n-input>
                        <n-button type="primary" size="large" :loading="recognitionState.loading" @click="handleRecognize" style="padding: 0 24px; font-weight: bold;">
                          <template #icon>
                            <n-icon :component="PlayIcon" />
                          </template>
                          立即解析
                        </n-button>
                      </n-input-group>
                    </div>

                    <n-collapse display-directive="show">
                      <n-collapse-item name="1">
                        <template #header>
                          <div class="card-title-box">
                            <n-icon style="color: var(--n-primary-color)">
                              <TuneIcon />
                            </n-icon>
                            <span class="card-title-text">高级参数与临时调试</span>
                          </div>
                        </template>
                        
                        <n-grid :cols="40" :x-gap="12" :y-gap="12">
                          <n-gi :span="20">
                            <n-form-item label="搜索辅助 (TMDB)" path="sandboxSearch.keyword">
                              <n-input v-model:value="sandboxSearch.keyword" placeholder="输入剧名搜索..." @keypress.enter="searchTmdbForSandbox">
                                <template #suffix>
                                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="searchTmdbForSandbox" :loading="sandboxSearch.loading">
                                    <template #icon>
                                      <n-icon :component="SearchIcon" />
                                    </template>
                                  </n-button>
                                </template>
                              </n-input>
                            </n-form-item>
                            <n-scrollbar v-if="(sandboxSearch.results || []).length > 0" style="max-height: 120px" class="search-res-box mb-4">
                              <n-list hoverable clickable size="small">
                                <n-list-item 
                                  v-for="res in (sandboxSearch.results || [])" 
                                  :key="res.id" 
                                  @click="selectSandboxResult(res)"
                                >
                                  <template #prefix>
                                    <n-avatar :src="getImg(res.poster_path)" size="small" shape="square" />
                                  </template>
                                  <div style="font-size:12px;">
                                    <b>{{ res.title }}</b> ({{ res.year }}) <span style="opacity: 0.5">ID: {{ res.id }}</span>
                                  </div>
                                </n-list-item>
                              </n-list>
                            </n-scrollbar>
                          </n-gi>
                          <n-gi :span="5"><n-form-item label="强制 ID"><n-input v-model:value="recognitionState.forced_tmdb_id" placeholder="TMDB ID" /></n-form-item></n-gi>
                          <n-gi :span="5"><n-form-item label="媒体类型"><n-select v-model:value="recognitionState.forced_type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="Type" /></n-form-item></n-gi>
                          <n-gi :span="5"><n-form-item label="强制季号"><n-input v-model:value="recognitionState.forced_season" placeholder="Season" /></n-form-item></n-gi>
                          <n-gi :span="5"><n-form-item label="强制集号"><n-input v-model:value="recognitionState.forced_episode" placeholder="Episode" /></n-form-item></n-gi>
                          
                          <n-gi :span="40">
                            <n-divider dashed style="margin: 0">
                              <div class="sandbox-label">临时规则注入 (仅本次生效)</div>
                            </n-divider>
                          </n-gi>
                          <n-gi :span="13"><n-input v-model:value="recognitionState.temp_noise" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="屏蔽词 (Regex)" /></n-gi>
                          <n-gi :span="13"><n-input v-model:value="recognitionState.temp_groups" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="自定义制作组" /></n-gi>
                          <n-gi :span="14"><n-input v-model:value="recognitionState.temp_render" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="自定义渲染词" /></n-gi>
                        </n-grid>
                      </n-collapse-item>
                    </n-collapse>

                    <RecognitionResult v-if="recognitionState.data?.final_result" />
                  </n-space>
                </div>
              </n-tab-pane>

              <n-tab-pane name="logs" tab="识别审计日志">
                 <RecognitionLogsView />
              </n-tab-pane>
            </n-tabs>
         </n-card>
      </n-gi>
      
      <n-gi span="1">
        <n-card title="识别偏好" size="small" segmented class="preference-card">
          <n-scrollbar style="max-height: 600px">
            <div class="pref-list">
              <!-- 动漫识别优化 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">动漫识别优化</div>
                  <div class="pref-desc">开启后提升动画匹配精度，过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="recognitionState.animePriority" size="small" />
              </div>

              <!-- 本地数据中心 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">本地数据中心</div>
                  <div class="pref-desc">优先碰撞本地数据库，实现毫秒级离线匹配</div>
                </div>
                <n-switch v-model:value="recognitionState.offlinePriority" size="small" />
              </div>

              <!-- Bangumi 数据源 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 数据源优先</div>
                  <div class="pref-desc">针对新番或缺失条目，优先尝试 BGM 镜像</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiPriority" size="small" />
              </div>

              <!-- Bangumi 故障转移 -->
              <div class="pref-item" :style="{ opacity: recognitionState.bangumiPriority ? 0.5 : 1 }">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 故障转移</div>
                  <div class="pref-desc">当 TMDB 搜索失败时，自动使用 BGM 补全</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiFailover" size="small" :disabled="recognitionState.bangumiPriority" />
              </div>

              <!-- 强制单文件 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">强制单文件模式</div>
                  <div class="pref-desc">将完整输入作为文件名解析，无视路径干扰</div>
                </div>
                <n-switch v-model:value="recognitionState.forceFilename" size="small" />
              </div>

              <!-- 智能记忆 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">智能记忆</div>
                  <div class="pref-desc">自动记住系列特征，后续文件实现秒级拦截</div>
                </div>
                <n-switch v-model:value="recognitionState.seriesFingerprint" size="small" />
              </div>

              <!-- 合集增强 -->
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">合集识别增强</div>
                  <div class="pref-desc">支持解析 01-12 等合集，自动计算集数区间</div>
                </div>
                <n-switch v-model:value="recognitionState.batchEnhancement" size="small" />
              </div>
            </div>
          </n-scrollbar>
          <template #footer>
             <div style="font-size: 11px; color: var(--text-muted); text-align: center;">
                偏好设置会自动保存至本地浏览器
             </div>
          </template>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<style scoped>
.search-hero { margin-bottom: 20px; }
.label-text { font-size: 13px; color: var(--n-text-color-3); font-weight: 500; }
.sandbox-label { font-size: 12px; font-weight: 700; color: var(--n-primary-color); margin-bottom: 0; }
.search-res-box { border: 1px solid var(--app-border-light); border-radius: 6px; background: var(--app-surface-inner); margin-top: 8px; }
.preference-card { height: 100%; }
.pref-list { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.pref-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-surface); border-radius: 8px; border: 1px solid var(--border-light); transition: all 0.3s ease; }
.pref-item:hover { background: var(--bg-surface-hover); border-color: var(--n-primary-color); }
.pref-info { flex: 1; margin-right: 12px; }
.pref-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-1); }
.pref-desc { font-size: 11px; color: var(--n-text-color-3); margin-top: 2px; line-height: 1.2; }
</style>