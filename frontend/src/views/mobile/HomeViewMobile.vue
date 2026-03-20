<script setup lang="ts">
import { ref } from 'vue'
import { 
  NInput, NButton, NSwitch, NCollapse, NCollapseItem,
  NCard, NSpace, NAvatar, NList, NListItem, NIcon, NScrollbar, NFormItem, 
  NSelect, NDivider, NTabs, NTabPane, NInputGroup
} from 'naive-ui'
import {
  PlayCircleOutlined as PlayIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import RecognitionLogsView from '../../views/RecognitionLogsView.vue'
import RecognitionResult from '../../components/RecognitionResult.vue'
import { useHome } from '../../composables/views/useHome'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
  <div class="m-page m-page-safe-bottom">
    <n-tabs type="line" animated v-model:value="activeTab" class="m-tabs" pane-class="m-tab-content">
      <n-tab-pane name="dashboard" tab="控制台">
        <div class="m-tab-content">
          <!-- Hero Input -->
          <div class="m-form-group">
             <n-input 
                v-model:value="recognitionState.filename" 
                type="textarea" 
                placeholder="输入文件名/路径..." 
                :autosize="{ minRows: 2, maxRows: 4 }" 
                style="font-family: monospace; margin-bottom: var(--m-spacing-md);"
              />
              <n-button 
                block 
                type="primary" 
                size="large" 
                :loading="recognitionState.loading" 
                @click="handleRecognize"
              >
                立即解析
              </n-button>
          </div>

          <n-collapse class="m-mb-lg">
            <n-collapse-item name="1">
              <template #header>
                <span style="font-weight: bold; color: var(--n-primary-color)">高级参数 & 调试</span>
              </template>
              <div class="m-card m-card-compact">
                 <n-form-item label="搜索辅助 (TMDB)">
                    <n-input-group>
                      <n-input v-model:value="sandboxSearch.keyword" placeholder="搜索..." />
                      <n-button v-bind="getButtonStyle('primary')" @click="searchTmdbForSandbox" :loading="sandboxSearch.loading">
                        <n-icon :component="SearchIcon" />
                      </n-button>
                    </n-input-group>
                 </n-form-item>
                 
                 <n-list 
                    v-if="(sandboxSearch.results || []).length > 0" 
                    clickable 
                    hoverable 
                    class="m-mb-md"
                    style="border: 1px solid var(--border-light); border-radius: var(--m-radius-md);"
                 >
                    <n-list-item 
                      v-for="res in sandboxSearch.results" 
                      :key="res.id" 
                      @click="selectSandboxResult(res)"
                      class="m-touchable"
                    >
                       <div class="m-flex m-items-center m-gap-md">
                          <n-avatar :src="getImg(res.poster_path)" size="small" shape="square" />
                          <div style="font-size: var(--m-text-sm);">{{ res.title }} ({{ res.id }})</div>
                       </div>
                    </n-list-item>
                 </n-list>

                 <n-space vertical size="small">
                    <n-input v-model:value="recognitionState.forced_tmdb_id" placeholder="强制 TMDB ID" />
                    <n-select 
                      v-model:value="recognitionState.forced_type" 
                      :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" 
                    />
                    <div class="m-input-group">
                       <n-input v-model:value="recognitionState.forced_season" placeholder="季 S" />
                       <n-input v-model:value="recognitionState.forced_episode" placeholder="集 E" />
                    </div>
                    <n-divider dashed>临时注入 (仅本次生效)</n-divider>
                    <n-form-item label="自定义识别词">
                       <n-input v-model:value="recognitionState.temp_noise" placeholder="屏蔽词正则" />
                    </n-form-item>
                    <n-form-item label="自定义制作组">
                       <n-input v-model:value="recognitionState.temp_groups" placeholder="自定义制作组" />
                    </n-form-item>
                    <n-form-item label="自定义渲染词">
                       <n-input v-model:value="recognitionState.temp_render" placeholder="渲染替换" />
                    </n-form-item>
                    <n-form-item label="自定义特权规则">
                       <n-input v-model:value="recognitionState.temp_privilege" placeholder="特权规则 (每行一条)" />
                    </n-form-item>
                 </n-space>
              </div>
            </n-collapse-item>
          </n-collapse>

          <!-- Result -->
          <div class="result-container">
            <RecognitionResult v-if="recognitionState.data?.final_result" />
          </div>
        </div>
      </n-tab-pane>

      <n-tab-pane name="prefs" tab="偏好">
         <div class="m-tab-content">
            <div class="m-card-list">
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">动漫识别优化</div>
                  <div class="m-list-item-desc">过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="recognitionState.animePriority" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">本地数据中心</div>
                  <div class="m-list-item-desc">优先匹配本地库</div>
                </div>
                <n-switch v-model:value="recognitionState.offlinePriority" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">Bangumi 优先</div>
                  <div class="m-list-item-desc">优先 BGM 数据源</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiPriority" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">Bangumi 故障转移</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiFailover" :disabled="recognitionState.bangumiPriority" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">强制单文件</div>
                </div>
                <n-switch v-model:value="recognitionState.forceFilename" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">智能记忆</div>
                </div>
                <n-switch v-model:value="recognitionState.seriesFingerprint" />
              </div>
              <div class="m-card-item m-card-touchable m-list-item-touch">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">合集增强</div>
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
.m-page {
  background-color: var(--app-bg-color);
}

.m-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.m-tabs :deep(.n-tabs-nav) {
  padding: var(--m-spacing-sm) var(--m-spacing-lg);
  border-bottom: 1px solid var(--border-light);
}

.m-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

.m-tabs :deep(.n-tab-pane) {
  height: 100%;
  overflow-y: auto;
  padding: 0;
}

.m-tab-content {
  padding: var(--m-spacing-lg);
}

.result-container {
  overflow-x: hidden;
  width: 100%;
}

/* 偏好设置项的特殊样式 */
.m-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
