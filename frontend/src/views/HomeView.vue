<script setup lang="ts">
/**
 * HomeView - 识别调试台
 *
 * 使用 app-split-layout 实现:
 * - 桌面 (≥1024px): 主区域 + 偏好侧栏并排
 * - 移动 (<1024px): 主区域在上, 偏好在下
 *
 * 高级参数表单使用 app-form-grid 响应式布局
 */
import AppTextField from '../components/AppTextField.vue'
import AppSelectField from '../components/AppSelectField.vue'
import AppSearchField from '../components/AppSearchField.vue'
import {
  NButton, NSwitch, NCollapse, NCollapseItem,
  NCard, NSpace, NImage, NIcon, NScrollbar, NFormItem,
  NDivider, NTabs, NTabPane
} from 'naive-ui'
import {
  AdjustmentsHorizontalIcon as TuneIcon
} from '@heroicons/vue/24/outline'
import RecognitionLogsView from './desktop/RecognitionLogsDesktop.vue'
import RecognitionResult from '../components/RecognitionResult.vue'
import { useHome } from '../composables/views/useHome'

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
    <!-- 页面头部 -->
    <div class="app-page-header">
      <div>
        <h1>识别调试台</h1>
        <div class="subtitle">文件名识别测试与结果查看</div>
      </div>
    </div>

    <!-- 响应式分栏: 桌面 3:1, 移动堆叠 -->
    <div class="app-split-layout">
      <!-- 主区域 -->
      <div class="app-split-layout__main">
        <n-card content-style="padding: 0;" bordered>
          <n-tabs type="line" animated class="custom-tabs">
            <n-tab-pane name="dashboard" tab="识别测试">
              <div class="dashboard-content">
                <n-space vertical size="large">
                  <!-- 搜索入口 -->
                  <div class="search-hero">
                    <AppSearchField
                      v-model:value="recognitionState.filename"
                      placeholder="粘贴文件名或完整路径进行深度解析..."
                      :loading="recognitionState.loading"
                      :disabled="recognitionState.loading"
                      @search="handleRecognize"
                    />
                  </div>

                  <!-- 高级参数 -->
                  <n-collapse display-directive="show">
                    <n-collapse-item name="1">
                      <template #header>
                        <div class="card-title-box">
                          <n-icon style="color: var(--n-primary-color)"><TuneIcon /></n-icon>
                          <span class="card-title-text">高级参数与临时调试</span>
                        </div>
                      </template>

                      <!-- TMDB 搜索辅助 -->
                      <n-form-item>
                        <AppSearchField
                          v-model:value="sandboxSearch.keyword"
                          placeholder="搜索辅助 (TMDB)，输入剧名..."
                          :loading="sandboxSearch.loading"
                          @search="searchTmdbForSandbox"
                        />
                      </n-form-item>
                      <n-scrollbar v-if="(sandboxSearch.results || []).length > 0" class="search-res-box">
                        <div
                          v-for="res in (sandboxSearch.results || [])"
                          :key="res.id"
                          class="search-result-item"
                          @click="selectSandboxResult(res)"
                        >
                          <n-image width="50" :src="getImg(res.poster_path)" preview-disabled />
                          <div class="search-result-info">
                            <div class="search-result-title">{{ res.title }} ({{ res.year }})</div>
                            <div class="search-result-sub">ID: {{ res.id }} · {{ res.category }} · {{ res.original_title || '-' }}</div>
                            <div v-if="res.genres?.length" class="search-result-sub">流派：{{ res.genres.join(' / ') }}</div>
                          </div>
                        </div>
                      </n-scrollbar>

                      <!-- 强制参数: 响应式 2 列 -->
                      <div class="app-form-grid app-form-grid--2 adv-params-grid">
                        <n-form-item><AppTextField v-model:value="recognitionState.forced_tmdb_id" label="强制 ID" placeholder="TMDB ID" /></n-form-item>
                        <n-form-item><AppSelectField v-model:value="recognitionState.forced_type" label="媒体类型" :options="[{label:'自动',value:null},{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="Type" clearable /></n-form-item>
                        <n-form-item><AppTextField v-model:value="recognitionState.forced_season" label="强制季号" placeholder="Season" /></n-form-item>
                        <n-form-item><AppTextField v-model:value="recognitionState.forced_episode" label="强制集号" placeholder="Episode" /></n-form-item>
                      </div>

                      <n-divider dashed>
                        <div class="sandbox-label">临时规则注入 (仅本次生效)</div>
                      </n-divider>

                      <div class="app-form-grid">
                        <n-form-item><AppTextField v-model:value="recognitionState.temp_noise" label="自定义识别词" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="屏蔽词 (Regex)" /></n-form-item>
                        <n-form-item><AppTextField v-model:value="recognitionState.temp_groups" label="自定义制作组" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="自定义制作组" /></n-form-item>
                        <n-form-item><AppTextField v-model:value="recognitionState.temp_render" label="自定义渲染词" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="自定义渲染词" /></n-form-item>
                        <n-form-item><AppTextField v-model:value="recognitionState.temp_privilege" label="自定义特权规则" type="textarea" :autosize="{minRows:2, maxRows: 3}" placeholder="特权规则 (每行一条)" /></n-form-item>
                      </div>
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
      </div>

      <!-- 侧栏: 识别偏好 -->
      <div class="app-split-layout__side">
        <n-card title="识别偏好" size="small" segmented class="preference-card">
          <n-scrollbar style="max-height: 600px">
            <div class="pref-list">
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">动漫识别优化</div>
                  <div class="pref-desc">开启后提升动画匹配精度，过滤同名真人剧</div>
                </div>
                <n-switch v-model:value="recognitionState.animePriority" size="small" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">本地数据中心</div>
                  <div class="pref-desc">优先碰撞本地数据库，实现毫秒级离线匹配</div>
                </div>
                <n-switch v-model:value="recognitionState.offlinePriority" size="small" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 数据源优先</div>
                  <div class="pref-desc">针对新番或缺失条目，优先尝试 BGM 镜像</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiPriority" size="small" />
              </div>

              <div class="pref-item" :style="{ opacity: recognitionState.bangumiPriority ? 0.5 : 1 }">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 故障转移</div>
                  <div class="pref-desc">当 TMDB 搜索失败时，自动使用 BGM 补全</div>
                </div>
                <n-switch v-model:value="recognitionState.bangumiFailover" size="small" :disabled="recognitionState.bangumiPriority" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">强制单文件模式</div>
                  <div class="pref-desc">将完整输入作为文件名解析，无视路径干扰</div>
                </div>
                <n-switch v-model:value="recognitionState.forceFilename" size="small" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">智能记忆</div>
                  <div class="pref-desc">自动记住系列特征，后续文件实现秒级拦截</div>
                </div>
                <n-switch v-model:value="recognitionState.seriesFingerprint" size="small" />
              </div>

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
            <div class="pref-footer-hint">偏好设置会自动保存至本地浏览器</div>
          </template>
        </n-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-content { padding: var(--rsp-card-padding); }
