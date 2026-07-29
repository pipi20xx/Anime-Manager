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
import { subscriptionApi } from '@/api'
import { useNotification } from '@/composables'
import SubscriptionsTab from './subscription/SubscriptionsTab.vue'
import FeedsTab from './subscription/FeedsTab.vue'
import RulesTab from './subscription/RulesTab.vue'

defineOptions({ name: 'SubscriptionView' })

const { success, error: showError } = useNotification()

const activeTab = ref('subscriptions')
const syncing = ref(false)

// Tab 组件引用
const subscriptionsTabRef = ref<InstanceType<typeof SubscriptionsTab> | null>(null)
const feedsTabRef = ref<InstanceType<typeof FeedsTab> | null>(null)
const rulesTabRef = ref<InstanceType<typeof RulesTab> | null>(null)

async function runNow() {
  syncing.value = true
  try { await subscriptionApi.runNow(); success('已触发 RSS 刷新') }
  catch { showError('触发失败') }
  finally { syncing.value = false }
}

async function clearRecognitionCache() {
  try { await subscriptionApi.clearRecognitionCache(); success('识别缓存已清除') }
  catch { showError('清除失败') }
}

function refreshCurrentTab() {
  if (activeTab.value === 'subscriptions') subscriptionsTabRef.value?.fetchSubscriptions()
  else if (activeTab.value === 'feeds') feedsTabRef.value?.fetchFeeds()
  else if (activeTab.value === 'rules') rulesTabRef.value?.fetchRules()
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between flex-wrap ga-3">
      <div>
        <h1 class="text-h5 font-weight-bold">订阅管理</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">RSS 自动化追番与资源监控</div>
      </div>
      <div class="d-flex ga-2 flex-wrap">
        <v-btn variant="tonal" color="info" prepend-icon="mdi-refresh" :loading="syncing" @click="runNow">立即触发全量刷新</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-eraser" color="warning" @click="clearRecognitionCache">清空黑名单</v-btn>
      </div>
    </div>

    <!-- 标签切换 -->
    <v-tabs v-model="activeTab" color="primary" class="sticky-tabs">
      <v-tab value="subscriptions">追剧订阅</v-tab>
      <v-tab value="feeds">订阅源</v-tab>
      <v-tab value="rules">下载规则</v-tab>
    </v-tabs>

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
