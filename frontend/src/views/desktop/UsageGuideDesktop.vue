<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButtonGroup, NButton } from 'naive-ui'
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

const row1 = [
  { key: 'settings', label: '设置说明' },
  { key: 'pipeline', label: '全链路识别流水线' },
  { key: 'recognition', label: '自定义识别词 (预处理)' },
  { key: 'privileged', label: '自定义特权规则 (优先提取)' },
  { key: 'render', label: '自定义渲染词 (后处理)' },
]

const row2 = [
  { key: 'rss', label: '下载规则配置 (RSS)' },
  { key: 'subscription', label: '追剧订阅配置 (TMDB)' },
  { key: 'strm', label: '虚拟库 (STRM)' },
  { key: 'datacenter', label: '数据中心架构' },
]
</script>

<template>
  <div class="guide-view">
    <div class="header mb-8">
      <h1>规则使用说明</h1>
      <div class="subtitle">规则与正则指南</div>
    </div>

    <div class="tab-nav">
      <n-button-group size="small" class="tab-row">
        <n-button
          v-for="t in row1" :key="t.key"
          :type="activeTab === t.key ? 'primary' : 'tertiary'"
          :ghost="activeTab !== t.key"
          @click="activeTab = t.key"
        >
          {{ t.label }}
        </n-button>
      </n-button-group>
      <n-button-group size="small" class="tab-row">
        <n-button
          v-for="t in row2" :key="t.key"
          :type="activeTab === t.key ? 'primary' : 'tertiary'"
          :ghost="activeTab !== t.key"
          @click="activeTab = t.key"
        >
          {{ t.label }}
        </n-button>
      </n-button-group>
    </div>

    <div class="tab-content">
      <SettingsGuide v-if="activeTab === 'settings'" />
      <RecognitionPipeline v-else-if="activeTab === 'pipeline'" />
      <RecognitionRules v-else-if="activeTab === 'recognition'" />
      <PrivilegedRules v-else-if="activeTab === 'privileged'" />
      <RenderRules v-else-if="activeTab === 'render'" />
      <RssRuleGuide v-else-if="activeTab === 'rss'" />
      <SubscriptionGuide v-else-if="activeTab === 'subscription'" />
      <StrmGuide v-else-if="activeTab === 'strm'" />
      <DataCenterGuide v-else-if="activeTab === 'datacenter'" />
    </div>
  </div>
</template>

<style scoped>
.guide-view { width: 100%; margin: 0 auto; padding: 0; }
.header h1 { margin: 0; font-size: var(--text-2xl); color: var(--text-primary); }
.subtitle { font-size: var(--text-base); color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.mb-8 { margin-bottom: 32px; }

.tab-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.tab-row {
  flex-wrap: wrap;
}

.tab-content {
  margin-top: 16px;
}
</style>
