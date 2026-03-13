<script setup lang="ts">
import { onMounted } from 'vue'
import { 
  NButton, NIcon, NTabs, NTabPane, NDropdown, NSpace
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  MoreVertOutlined as MoreIcon,
  CloudSyncOutlined as SyncIcon
} from '@vicons/material'

import FeedEditModal from '../../components/FeedEditModal.vue'
import RssRuleModal from '../../components/RssRuleModal.vue'
import FeedItemsModal from '../../components/FeedItemsModal.vue'
import RulePreviewModal from '../../components/RulePreviewModal.vue'
import RuleHistoryModal from '../../components/RuleHistoryModal.vue'
import MobileSubscriptionManager from '../../components/mobile/MobileSubscriptionManager.vue'
import MobileFeedList from '../../components/mobile/MobileFeedList.vue'
import MobileRuleList from '../../components/mobile/MobileRuleList.vue'
import { useSubscriptionView } from '../../composables/views/useSubscriptionView'
import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  feeds,
  rules,
  clients,
  showFeedModal,
  showRuleModal,
  showItemsModal,
  showPreviewModal,
  showHistoryModal,
  currentItem,
  previewRuleData,
  isNew,
  fetchData,
  openAddFeed,
  openEditFeed,
  saveFeed,
  deleteFeed,
  openViewItems,
  openViewHistory,
  resetFeedHistory,
  openAddRule,
  openEditRule,
  saveRule,
  duplicateRule,
  deleteRule,
  handlePreviewRule,
  runNow,
  retryRecognition,
  clearCache,
  clearBlacklist,
  syncJackettFeeds
} = useSubscriptionView()

// Apply Back Button support to Modals
useBackClose(showFeedModal)
useBackClose(showRuleModal)
useBackClose(showItemsModal)
useBackClose(showPreviewModal)
useBackClose(showHistoryModal)

// Mobile Global Actions
const mobileGlobalActions = [
  { label: '清空下载黑名单', key: 'clearBlacklist' },
  { label: '清空识别缓存', key: 'clearCache' },
  { label: '重试识别失败项', key: 'retry' },
  { label: '立即触发全量刷新', key: 'runNow' }
]

const handleMobileGlobalAction = (key: string) => {
  if (key === 'clearBlacklist') {
     if(confirm('确定清空下载黑名单吗？')) clearBlacklist()
  }
  else if (key === 'clearCache') {
     if(confirm('确定清空识别缓存吗？')) clearCache()
  }
  else if (key === 'retry') retryRecognition()
  else if (key === 'runNow') runNow()
}

onMounted(fetchData)
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- 页面头部 -->
    <div class="m-header m-header-plain">
      <h1 class="m-header-title">订阅与下载</h1>
      <n-dropdown trigger="click" :options="mobileGlobalActions" @select="handleMobileGlobalAction">
        <n-button v-bind="getButtonStyle('icon')">
          <template #icon><n-icon><MoreIcon/></n-icon></template>
        </n-button>
      </n-dropdown>
    </div>

    <n-tabs type="line" animated class="m-tabs" pane-class="m-tab-content">
      <!-- 追剧订阅管理 -->
      <n-tab-pane name="subscriptions" tab="追剧订阅">
        <MobileSubscriptionManager :clients="clients" />
      </n-tab-pane>

      <!-- 订阅源管理 -->
      <n-tab-pane name="feeds" tab="订阅源">
        <div class="m-tab-content">
          <n-space vertical size="medium">
            <n-button v-bind="getButtonStyle('secondary')" block dashed @click="syncJackettFeeds">
              <template #icon><n-icon><SyncIcon /></n-icon></template>
              同步 Jackett 源
            </n-button>
            <n-button v-bind="getButtonStyle('primary')" block dashed @click="openAddFeed">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              新增订阅源
            </n-button>
          </n-space>
          <div class="m-mt-lg">
            <MobileFeedList 
              :feeds="feeds" 
              @edit="openEditFeed"
              @delete="deleteFeed"
              @reset="resetFeedHistory"
              @viewItems="openViewItems"
            />
          </div>
        </div>
      </n-tab-pane>

      <!-- 自动下载规则 -->
      <n-tab-pane name="rules" tab="下载规则">
        <div class="m-tab-content">
          <n-button v-bind="getButtonStyle('warning')" block dashed class="m-mb-lg" @click="openAddRule">
            <template #icon><n-icon><AddIcon/></n-icon></template>
            创建新规则
          </n-button>
          <MobileRuleList 
            :rules="rules"
            @edit="openEditRule"
            @delete="deleteRule"
            @duplicate="duplicateRule"
            @viewHistory="openViewHistory"
          />
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- Modals -->
    <FeedEditModal 
      v-model:show="showFeedModal" 
      :feed-data="currentItem" 
      :is-new="isNew"
      @save="saveFeed"
    />

    <RssRuleModal
      v-model:show="showRuleModal"
      :rule-data="currentItem"
      :is-new="isNew"
      :feeds="feeds"
      :clients="clients"
      @save="saveRule"
      @preview="handlePreviewRule"
    />

    <FeedItemsModal
      v-model:show="showItemsModal"
      :feed="currentItem"
      :clients="clients"
    />

    <RulePreviewModal
      v-model:show="showPreviewModal"
      :rule-data="previewRuleData"
      :clients="clients"
    />

    <RuleHistoryModal
      v-model:show="showHistoryModal"
      :rule="currentItem"
      :clients="clients"
    />

  </div>
</template>

<style scoped>
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
</style>
