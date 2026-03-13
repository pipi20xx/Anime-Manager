<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NButton, NIcon, NTabs, NTabPane, NSpace, NDrawer, NDrawerContent
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  MoreVertOutlined as MoreIcon,
  CloudSyncOutlined as SyncIcon,
  BlockOutlined as BlockIcon,
  CleaningServicesOutlined as CleanIcon,
  RefreshOutlined as RefreshIcon,
  PlayArrowOutlined as PlayIcon
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

// Mobile Global Actions Drawer
const showActionDrawer = ref(false)
useBackClose(showActionDrawer)

const actionItems = [
  { key: 'clearBlacklist', label: '清空下载黑名单', icon: BlockIcon, danger: true },
  { key: 'clearCache', label: '清空识别缓存', icon: CleanIcon, danger: false },
  { key: 'retry', label: '重试识别失败项', icon: RefreshIcon, danger: false },
  { key: 'runNow', label: '立即触发全量刷新', icon: PlayIcon, danger: false }
]

const handleAction = (key: string) => {
  showActionDrawer.value = false
  setTimeout(() => {
    if (key === 'clearBlacklist') {
       if(confirm('确定清空下载黑名单吗？')) clearBlacklist()
    }
    else if (key === 'clearCache') {
       if(confirm('确定清空识别缓存吗？')) clearCache()
    }
    else if (key === 'retry') retryRecognition()
    else if (key === 'runNow') runNow()
  }, 300)
}

onMounted(fetchData)
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- 页面头部 -->
    <div class="m-header m-header-plain">
      <h1 class="m-header-title">订阅与下载</h1>
      <div class="m-header-actions">
        <n-button v-bind="getButtonStyle('icon')" @click="showActionDrawer = true">
          <template #icon><n-icon><MoreIcon/></n-icon></template>
        </n-button>
      </div>
    </div>

    <n-tabs type="line" animated class="m-tabs" pane-class="m-tab-content">
      <!-- 追剧订阅管理 -->
      <n-tab-pane name="subscriptions" tab="追剧订阅">
        <MobileSubscriptionManager :clients="clients" />
      </n-tab-pane>

      <!-- 订阅源管理 -->
      <n-tab-pane name="feeds" tab="订阅源">
        <div class="m-tab-content">
          <!-- 操作按钮栏 -->
          <div class="m-action-bar">
            <n-button type="default" dashed size="small" @click="syncJackettFeeds">
              <template #icon><n-icon><SyncIcon /></n-icon></template>
              同步 Jackett
            </n-button>
            <n-button type="primary" dashed size="small" @click="openAddFeed">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              新增订阅源
            </n-button>
          </div>
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
          <div class="m-action-bar m-mb-lg">
            <n-button type="warning" dashed size="small" @click="openAddRule">
              <template #icon><n-icon><AddIcon/></n-icon></template>
              创建新规则
            </n-button>
          </div>
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

    <!-- 全局操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="actionItems.length * 100 + 60" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content closable title="更多操作" :native-scrollbar="false">
        <div class="action-list">
          <div
            v-for="item in actionItems"
            :key="item.key"
            class="action-item"
            :class="{ danger: item.danger }"
            @click="handleAction(item.key)"
          >
            <div class="action-icon">
              <n-icon size="22"><component :is="item.icon" /></n-icon>
            </div>
            <span class="action-label">{{ item.label }}</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

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

/* 操作按钮栏 */
.m-action-bar {
  display: flex;
  gap: var(--m-spacing-md);
  flex-wrap: wrap;
}

.m-action-bar .n-button {
  flex: 1;
  min-width: 120px;
}

/* 操作列表样式 */
.action-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}

.action-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.action-item:active {
  background: var(--bg-surface-hover);
}

.action-item.danger {
  color: var(--color-error);
}

.action-item.danger .action-icon {
  color: var(--color-error);
}

.action-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  color: var(--text-secondary);
}

.action-item.danger .action-icon {
  background: var(--color-error-bg);
}

.action-label {
  font-size: var(--m-text-md);
  font-weight: 500;
}
</style>
