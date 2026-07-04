<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import {
  NCard, NSpace, NButton, NIcon, NTabs, NTabPane,
  NTag, NPopconfirm, NGrid, NGi, NEmpty, NTooltip
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  RefreshOutlined as RefreshIcon,
  DeleteOutlined as DeleteIcon,
  ContentCopyOutlined as CopyIcon,
  CloudSyncOutlined as SyncIcon
} from '@vicons/material'

import FeedEditModal from '../../components/FeedEditModal.vue'
import RssRuleModal from '../../components/RssRuleModal.vue'
import AggregatedFeedItemsModalDesktop from '../../components/desktop/AggregatedFeedItemsModalDesktop.vue'
import AggregatedRuleHistoryModalDesktop from '../../components/desktop/AggregatedRuleHistoryModalDesktop.vue'
import RulePreviewModal from '../../components/RulePreviewModal.vue'
import SubscriptionManager from '../../components/SubscriptionManager.vue'
import { useSubscriptionView } from '../../composables/views/useSubscriptionView'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  feeds,
  rules,
  clients,
  loading,
  syncing,
  showFeedModal,
  showRuleModal,
  showPreviewModal,
  currentItem,
  previewRuleData,
  isNew,
  fetchData,
  openAddFeed,
  openEditFeed,
  saveFeed,
  deleteFeed,
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

// 聚合订阅源详情弹窗（本地状态，无需侵入 composable）
const showAggregatedModal = ref(false)
// 聚合下载记录弹窗
const showRuleHistoryModal = ref(false)

// 通过 client id 查询下载器名称
const clientNameMap = computed(() => {
  const map: Record<string, string> = {}
  clients.value.forEach(c => { map[c.id] = c.name })
  return map
})
const getClientName = (id: string) => (id ? (clientNameMap.value[id] || '—') : '—')

onMounted(fetchData)
</script>

