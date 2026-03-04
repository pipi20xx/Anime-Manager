<script setup lang="ts">
import { onMounted } from 'vue'
import { 
  NButton, NIcon, NTabs, NTabPane, NDropdown, NSpace
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  MoreVertOutlined as MoreIcon
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
  clearBlacklist
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
  <div class="sub-view-mobile">
    <div class="page-header-mobile">
      <div>
        <h1>订阅与下载</h1>
      </div>
      
      <n-dropdown trigger="click" :options="mobileGlobalActions" @select="handleMobileGlobalAction">
        <n-button circle secondary>
          <template #icon><n-icon><MoreIcon/></n-icon></template>
        </n-button>
      </n-dropdown>
    </div>

    <n-tabs type="line" animated class="mobile-tabs" pane-class="mobile-tab-pane">
      <!-- 追剧订阅管理 -->
      <n-tab-pane name="subscriptions" tab="追剧订阅">
        <MobileSubscriptionManager :clients="clients" />
      </n-tab-pane>

      <!-- 订阅源管理 -->
      <n-tab-pane name="feeds" tab="订阅源">
        <div class="tab-content">
          <n-button block dashed type="primary" @click="openAddFeed" style="margin-bottom: 12px">
            <template #icon><n-icon><AddIcon/></n-icon></template>
            新增订阅源
          </n-button>
          <MobileFeedList 
            :feeds="feeds" 
            @edit="openEditFeed"
            @delete="deleteFeed"
            @reset="resetFeedHistory"
            @viewItems="openViewItems"
          />
        </div>
      </n-tab-pane>

      <!-- 自动下载规则 -->
      <n-tab-pane name="rules" tab="下载规则">
        <div class="tab-content">
          <n-button block dashed type="warning" @click="openAddRule" style="margin-bottom: 12px">
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
.sub-view-mobile {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--app-background);
  padding-bottom: 80px; 
}

.page-header-mobile {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.page-header-mobile h1 { margin: 0; font-size: 20px; font-weight: 800; }

.mobile-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 0 16px;
}

:deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

:deep(.mobile-tab-pane) {
  height: 100%;
  overflow-y: auto;
}

.tab-content {
  padding: 16px;
}
</style>
