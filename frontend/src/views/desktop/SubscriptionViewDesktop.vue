<script setup lang="ts">
import { onMounted, h } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NTabs, NTabPane, NDataTable, 
  NTag, NPopconfirm, NGrid, NGi, NEmpty, NTooltip
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  RefreshOutlined as RefreshIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  RssFeedOutlined as FeedIcon,
  DownloadOutlined as AutoIcon,
  ListAltOutlined as ListIcon,
  HistoryOutlined as ResetIcon,
  ContentCopyOutlined as CopyIcon,
  CloudSyncOutlined as SyncIcon
} from '@vicons/material'

import FeedEditModal from '../../components/FeedEditModal.vue'
import RssRuleModal from '../../components/RssRuleModal.vue'
import FeedItemsModal from '../../components/FeedItemsModal.vue'
import RulePreviewModal from '../../components/RulePreviewModal.vue'
import RuleHistoryModal from '../../components/RuleHistoryModal.vue'
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

    <n-tabs type="card" animated>
      <!-- 追剧订阅管理 -->
      <n-tab-pane name="subscriptions" tab="追剧订阅">
        <SubscriptionManager :clients="clients" />
      </n-tab-pane>

      <!-- 订阅源管理 -->
      <n-tab-pane name="feeds" tab="订阅源">
        <n-card bordered style="background: var(--app-surface-card)">
          <template #header>
            <div class="card-title-box">
              <n-icon size="20" style="color: var(--n-primary-color)"><FeedIcon /></n-icon>
              <span class="card-title-text">已添加的 RSS 订阅</span>
            </div>
          </template>
          <template #header-extra>
            <n-space :size="8">
              <n-button v-bind="getButtonStyle('secondary')" size="small" @click="syncJackettFeeds">
                同步 Jackett 源
              </n-button>
              <n-button v-bind="getButtonStyle('primary')" size="small" @click="openAddFeed">
                新增订阅源
              </n-button>
            </n-space>
          </template>
          
          <n-grid :x-gap="12" :y-gap="12" :cols="3" v-if="feeds.length > 0">
            <n-gi v-for="feed in feeds" :key="feed.id">
              <n-card hoverable class="feed-card clickable-card" @click="openEditFeed(feed)">
                <div class="f-head">
                  <div class="f-title">{{ feed.title || '未命名订阅' }}</div>
                  <div class="f-status">
                    <n-tag size="small" :type="feed.enabled ? 'success' : 'error'" round>
                      {{ feed.enabled ? '监控中' : '已暂停' }}
                    </n-tag>
                  </div>
                </div>
                <div class="f-url code-inline">{{ feed.url }}</div>
                
                <div class="f-act" @click.stop>
                  <n-space :size="4">
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button v-bind="getButtonStyle('icon')" size="small" @click="openViewItems(feed)">
                          <template #icon><n-icon><ListIcon/></n-icon></template>
                        </n-button>
                      </template>
                      查看抓取内容
                    </n-tooltip>

                    <n-popconfirm @positive-click="resetFeedHistory(feed.id)" positive-text="重置" negative-text="取消">
                      <template #trigger>
                        <n-tooltip trigger="hover">
                          <template #trigger>
                            <n-button v-bind="getButtonStyle('icon')" size="small">
                              <template #icon><n-icon><ResetIcon/></n-icon></template>
                            </n-button>
                          </template>
                          清除下载历史
                        </n-tooltip>
                      </template>
                      确认清除该源的下载历史吗？
                    </n-popconfirm>

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
        </n-card>
      </n-tab-pane>

      <!-- 自动下载规则 -->
      <n-tab-pane name="rules" tab="下载规则">
        <n-card bordered style="background: var(--app-surface-card)">
          <template #header>
            <div class="card-title-box">
              <n-icon size="20" style="color: var(--n-warning-color)"><AutoIcon /></n-icon>
              <span class="card-title-text">自动匹配与推送逻辑</span>
            </div>
          </template>
          <template #header-extra>
            <n-button v-bind="getButtonStyle('primary')" size="small" @click="openAddRule">
              创建新规则
            </n-button>
          </template>

          <n-data-table 
            :columns="[
              { title: '规则名称', key: 'name', width: 180 },
              { title: '包含关键词', key: 'must_contain', ellipsis: { tooltip: true } },
              { title: '模式', key: 'use_regex', width: 80, render(r: any){ 
                  return h(NTag, { size: 'small', quaternary: true, type: r.use_regex ? 'warning' : 'info' }, { default: () => r.use_regex ? '正则' : '普通' })
              }},
              { title: '状态', key: 'enabled', width: 80, render(r: any){ 
                  return h(NTag, { size: 'small', round: true, type: r.enabled ? 'success' : 'error' }, { default: () => r.enabled ? '生效中' : '未启用' })
              }},
              { title: '操作', key: 'actions', width: 180, render(r: any){ 
                  return h(NSpace, { size: 'small' }, { default: () => [
                    // 复制
                    h(NTooltip, { trigger: 'hover' }, {
                      trigger: () => h(NButton, { ...getButtonStyle('icon'), onClick: ()=>duplicateRule(r) }, { 
                        icon: () => h(NIcon, null, { default: () => h(CopyIcon) }) 
                      }),
                      default: () => '复制规则'
                    }),
                    // 编辑
                    h(NTooltip, { trigger: 'hover' }, {
                      trigger: () => h(NButton, { ...getButtonStyle('icon'), onClick: ()=>openEditRule(r) }, { 
                        icon: () => h(NIcon, null, { default: () => h(EditIcon) }) 
                      }),
                      default: () => '编辑规则'
                    }),
                    // 记录
                    h(NTooltip, { trigger: 'hover' }, {
                      trigger: () => h(NButton, { ...getButtonStyle('iconPrimary'), onClick: ()=>openViewHistory(r) }, { 
                        icon: () => h(NIcon, null, { default: () => h(ResetIcon) })
                      }),
                      default: () => '执行记录'
                    }),
                    // 删除
                    h(NPopconfirm, { 
                      onPositiveClick: ()=>deleteRule(r.id),
                      positiveText: '确定删除',
                      negativeText: '取消'
                    }, {
                       trigger: () => h(NTooltip, { trigger: 'hover' }, {
                         trigger: () => h(NButton, { ...getButtonStyle('iconDanger'), size: 'small' }, { 
                           icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) 
                         }),
                         default: () => '删除规则'
                       }),
                       default: () => '确定要删除此规则吗？'
                    })
                  ]})
              }}
            ]" 
            :data="rules" 
          />
        </n-card>
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
.sub-view { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }

.card-title-box {
  display: flex;
  align-items: center;
  gap: 0;
}
.card-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
}

.feed-card {
  border: 1px solid var(--app-border-light) !important;
  background: var(--app-surface-card) !important;
  border-radius: var(--card-border-radius, 12px) !important;
  transition: all var(--transition-normal);
  position: relative;
}
.clickable-card { cursor: pointer; }
.feed-card:hover {
  border-color: var(--primary-half) !important;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.f-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.f-title { font-weight: bold; font-size: 15px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; flex: 1; margin-right: 8px; }
.f-status { flex-shrink: 0; }
.f-url { font-size: 11px; color: var(--n-text-color-3); word-break: break-all; margin-bottom: 16px; height: 32px; overflow: hidden; opacity: 0.8; }
.f-act { display: flex; justify-content: flex-end; }

.empty-tip { padding: 40px; text-align: center; color: var(--text-muted); }
</style>