<template>
  <div class="sub-view">
    <div class="page-header">
      <div>
        <h1>订阅与下载</h1>
        <div class="subtitle">RSS 自动化追番与资源监控</div>
      </div>
      
      <n-space>
        <n-popconfirm @positive-click="clearBlacklist" positive-text="确定清空" negative-text="取消">
          <template #trigger>
            <n-button v-bind="getButtonStyle('warning')">
              清空黑名单
            </n-button>
          </template>
          确定清空下载黑名单吗？这会让之前因为下载超时而被屏蔽的资源恢复可下载状态。
        </n-popconfirm>
        <n-popconfirm @positive-click="clearCache" positive-text="确定重置" negative-text="取消">
          <template #trigger>
            <n-button v-bind="getButtonStyle('warning')">
              清空识别缓存
            </n-button>
          </template>
          确定清空所有已识别的元数据吗？这会导致所有条目在下次刷新时重新执行 AI/TMDB 识别。
        </n-popconfirm>
        <n-button v-bind="getButtonStyle('warning')" @click="retryRecognition">
          重试识别失败项
        </n-button>
        <n-button v-bind="getButtonStyle('primary')" :loading="syncing" @click="runNow">
          立即触发全量刷新
        </n-button>
      </n-space>
    </div>

    <n-tabs type="segment" animated class="custom-tabs">
      <!-- 追剧订阅管理 -->
      <n-tab-pane name="subscriptions" tab="追剧订阅">
        <SubscriptionManager :clients="clients" />
      </n-tab-pane>

      <!-- 订阅源管理 -->
      <n-tab-pane name="feeds" tab="订阅源">
        <div class="section-header">
          <n-space :size="8">
            <n-button v-bind="getButtonStyle('primary')" size="small" @click="showAggregatedModal = true">
              订阅源详情
            </n-button>
            <n-button v-bind="getButtonStyle('secondary')" size="small" @click="syncJackettFeeds">
              同步 Jackett 源
            </n-button>
            <n-button v-bind="getButtonStyle('primary')" size="small" @click="openAddFeed">
              新增订阅源
            </n-button>
          </n-space>
        </div>

        <n-grid :x-gap="12" :y-gap="12" :cols="3" v-if="feeds.length > 0">
          <n-gi v-for="feed in feeds" :key="feed.id">
            <n-card hoverable class="feed-card clickable-card" @click="openEditFeed(feed)">
              <div class="f-head">
                <div class="f-title">{{ feed.title || '未命名订阅' }}</div>
                <div class="f-status">
                  <n-tag size="small" round :bordered="false" :style="feed.enabled ? { color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' } : { color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' }">
                    {{ feed.enabled ? '监控中' : '已暂停' }}
                  </n-tag>
                </div>
              </div>
              <div class="f-url code-inline">{{ feed.url }}</div>

              <div class="f-act" @click.stop>
                <n-space :size="4">
                  <n-popconfirm @positive-click="deleteFeed(feed.id)" positive-text="删除" negative-text="取消">
                    <template #trigger>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                            <template #icon><n-icon><DeleteIcon/></n-icon></template>
                          </n-button>
                        </template>
                        移除订阅源
                      </n-tooltip>
                    </template>
                    确定彻底移除此订阅源吗？
                  </n-popconfirm>
                </n-space>
              </div>
            </n-card>
          </n-gi>
        </n-grid>
        <div v-else class="empty-tip">
          <n-empty description="暂无订阅源，快去添加一个吧" />
        </div>
      </n-tab-pane>

      <!-- 自动下载规则 -->
      <n-tab-pane name="rules" tab="下载规则">
        <div class="section-header">
          <n-space :size="8">
            <n-button v-bind="getButtonStyle('primary')" size="small" @click="showRuleHistoryModal = true">
              下载记录
            </n-button>
            <n-button v-bind="getButtonStyle('primary')" size="small" @click="openAddRule">
              创建新规则
            </n-button>
          </n-space>
        </div>

        <n-grid :x-gap="12" :y-gap="12" :cols="3" v-if="rules.length > 0">
          <n-gi v-for="rule in rules" :key="rule.id">
            <n-card hoverable class="rule-card clickable-card" @click="openEditRule(rule)">
              <div class="f-head">
                <div class="f-title">{{ rule.name || '未命名规则' }}</div>
                <div class="f-status">
                  <n-tag size="small" round :bordered="false" :style="rule.enabled ? { color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' } : { color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' }">
                    {{ rule.enabled ? '生效中' : '未启用' }}
                  </n-tag>
                </div>
              </div>
              <div class="r-info-row">
                <span class="r-label">包含关键词：</span>
                <span class="r-value r-ellipsis" :title="rule.must_contain">{{ rule.must_contain || '无' }}</span>
              </div>
              <div class="r-info-row">
                <span class="r-label">排除关键词：</span>
                <span class="r-value r-ellipsis" :title="rule.must_not_contain">{{ rule.must_not_contain || '无' }}</span>
              </div>
              <div class="r-info-row">
                <span class="r-label">匹配模式：</span>
                <span class="r-value">{{ rule.use_regex ? '正则' : '普通' }}</span>
              </div>
              <div class="r-info-row">
                <span class="r-label">下载器：</span>
                <span class="r-value">{{ getClientName(rule.target_client_id) }}</span>
              </div>
              <div class="r-info-row">
                <span class="r-label">保存路径：</span>
                <span class="r-value r-ellipsis code-inline" :title="rule.save_path">{{ rule.save_path || '默认' }}</span>
              </div>

              <div class="f-act" @click.stop>
                <n-space :size="4">
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('icon')" size="small" @click="duplicateRule(rule)">
                        <template #icon><n-icon><CopyIcon/></n-icon></template>
                      </n-button>
                    </template>
                    复制规则
                  </n-tooltip>
                  <n-popconfirm @positive-click="deleteRule(rule.id)" positive-text="删除" negative-text="取消">
                    <template #trigger>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                            <template #icon><n-icon><DeleteIcon/></n-icon></template>
                          </n-button>
                        </template>
                        删除规则
                      </n-tooltip>
                    </template>
                    确定要删除此规则吗？
                  </n-popconfirm>
                </n-space>
              </div>
            </n-card>
          </n-gi>
        </n-grid>
        <div v-else class="empty-tip">
          <n-empty description="暂无下载规则，快去创建一个吧" />
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

    <AggregatedFeedItemsModalDesktop
      v-model:show="showAggregatedModal"
      :feeds="feeds"
      :clients="clients"
    />

    <AggregatedRuleHistoryModalDesktop
      v-model:show="showRuleHistoryModal"
      :rules="rules"
      :clients="clients"
    />

    <RulePreviewModal
      v-model:show="showPreviewModal"
      :rule-data="previewRuleData"
      :clients="clients"
    />

  </div>
</template>

<style scoped>
.sub-view { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }

.section-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 16px;
}

.custom-tabs :deep(.n-tab-pane) {
  padding-top: 16px !important;
}

.feed-card,
.rule-card {
  border: 1px solid var(--app-border-light) !important;
  background: var(--app-surface-card-mixed) !important;
  border-radius: var(--card-border-radius, 12px) !important;
  transition: all var(--transition-normal);
  position: relative;
}
.clickable-card { cursor: pointer; }
.feed-card:hover,
.rule-card:hover {
  border-color: var(--n-primary-color) !important;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.f-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.f-title { font-weight: bold; font-size: 15px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; flex: 1; margin-right: 8px; }
.f-status { flex-shrink: 0; }
.f-url { font-size: 11px; color: var(--text-tertiary); word-break: break-all; margin-bottom: 16px; height: 32px; overflow: hidden; opacity: 0.8; }
.f-act { display: flex; justify-content: flex-end; }

.r-keywords { font-size: 12px; color: var(--text-tertiary); margin-bottom: 10px; min-height: 32px; word-break: break-all; opacity: 0.9; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.r-label { color: var(--text-muted); font-size: 12px; flex-shrink: 0; }
.r-value { color: var(--text-secondary); font-size: 12px; word-break: break-all; }
.r-info-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; min-height: 22px; }
.r-ellipsis { flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; min-width: 0; }
.r-exclude { font-size: 11px; color: var(--text-tertiary); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; flex: 1; opacity: 0.8; }

.empty-tip { padding: 40px; text-align: center; color: var(--text-muted); }

/* Tabs 样式已移至 global.css 统一管理 */
</style>
