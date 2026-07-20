<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted, h } from 'vue'
import { 
  NButton, NIcon, NTag, NInput, NPopconfirm, NEmpty, NSpace, NTabs, NTabPane, NAlert, NText, NCheckbox, NSpin, NDivider, NCard, NTooltip
} from 'naive-ui'
import { useBackDialog } from '../../composables/useBackDialog'
import {
  ClockIcon as HistoryIcon,
  TrashIcon as DeleteIcon,
  MagnifyingGlassIcon as SearchIcon,
  FolderIcon,
  ArrowRightIcon as ArrowIcon,
  ClockIcon as TimeIcon,
  ServerIcon as SizeIcon,
  CheckBadgeIcon as SuccessIcon,
  ExclamationCircleIcon as ErrorIcon,
  ChevronDoubleDownIcon as MoreIcon,
  ArrowPathIcon as RetryIcon,
  DocumentTextIcon as LogIcon
} from '@heroicons/vue/24/outline'
import AppSearchField from '../../components/AppSearchField.vue'
import AppGlassModal from '../../components/AppGlassModal.vue'
import { useOrganizeHistory } from '../../composables/views/useOrganizeHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  loading,
  history,
  searchQuery,
  statusFilter,
  hasMore,
  fetchData,
  loadMore,
  deleteItem,
  retryItem,
  isRetrying,
  clearAll,
  getActionLabel,
  formatTime,
  showLogModal,
  logDetail,
  logLoading,
  logDetailGroupedLogs,
  viewTaskLog
} = useOrganizeHistory()

const dialog = useBackDialog()

const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const setupObserver = (el: HTMLElement) => {
  if (observer) observer.disconnect()
  
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      loadMore()
    }
  }, { 
    threshold: 0,
    rootMargin: '200px'
  })
  observer.observe(el)
}

watch(scrollTarget, (el) => {
  if (el) {
    setupObserver(el)
  }
})

