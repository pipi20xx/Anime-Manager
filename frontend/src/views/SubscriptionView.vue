<script setup lang="ts">
/**
 * SubscriptionView — 订阅管理
 *
 * 重构: 拆分为三个子Tab组件 + 公共操作栏
 * - SubscriptionsTab: 追剧订阅 (海报卡片、Bangumi一键订阅、补全等)
 * - FeedsTab: 订阅源管理 (Feed CRUD、Jackett同步、TMDB屏蔽)
 * - RulesTab: 下载规则 (规则CRUD、复制、预览)
 */
import { ref } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import SubscriptionsTab from './subscription/SubscriptionsTab.vue'
import FeedsTab from './subscription/FeedsTab.vue'
import RulesTab from './subscription/RulesTab.vue'

defineOptions({ name: 'SubscriptionView' })

const activeTab = ref('subscriptions')

// Tab 组件引用
const subscriptionsTabRef = ref<InstanceType<typeof SubscriptionsTab> | null>(null)
const feedsTabRef = ref<InstanceType<typeof FeedsTab> | null>(null)
const rulesTabRef = ref<InstanceType<typeof RulesTab> | null>(null)

function refreshCurrentTab() {
  if (activeTab.value === 'subscriptions') subscriptionsTabRef.value?.fetchSubscriptions()
  else if (activeTab.value === 'feeds') feedsTabRef.value?.fetchFeeds()
  else if (activeTab.value === 'rules') rulesTabRef.value?.fetchRules()
}

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '追剧订阅', tab: 'subscriptions' },
    { title: '订阅源', tab: 'feeds' },
    { title: '下载规则', tab: 'rules' },
  ],
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <v-window-item value="subscriptions">
        <SubscriptionsTab ref="subscriptionsTabRef" />
      </v-window-item>
      <v-window-item value="feeds">
        <FeedsTab ref="feedsTabRef" />
      </v-window-item>
      <v-window-item value="rules">
        <RulesTab ref="rulesTabRef" />
      </v-window-item>
    </v-window>
  </v-container>
</template>
