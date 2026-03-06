<script setup lang="ts">
import { 
  NTabs, NTabPane, NIcon
} from 'naive-ui'
import {
  AltRouteOutlined as PipelineIcon,
  SpellcheckOutlined as TextIcon,
  StarOutlined as PrivilegedIcon,
  FormatPaintOutlined as RenderIcon,
  RssFeedOutlined as RssIcon,
  SubscriptionsOutlined as SubIcon,
  MovieOutlined as StrmIcon,
  StorageOutlined as DataIcon,
  SettingsOutlined as SettingsIcon
} from '@vicons/material'
import RecognitionPipeline from '../../components/RecognitionPipeline.vue'
import RecognitionRules from '../../components/RecognitionRules.vue'
import PrivilegedRules from '../../components/PrivilegedRules.vue'
import RenderRules from '../../components/RenderRules.vue'
import RssRuleGuide from '../../components/RssRuleGuide.vue'
import SubscriptionGuide from '../../components/SubscriptionGuide.vue'
import DataCenterGuide from '../../components/DataCenterGuide.vue'
import StrmGuide from '../../components/StrmGuide.vue'
import SettingsGuide from '../../components/SettingsGuide.vue'
import { useUsageGuide } from '../../composables/views/useUsageGuide'

const { activeTab } = useUsageGuide()
</script>

<template>
  <div class="mobile-guide-view">
    <div class="mobile-header">
      <h2>规则使用说明</h2>
    </div>

    <n-tabs 
      v-model:value="activeTab" 
      type="line" 
      animated
      class="mobile-tabs"
      pane-class="mobile-tab-pane"
    >
      <n-tab-pane name="settings" tab="设置说明">
        <template #tab>
           <div class="tab-label"><n-icon><SettingsIcon /></n-icon><span>设置</span></div>
        </template>
        <div class="content-wrapper">
          <SettingsGuide />
        </div>
      </n-tab-pane>

      <n-tab-pane name="pipeline" tab="识别流水线">
        <template #tab>
          <div class="tab-label"><n-icon><PipelineIcon /></n-icon><span>流水线</span></div>
        </template>
        <div class="content-wrapper">
          <RecognitionPipeline />
        </div>
      </n-tab-pane>

      <n-tab-pane name="recognition" tab="识别词">
        <template #tab>
           <div class="tab-label"><n-icon><TextIcon /></n-icon><span>识别词</span></div>
        </template>
        <div class="content-wrapper">
          <RecognitionRules />
        </div>
      </n-tab-pane>

      <n-tab-pane name="privileged" tab="特权规则">
        <template #tab>
           <div class="tab-label"><n-icon><PrivilegedIcon /></n-icon><span>特权</span></div>
        </template>
        <div class="content-wrapper">
          <PrivilegedRules />
        </div>
      </n-tab-pane>

      <n-tab-pane name="render" tab="渲染词">
        <template #tab>
           <div class="tab-label"><n-icon><RenderIcon /></n-icon><span>渲染词</span></div>
        </template>
        <div class="content-wrapper">
          <RenderRules />
        </div>
      </n-tab-pane>

      <n-tab-pane name="rss" tab="RSS规则">
        <template #tab>
           <div class="tab-label"><n-icon><RssIcon /></n-icon><span>RSS</span></div>
        </template>
        <div class="content-wrapper">
          <RssRuleGuide />
        </div>
      </n-tab-pane>

      <n-tab-pane name="subscription" tab="订阅配置">
        <template #tab>
           <div class="tab-label"><n-icon><SubIcon /></n-icon><span>订阅</span></div>
        </template>
        <div class="content-wrapper">
          <SubscriptionGuide />
        </div>
      </n-tab-pane>

      <n-tab-pane name="strm" tab="虚拟库">
        <template #tab>
           <div class="tab-label"><n-icon><StrmIcon /></n-icon><span>STRM</span></div>
        </template>
        <div class="content-wrapper">
          <StrmGuide />
        </div>
      </n-tab-pane>

      <n-tab-pane name="datacenter" tab="数据中心">
        <template #tab>
           <div class="tab-label"><n-icon><DataIcon /></n-icon><span>架构</span></div>
        </template>
        <div class="content-wrapper">
          <DataCenterGuide />
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.mobile-guide-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--app-background);
  padding-bottom: 80px; /* Bottom Nav Space */
}

.mobile-header {
  padding: 16px 16px 0 16px;
  flex-shrink: 0;
}
.mobile-header h2 { margin: 0; font-size: 20px; font-weight: 800; }

.mobile-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 0 8px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: auto;
  scrollbar-color: var(--n-scrollbar-color-hover) var(--n-scrollbar-color);
}

/* 移动端更明显的滑动条 */
:deep(.n-tabs-nav)::-webkit-scrollbar {
  height: 10px;
}

:deep(.n-tabs-nav)::-webkit-scrollbar-track {
  background: var(--n-scrollbar-color);
  border-radius: 5px;
  margin: 4px 0;
}

:deep(.n-tabs-nav)::-webkit-scrollbar-thumb {
  background: var(--n-scrollbar-color-hover);
  border-radius: 5px;
  border: 2px solid var(--n-scrollbar-color);
}

:deep(.n-tabs-nav)::-webkit-scrollbar-thumb:hover {
  background: var(--n-primary-color);
}

/* 移动端滑动提示 */
:deep(.n-tabs-nav)::after {
  content: '→ 滑动查看更多';
  position: fixed;
  right: 10px;
  top: 90px;
  background: var(--n-primary-color);
  color: white;
  padding: 8px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: bold;
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

:deep(.n-tabs-nav:hover)::after {
  opacity: 1;
}

:deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

:deep(.mobile-tab-pane) {
  height: 100%;
  overflow-y: auto;
  padding: 16px; 
}

.tab-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 10px;
  gap: 2px;
}
.tab-label .n-icon { font-size: 18px; }

/* Content Wrapper to enforce mobile styles on children */
.content-wrapper {
  padding-bottom: 24px;
}

/* Deep selectors to fix Markdown content on mobile */
.content-wrapper :deep(h1) { font-size: 1.3rem !important; margin-bottom: 0.8rem !important; }
.content-wrapper :deep(h2) { font-size: 1.15rem !important; margin-top: 1.2rem !important; }
.content-wrapper :deep(h3) { font-size: 1rem !important; }

/* Force tables to scroll */
.content-wrapper :deep(table) {
  display: block !important;
  width: 100% !important;
  overflow-x: auto !important;
  white-space: nowrap !important;
  margin: 1rem 0 !important;
}

.content-wrapper :deep(th), 
.content-wrapper :deep(td) {
  padding: 6px !important;
  font-size: 12px !important;
}

/* Fix code blocks */
.content-wrapper :deep(pre) {
  padding: 12px !important;
  overflow-x: auto !important;
  font-size: 12px !important;
}

.content-wrapper :deep(.n-card) {
  background: transparent !important;
  border: none !important;
}
.content-wrapper :deep(.n-card > .n-card__content) {
  padding: 0 !important;
}
</style>
