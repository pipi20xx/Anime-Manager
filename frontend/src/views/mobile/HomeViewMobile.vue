<script setup lang="ts">
import { ref } from 'vue'
import { 
  NInput, NButton, NSwitch, NCollapse, NCollapseItem,
  NCard, NSpace, NAvatar, NList, NListItem, NIcon, NScrollbar, NFormItem, 
  NSelect, NDivider, NTabs, NTabPane, NInputGroup
} from 'naive-ui'
import {
  PlayCircleOutlined as PlayIcon,
  TuneOutlined as TuneIcon,
  SearchOutlined as SearchIcon,
  SettingsOutlined as SettingsIcon
} from '@vicons/material'
import RecognitionLogsView from '../../views/RecognitionLogsView.vue'
import RecognitionResult from '../../components/RecognitionResult.vue'
import { useHome } from '../../composables/views/useHome'

const {
  sandboxSearch,
  recognitionState,
  getImg,
  handleRecognize,
  searchTmdbForSandbox,
  selectSandboxResult
} = useHome()

const activeTab = ref('dashboard')
</script>

<template>
  <div class="home-view-mobile">
    <n-tabs type="line" animated v-model:value="activeTab" class="mobile-tabs" pane-class="mobile-tab-pane">
      <n-tab-pane name="dashboard" tab="控制台">
        <div class="tab-content">
          <!-- Hero Input -->
          <div class="mobile-hero">
             <n-input 
                v-model:value="recognitionState.filename" 
                type="textarea" 
                placeholder="输入文件名/路径..." 
                :autosize="{ minRows: 2, maxRows: 4 }" 
                style="font-family: monospace; margin-bottom: 8px;"
              />
              <n-button block type="primary" size="large" :loading="recognitionState.loading" @click="handleRecognize">
                <template #icon><n-icon :component="PlayIcon" /></template>
                立即解析
              </n-button>
          </div>

          <n-collapse style="margin-bottom: 16px;">
            <n-collapse-item name="1">
              <template #header>
                <span style="font-weight: bold; color: var(--n-primary-color)">高级参数 & 调试</span>
              </template>
              <n-card size="small" embedded class="debug-card">
                 <n-form-item label="搜索辅助 (TMDB)">
                    <n-input-group>
                      <n-input v-model:value="sandboxSearch.keyword" placeholder="搜索..." />
                      <n-button @click="searchTmdbForSandbox" :loading="sandboxSearch.loading"><n-icon :component="SearchIcon" /></n-button>
                    </n-input-group>
                 </n-form-item>
                 
                 <n-list v-if="(sandboxSearch.results || []).length > 0" clickable hoverable style="margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;">
                    <n-list-item v-for="res in sandboxSearch.results" :key="res.id" @click="selectSandboxResult(res)">
                       <div style="display: flex; gap: 8px; align-items: center;">
                          <n-avatar :src="getImg(res.poster_path)" size="small" shape="square" />
                          <div style="font-size: 12px;">{{ res.title }} ({{ res.id }})</div>
                       </div>
                    </n-list-item>
                 </n-list>

                 <n-space vertical size="small">
                    <n-input v-model:value="recognitionState.forced_tmdb_id" placeholder="强制 TMDB ID" />
                    <n-select v-model:value="recognitionState.forced_type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" />
                    <div class="row-inputs">
                       <n-input v-model:value="recognitionState.forced_season" placeholder="季 S" style="flex: 1" />
                       <n-input v-model:value="recognitionState.forced_episode" placeholder="集 E" style="flex: 1" />
                    </div>
                    <n-divider dashed>临时注入</n-divider>
                    <n-input v-model:value="recognitionState.temp_noise" placeholder="屏蔽词正则" />
                    <n-input v-model:value="recognitionState.temp_groups" placeholder="自定义制作组" />
                    <n-input v-model:value="recognitionState.temp_render" placeholder="渲染替换" />
                 </n-space>
              </n-card>
            </n-collapse-item>
          </n-collapse>

          <!-- Result -->
          <div class="result-container">
            <RecognitionResult v-if="recognitionState.data?.final_result" />
          </div>
        </div>
      </n-tab-pane>

      <n-tab-pane name="prefs" tab="偏好">
         <div class="tab-content">
            <div class="pref-list">
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">动漫识别优化</div>
                  <div class="pref-desc">过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="recognitionState.animePriority" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">本地数据中心</div>
                  <div class="pref-desc">优先匹配本地库</div>
                </div>
                <n-switch v-model:value="recognitionState.offlinePriority" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 优先</div>
                  <div class="pref-desc">优先 BGM 数据源</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiPriority" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 故障转移</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiFailover" :disabled="recognitionState.bangumiPriority" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">强制单文件</div>
                </div>
                <n-switch v-model:value="recognitionState.forceFilename" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">智能记忆</div>
                </div>
                <n-switch v-model:value="recognitionState.seriesFingerprint" />
              </div>
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">合集增强</div>
                </div>
                <n-switch v-model:value="recognitionState.batchEnhancement" />
              </div>
            </div>
         </div>
      </n-tab-pane>

      <n-tab-pane name="logs" tab="日志">
         <RecognitionLogsView />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.home-view-mobile {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--app-background);
  padding-bottom: 80px; /* Space for bottom nav */
}

.mobile-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 0 16px;
}

:deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

:deep(.mobile-tab-pane) {
  height: 100%;
  overflow-y: auto;
  padding: 0;
}

.tab-content {
  padding: 16px;
}

.mobile-hero { margin-bottom: 16px; }

.row-inputs { display: flex; gap: 8px; }

.debug-card { border-radius: 8px; border: 1px solid var(--n-border-color); }

.pref-list { display: flex; flex-direction: column; gap: 12px; }
.pref-item { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--bg-surface); border-radius: 8px; border: 1px solid var(--border-light); }
.pref-label { font-weight: bold; font-size: 14px; }
.pref-desc { font-size: 11px; color: var(--text-muted); }

.result-container {
  overflow-x: hidden; /* Prevent horizontal scroll */
  width: 100%;
}
</style>
