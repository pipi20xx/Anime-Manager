<script setup lang="ts">
import { NTabs, NTabPane } from 'naive-ui'
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

    <n-tabs v-model:value="activeTab" type="line" animated class="custom-tabs">
      <n-tab-pane name="settings" tab="设置说明">
        <SettingsGuide />
      </n-tab-pane>
      <n-tab-pane name="pipeline" tab="全链路识别流水线">
        <RecognitionPipeline />
      </n-tab-pane>
      <n-tab-pane name="recognition" tab="自定义识别词 (预处理)">
        <RecognitionRules />
      </n-tab-pane>
      <n-tab-pane name="privileged" tab="自定义特权规则 (优先提取)">
        <PrivilegedRules />
      </n-tab-pane>
      <n-tab-pane name="render" tab="自定义渲染词 (后处理)">
        <RenderRules />
      </n-tab-pane>
      <n-tab-pane name="rss" tab="下载规则配置 (RSS)">
        <RssRuleGuide />
      </n-tab-pane>
      <n-tab-pane name="subscription" tab="追剧订阅配置 (TMDB)">
        <SubscriptionGuide />
      </n-tab-pane>
      <n-tab-pane name="strm" tab="虚拟库 (STRM)">
        <StrmGuide />
      </n-tab-pane>
      <n-tab-pane name="datacenter" tab="数据中心架构">
        <DataCenterGuide />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.guide-view { width: 100%; margin: 0 auto; padding: 0; }
.header h1 { margin: 0; font-size: var(--text-2xl); color: var(--text-primary); }
.subtitle { font-size: var(--text-base); color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.mb-8 { margin-bottom: 32px; }

/* Tabs 间距：覆盖全局 --tabs-pane-padding，避免内容紧贴 Tabs 导航栏 */
.custom-tabs { --tabs-pane-padding: 16px 0 0 0; }
</style>
