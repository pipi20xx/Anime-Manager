<script setup lang="ts">
import { 
  NTabs, NTabPane
} from 'naive-ui'
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
  <div class="guide-view">
    <div class="header mb-8">
      <h1>规则使用说明</h1>
      <div class="subtitle">规则与正则指南</div>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated class="guide-tabs">
      <!-- TAB 0: 设置说明 -->
      <n-tab-pane name="settings" tab="设置说明">
        <SettingsGuide />
      </n-tab-pane>

      <!-- TAB 1: 全链路识别流水线 -->
      <n-tab-pane name="pipeline" tab="全链路识别流水线">
        <RecognitionPipeline />
      </n-tab-pane>

      <!-- TAB 2: 识别词 -->
      <n-tab-pane name="recognition" tab="自定义识别词 (预处理)">
        <RecognitionRules />
      </n-tab-pane>

      <!-- TAB 3: 特权规则 -->
      <n-tab-pane name="privileged" tab="自定义特权规则 (优先提取)">
        <PrivilegedRules />
      </n-tab-pane>

      <!-- TAB 4: 渲染词 -->
      <n-tab-pane name="render" tab="自定义渲染词 (后处理)">
        <RenderRules />
      </n-tab-pane>

      <!-- TAB 5: 下载规则 (RSS) -->
      <n-tab-pane name="rss" tab="下载规则配置 (RSS)">
        <RssRuleGuide />
      </n-tab-pane>

      <!-- TAB 6: 追剧订阅 (TMDB) -->
      <n-tab-pane name="subscription" tab="追剧订阅配置 (TMDB)">
        <SubscriptionGuide />
      </n-tab-pane>

      <!-- TAB 7: STRM -->
      <n-tab-pane name="strm" tab="虚拟库 (STRM)">
        <StrmGuide />
      </n-tab-pane>

      <!-- TAB 8: 数据中心架构 -->
      <n-tab-pane name="datacenter" tab="数据中心架构">
        <DataCenterGuide />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.guide-view { width: 100%; margin: 0 auto; padding: 0; }
.header h1 { margin: 0; font-size: 28px; color: var(--n-text-color-1); }
.subtitle { font-size: 12px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.mb-8 { margin-bottom: 32px; }

/* Tabs 滑动条样式 */
.guide-tabs :deep(.n-tabs-nav-scroll-content) {
  overflow-x: auto !important;
  overflow-y: hidden !important;
  scrollbar-width: thin !important;
  scrollbar-color: var(--n-scrollbar-color-hover) var(--n-scrollbar-color) !important;
}

.guide-tabs :deep(.n-tabs-nav-scroll-content)::-webkit-scrollbar {
  height: 10px !important;
}

.guide-tabs :deep(.n-tabs-nav-scroll-content)::-webkit-scrollbar-track {
  background: var(--n-scrollbar-color) !important;
  border-radius: 5px !important;
}

.guide-tabs :deep(.n-tabs-nav-scroll-content)::-webkit-scrollbar-thumb {
  background: var(--n-scrollbar-color-hover) !important;
  border-radius: 5px !important;
  border: 2px solid var(--n-scrollbar-color) !important;
}

.guide-tabs :deep(.n-tabs-nav-scroll-content)::-webkit-scrollbar-thumb:hover {
  background: var(--n-primary-color) !important;
}

/* 滑动条提示 */
.guide-tabs :deep(.n-tabs-nav)::after {
  content: '→ 滑动查看更多';
  position: fixed;
  right: 20px;
  top: 140px;
  background: var(--n-primary-color);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: bold;
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.guide-tabs :deep(.n-tabs-nav:hover)::after {
  opacity: 1;
}
</style>