watch(loading, async (isLoading) => {
  if (!isLoading && hasMore.value && scrollTarget.value) {
    await nextTick()
    const rect = scrollTarget.value.getBoundingClientRect()
    if (rect.top < window.innerHeight + 200) {
      loadMore()
    }
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

// 搜索和筛选变化时，重新加载数据
watch(searchQuery, () => {
  fetchData(true)
})

watch(statusFilter, () => {
  fetchData(true)
})

// 实时日志自动滚动到底部
watch(logDetailGroupedLogs, async () => {
  if (showLogModal.value) {
    await nextTick()
    const scrollArea = document.querySelector('.log-scroll-area')
    if (scrollArea) {
      scrollArea.scrollTop = scrollArea.scrollHeight
    }
  }
})

const handleRetry = (item: any) => {
  dialog.warning({
    title: '确认重试',
    content: '将根据源路径重新执行识别与整理流程（绕过历史去重）。进度可在「任务历史」中查看。',
    positiveText: '确定重试',
    negativeText: '取消',
    onPositiveClick: () => retryItem(item.id)
  })
}

const handleDelete = (item: any) => {
  const deleteFile = ref(false)
  dialog.warning({
    title: '确认删除',
    content: () => h('div', { style: 'max-width: 400px' }, [
      h('p', { class: 'm-0 mb-2' }, '确定要删除这条整理记录吗？'),
      h(NCheckbox, {
        checked: deleteFile.value,
        'onUpdate:checked': (val: boolean) => { deleteFile.value = val }
      }, { default: () => h('span', { style: 'color: var(--n-error-color)' }, '同时物理删除源文件') }),
      deleteFile.value ? h('div', { style: 'font-size: 11px; color: var(--text-tertiary); margin-top: 4px; line-height: 1.2;' }, '警告：这将尝试永久删除原始源路径下的文件。') : null
    ]),
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => {
      deleteItem(item.id, deleteFile.value)
    }
  })
}

/** 日志弹框状态标签（与任务中心样式一致） */
const getStatusTag = (status: string) => {
  const map: Record<string, { color: string; bg: string; label: string }> = {
    completed: { color: '#fff', bg: '#2e7d32', label: '完成' },
    running: { color: '#fff', bg: '#0288d1', label: '运行中' },
    error: { color: '#fff', bg: '#c62828', label: '错误' },
    stopped: { color: '#fff', bg: '#f57c00', label: '已停止' },
    skipped: { color: '#fff', bg: '#f57c00', label: '跳过' }
  }
  return map[status] || { color: '#fff', bg: '#616161', label: status }
}
</script>

<template>
  <div class="history-view">
    <div class="page-header mb-6">
      <div class="d-flex align-center gap-3">
        <div>
          <h1 class="m-0">整理历史</h1>
          <div class="subtitle">记录所有成功的媒体识别与入库流水</div>
        </div>
      </div>
      <n-space>
        <n-tabs type="line" animated v-model:value="statusFilter" class="custom-tabs">
          <n-tab-pane name="all" tab="全部" />
          <n-tab-pane name="success" tab="成功" />
          <n-tab-pane name="skipped" tab="跳过" />
          <n-tab-pane name="failed" tab="失败" />
        </n-tabs>
        <AppSearchField v-model:value="searchQuery" placeholder="搜索标题或文件名..." :loading="loading" style="width: 250px" />
        <n-popconfirm @positive-click="clearAll" positive-text="确定清空" negative-text="我再想想">
          <template #trigger>
            <n-button v-bind="getButtonStyle('danger')">
              清空历史
            </n-button>
          </template>
          确定要彻底删除所有整理记录吗？这不会影响磁盘上的文件。
</n-popconfirm>
</n-space>
</div>

    <div v-if="history.length > 0" class="history-list">
        <n-card v-for="item in history" :key="item.id" class="history-item" data-app-instance="organize-history-card" hoverable :bordered="false">
          <!-- 现有项内容保持不变 -->
          <!-- 1. Header: Title & Meta -->
          <div class="item-row header-row">
            <div class="title-group">
              <span class="item-title">{{ item.title || item.filename }}</span>
              <span class="item-year" v-if="item.year">({{ item.year }})</span>
              <span class="history-tag tag-episode" v-if="item.season || item.episode">
                S{{ item.season?.toString().padStart(2, '0') }}E{{ item.episode }}
              </span>
              <span v-if="item.media_type" class="history-tag tag-type">{{ item.media_type }}</span>
              <span v-if="item.resolution" class="history-tag tag-res">{{ item.resolution }}</span>
              <span v-if="item.video_encode" class="history-tag tag-encode">{{ item.video_encode }}</span>
              <span v-if="item.team" class="history-tag tag-team">{{ item.team }}</span>
            </div>
            <div class="item-status">
              <span class="history-tag" :class="'tag-status-' + item.status">
                {{ item.status === 'failed' ? '失败' : (item.status === 'skipped' ? '跳过' : '成功') }}
              </span>
            </div>
          </div>

          <!-- Skipped Message Row -->
          <div v-if="item.status === 'skipped' && item.message" class="skipped-msg-row mt-2">
            <n-alert :show-icon="false" size="small" class="compact-alert" :bordered="false">
              {{ item.message }}
            </n-alert>
          </div>

          <!-- 2. Paths (Vertical Stacked) -->
          <div class="path-container mt-3">
            <div class="path-item source">
              <div class="path-label">源路径</div>
              <div class="path-content">
                <n-icon><FolderIcon /></n-icon>
                <span class="path-text">{{ item.source_path }}</span>
              </div>
            </div>
            <div class="path-divider">
              <div class="line"></div>
              <n-icon size="14"><ArrowIcon /></n-icon>
              <div class="line"></div>
            </div>
            <div class="path-item target">
              <div class="path-label">目标路径</div>
              <div class="path-content">
                <n-icon style="color: var(--n-primary-color)"><FolderIcon /></n-icon>
                <span class="path-text">{{ item.target_path }}</span>
              </div>
            </div>
          </div>

          <!-- 3. Footer: Details -->
          <div class="item-row footer-row mt-3">
            <div class="detail-group">
              <div class="detail-item">
                <span class="label">转移方式：</span>
                <span class="history-tag tag-action">{{ getActionLabel(item.action_type) }}</span>
              </div>
              <div class="detail-item" v-if="item.status === 'failed' && item.message">
                <span class="label">失败原因：</span>
                <span class="history-tag tag-error" :title="item.message">{{ item.message }}</span>
              </div>
              <div class="detail-item">
                <span class="history-tag tag-size">{{ item.file_size || '未知大小' }}</span>
              </div>
              <div class="detail-item">
                <span class="history-tag tag-time">{{ formatTime(item.processed_at) }}</span>
              </div>
              <div class="detail-item" v-if="item.tmdb_id">
                <a 
                  :href="`https://www.themoviedb.org/${item.media_type === '电影' ? 'movie' : 'tv'}/${item.tmdb_id}`" 
                  target="_blank"
                  class="history-tag tag-tmdb tag-link"
                >TMDB: {{ item.tmdb_id }}</a>
              </div>
            </div>
            <div class="delete-btn-wrapper">
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-button
                    v-bind="getButtonStyle('icon')"
                    size="small"
                    :disabled="!item.task_id"
                    style="margin-right: 6px"
                    @click="viewTaskLog(item.task_id)"
                  >
                    <template #icon><n-icon><LogIcon /></n-icon></template>
                  </n-button>
                </template>
                {{ item.task_id ? '查看识别日志' : '该记录未关联识别日志（旧数据）' }}
              </n-tooltip>
              <n-button
                v-bind="getButtonStyle('iconPrimary')"
                size="small"
                :loading="isRetrying(item.id)"
                :disabled="isRetrying(item.id)"
                style="margin-right: 6px"
                @click="handleRetry(item)"
              >
                <template #icon><n-icon><RetryIcon /></n-icon></template>
              </n-button>
              <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDelete(item)">
                <template #icon><n-icon><DeleteIcon /></n-icon></template>
              </n-button>
            </div>
          </div>
        </n-card>

      <!-- Sentinel for Infinite Scroll -->
      <div ref="scrollTarget" class="load-more-sentinel">
        <n-spin v-if="loading" size="small" description="正在加载更多..." />
        <div v-else-if="!hasMore" class="end-of-list">
          <n-divider dashed>
            <span style="font-size: 12px; color: var(--text-tertiary)">到底了，共 {{ history.length }} 条记录</span>
          </n-divider>
        </div>
        <div v-else class="can-load-more">
           <n-icon size="16"><MoreIcon /></n-icon>
           向下滚动加载更多
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <n-empty description="暂无整理历史" />
    </div>

    <!-- 识别日志查看弹框（复用任务中心「识别」日志样式） -->
    <AppGlassModal appearance-key="task-history-modal" v-model:show="showLogModal" style="width: 960px;" title="识别日志">
      <template #header-extra>
        <n-tag v-if="logDetail" size="small" round :bordered="false" :style="{ color: getStatusTag(logDetail.status).color, backgroundColor: getStatusTag(logDetail.status).bg, borderColor: 'transparent' }">
          {{ getStatusTag(logDetail.status).label }}
        </n-tag>
      </template>
      <n-spin :show="logLoading">
        <div v-if="logDetail" class="log-scroll-area">
          <div class="log-container">
            <div v-for="group in logDetailGroupedLogs" :key="group.groupTime" class="log-group">
              <div class="log-group-time">{{ group.displayTime }}</div>
              <div class="log-group-line"></div>
              <div class="log-group-items">
                <div v-for="(log, i) in group.logs" :key="i" class="log-line">
                  <span class="log-time">{{ log.time }}</span>
                  <span :class="['log-level', log.level.toLowerCase()]">{{ log.level }}</span>
                  <span class="log-msg">{{ log.message }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <n-empty v-else-if="!logLoading" description="暂无日志" style="padding: 60px 0" />
      </n-spin>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.history-view { width: 100%; padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h1 { margin: 0; font-size: 26px; font-weight: bold; color: var(--text-primary); }
.subtitle { font-size: 12px; color: var(--n-primary-color); letter-spacing: 1px; }
.page-header :deep(.n-space) { align-items: center; }
/* 输入框/按钮高度、Tabs 高度/间距/内边距 由 global.css CSS 变量统一管理 */

.history-list { margin-bottom: 40px; }
.history-list .history-item {
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 12px);
  margin-bottom: 16px;
  transition: all var(--transition-normal);
  background: var(--app-surface-card-mixed);
}
.history-list .history-item :deep(.n-card__content) {
  padding: 16px 20px !important;
}
.history-list .history-item:hover {
  border-color: var(--n-primary-color);
}

/* 原history-item样式已迁移到n-list-item */

.item-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }

/* Header Row */
.title-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; min-width: 0; }
.item-status { flex-shrink: 0; }
.item-title { font-size: 17px; font-weight: bold; color: var(--text-primary); }
.item-year { font-size: 13px; color: var(--text-tertiary); }
/* History Tags - New Component */
.history-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  border-radius: 11px;
  font-family: var(--code-font);
  border: 1px solid;
}

/* Episode Tag (S01E12) - 电光蓝底色+白色文字 */
.history-tag.tag-episode {
  background: #3B82F6;
  color: #fff;
  border-color: #3B82F6;
}

/* Media Type Tag (剧集/电影) - 蓝色底色+白色文字 */
.history-tag.tag-type {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}

/* Resolution Tag (1080P) - 深橙色底色+白色文字 */
.history-tag.tag-res {
  background: #e65100;
  color: #fff;
  border-color: #e65100;
}

/* Encode Tag (H.265) - 深橙色底色+白色文字 */
.history-tag.tag-encode {
  background: #e65100;
  color: #fff;
  border-color: #e65100;
}

/* Team Tag (LoliHouse) - 深蓝色底色+白色文字 */
.history-tag.tag-team {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}

/* TMDB Tag - 深绿色底色+白色文字 */
.history-tag.tag-tmdb,
.detail-item .history-tag.tag-tmdb {
  background: #2e7d32;
  color: #fff;
  border-color: #2e7d32;
}

.history-tag.tag-link {
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s ease;
}
.history-tag.tag-link:hover {
  opacity: 0.85;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* Action Tag (硬链/来源) - 红色底色+白色文字 */
.history-tag.tag-action,
.detail-item .history-tag.tag-action {
  background: #c62828;
  color: #fff;
  border-color: #c62828;
}

/* Error Reason Tag - 红色底色+白色文字 */
.history-tag.tag-error,
.detail-item .history-tag.tag-error {
  background: #c62828;
  color: #fff;
  border-color: #c62828;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Size Tag - 紫色底色+白色文字 */
.history-tag.tag-size,
.detail-item .history-tag.tag-size {
  background: #7b1fa2;
  color: #fff;
  border-color: #7b1fa2;
}

/* Time Tag - 青色底色+白色文字 */
.history-tag.tag-time,
.detail-item .history-tag.tag-time {
  background: #00838f;
  color: #fff;
  border-color: #00838f;
}

/* Status Tags - 底色+白色文字 */
.history-tag.tag-status-success {
  background: #2e7d32;
  color: #fff;
  border-color: #2e7d32;
}
.history-tag.tag-status-failed {
  background: #c62828;
  color: #fff;
  border-color: #c62828;
}
.history-tag.tag-status-skipped {
  background: #f57c00;
  color: #fff;
  border-color: #f57c00;
}



/* Path Container (Vertical) */
.path-container {
  display: flex;
  flex-direction: column;
  background: transparent;
  border-radius: var(--code-radius, 8px);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
}

.path-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  gap: 12px;
}

.path-item.source {
  background: transparent;
  border: none;
}

.path-item.target {
  background: transparent;
  border: none;
}

.path-label {
  font-size: 9px;
  font-weight: 900;
  padding: 2px 4px;
  border-radius: var(--button-border-radius, 3px);
  min-width: 45px;
  text-align: center;
  flex-shrink: 0;
}

.source .path-label {
  background: var(--app-surface-card-mixed);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}
.target .path-label {
  background: var(--app-surface-card-mixed);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}

.path-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.path-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source .path-text { color: var(--text-secondary); }
.target .path-text { color: var(--text-primary); }

.path-divider {
  height: 1px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  opacity: var(--opacity-disabled);
  color: var(--app-border-light);
  background: var(--app-border-light);
}
.path-divider .line { display: none; }
.path-divider .n-icon { margin: 0 auto; }

/* Footer Row */
.footer-row { 
  color: var(--text-tertiary); 
  font-size: 13px; 
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.detail-group { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; flex: 1; min-width: 0; }
.detail-item { display: flex; align-items: center; gap: 6px; }
.detail-item .label { color: var(--text-tertiary); }
.delete-btn-wrapper { flex-shrink: 0; display: flex; align-items: center; }

/* === 识别日志弹框样式（与任务中心日志样式保持一致） === */
.log-container {
  font-family: var(--code-font, 'JetBrains Mono', monospace);
  font-size: 13px;
  background: var(--app-surface-card-mixed);
  border-radius: 8px;
  padding: 12px;
}
.log-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--app-border-light);
}
.log-group:last-child { border-bottom: none; }
.log-group-time {
  color: var(--n-primary-color);
  font-size: 12px;
  min-width: 130px;
  flex-shrink: 0;
  padding-top: 2px;
  font-weight: 700;
}
.log-group-line {
  width: 2px;
  background-color: var(--n-primary-color);
  border-radius: 1px;
  flex-shrink: 0;
  align-self: stretch;
  margin: 4px 0;
  opacity: 0.6;
}
.log-group-items {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}
.log-time { color: var(--text-tertiary); min-width: 75px; font-variant-numeric: tabular-nums; }
.log-level {
  min-width: 40px;
  font-weight: bold;
  text-transform: uppercase;
}
.log-level.info { color: #52c41a; }
.log-level.error { color: #ff4d4f; }
.log-level.warning { color: #faad14; }
.log-level.warn { color: #faad14; }
.log-level.debug { color: #1890ff; }
.log-msg { flex: 1; word-break: break-all; }

/* === 移动端适配: 日志弹框 === */
@media (max-width: 767px) {
  .log-container { padding: 8px; font-size: 11px; }
  .log-group { gap: 8px; padding: 4px 0; }
  .log-group-time { min-width: 60px; font-size: 10px; }
  .log-group-line { margin: 2px 0; }
  .log-line { flex-wrap: wrap; gap: 4px; padding: 1px 0; }
  .log-time { font-size: 10px; min-width: 0 !important; }
  .log-level { font-size: 10px; min-width: 0 !important; }
  .log-msg { font-size: 11px; flex: none !important; width: 100%; }
}

/* Compact Alert - 改成标签样式 */
.compact-alert { display: inline-block; width: auto; max-width: 100%; }
.compact-alert :deep(.n-alert-body) { padding: 6px 12px; }

/* 错误消息标签样式 - 红色底色+白色文字 */
.error-msg-row .compact-alert :deep(.n-alert-body) {
  background: #c62828 !important;
  border-radius: 11px;
  font-family: var(--code-font);
  font-size: 12px;
  font-weight: 500;
}
.error-msg-row .compact-alert :deep(.n-alert-body__content) {
  color: #fff !important;
}

/* 跳过消息标签样式 - 橙色底色+白色文字 */
.skipped-msg-row .compact-alert :deep(.n-alert-body) {
  background: #f57c00 !important;
  border-radius: 11px;
  font-family: var(--code-font);
  font-size: 12px;
  font-weight: 500;
}
.skipped-msg-row .compact-alert :deep(.n-alert-body__content) {
  color: #fff !important;
}

.ml-2 { margin-left: 8px; }
.mt-3 { margin-top: 12px; }
.mb-6 { margin-bottom: 24px; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-3 { gap: 12px; }
.m-0 { margin: 0; }

.empty-state { padding: 100px 0; }

.load-more-sentinel {
  padding: 24px 0 48px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.end-of-list {
  width: 100%;
  opacity: var(--opacity-secondary);
}

.can-load-more {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
  opacity: var(--opacity-primary);
}
</style>
