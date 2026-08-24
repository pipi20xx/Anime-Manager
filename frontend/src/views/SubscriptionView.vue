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
import { useNotification, useConfirm } from '@/composables'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import SubscriptionsTab from './subscription/SubscriptionsTab.vue'
import FeedsTab from './subscription/FeedsTab.vue'
import RulesTab from './subscription/RulesTab.vue'

defineOptions({ name: 'SubscriptionView' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const activeTab = ref('subscriptions')
const syncing = ref(false)

// Tab 组件引用
const subscriptionsTabRef = ref<InstanceType<typeof SubscriptionsTab> | null>(null)
const feedsTabRef = ref<InstanceType<typeof FeedsTab> | null>(null)
const rulesTabRef = ref<InstanceType<typeof RulesTab> | null>(null)

async function runNow() {
  const ok = await confirm({ title: '确认触发', content: '将立即触发所有订阅源的 RSS 全量刷新，可能产生较大负载，确定要继续吗？', confirmColor: 'info' })
  if (!ok) return
  syncing.value = true
  try { await subscriptionApi.runNow(); success('已触发 RSS 刷新') }
  catch { showError('触发失败') }
  finally { syncing.value = false }
}

async function clearRecognitionCache() {
  const ok = await confirm({ title: '确认清空', content: '清空黑名单后，之前被识别引擎排除的条目将不再被屏蔽，可能导致已忽略的资源重新进入下载流程。确定要继续吗？', confirmColor: 'warning' })
  if (!ok) return
  try { await subscriptionApi.clearRecognitionCache(); success('识别缓存已清除') }
  catch { showError('清除失败') }
}

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
  appendButtons: [
    {
      icon: 'mdi-refresh',
      text: '全量刷新',
      variant: 'tonal',
      color: 'info',
      action: runNow,
      show: true,
      loading: syncing,
    },
    {
      icon: 'mdi-eraser',
      text: '清空黑名单',
      variant: 'tonal',
      color: 'warning',
      action: clearRecognitionCache,
      show: true,
    },
  ],
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