.custom-tabs { --tabs-pane-padding: 16px 0 0 0; }

.search-hero { margin-bottom: var(--space-4); }

.card-title-box { display: flex; align-items: center; gap: var(--space-2); }
.card-title-text { font-weight: 600; color: var(--text-primary); }

.sandbox-label { font-size: var(--text-base); font-weight: 700; color: var(--n-primary-color); }

.search-res-box {
  border: 1px solid var(--app-border-light);
  border-radius: var(--radius-md);
  background: var(--app-surface-inner);
  margin-top: var(--space-2);
  max-height: 300px;
}
.search-result-item {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  border-bottom: 1px solid var(--app-border-light);
  transition: background var(--transition-fast);
}
.search-result-item:last-child { border-bottom: none; }
.search-result-item:hover { background: var(--app-surface-card-mixed); }
.search-result-item :deep(img) { border-radius: var(--button-border-radius, 4px); object-fit: cover; flex-shrink: 0; }
.search-result-info { flex: 1; min-width: 0; }
.search-result-title { font-size: var(--text-md); font-weight: 600; color: var(--text-primary); line-height: 1.4; }
.search-result-sub { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 2px; line-height: 1.4; }

.adv-params-grid { margin: var(--space-3) 0; }

.preference-card { height: 100%; }
.pref-list { display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-1) 0; }
.pref-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-2) var(--space-3);
  background: var(--app-surface-card-mixed);
  border-radius: var(--radius-lg);
  border: 1px solid var(--app-border-light);
  transition: all var(--transition-normal);
}
.pref-item:hover {
  background: color-mix(in srgb, var(--app-surface-card-mixed), rgba(255,255,255,0.04));
  border-color: var(--n-primary-color);
}
.pref-info { flex: 1; margin-right: var(--space-3); }
.pref-label { font-size: var(--text-md); font-weight: 600; color: var(--text-primary); }
.pref-desc { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 2px; line-height: 1.2; }
.pref-footer-hint { font-size: var(--text-xs); color: var(--text-muted); text-align: center; }

/* === 移动端适配 === */
@media (max-width: 767px) {
  .dashboard-content { padding: var(--space-3); }
  .search-hero { margin-bottom: var(--space-3); }
  .pref-desc { display: none; }
  .pref-label { font-size: var(--text-sm); }
  .preference-card :deep(.n-scrollbar) { max-height: none !important; }
  .pref-item { padding: var(--space-2); }
  /* 搜索结果项: 缩小图片 */
  .search-result-item { padding: var(--space-2); gap: var(--space-2); }
  .search-result-title { font-size: var(--text-sm); }
  .search-result-sub { font-size: var(--text-2xs); }
}
</style>
