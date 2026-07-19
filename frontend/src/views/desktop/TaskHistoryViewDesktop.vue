<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { NCard, NSpace, NTag, NButton, NIcon, NEmpty, NModal, NPopconfirm, NSpin, NDivider, NText, NTabs, NTabPane, useDialog } from 'naive-ui'
import {
  TrashIcon as DeleteIcon,
  EyeIcon as ViewIcon,
  XMarkIcon as ClearIcon,
  ChevronDoubleDownIcon as MoreIcon,
  DocumentTextIcon as LogIcon
} from '@heroicons/vue/24/outline'
import AppGlassModal from '../../components/AppGlassModal.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import { useTaskHistory } from '../../composables/views/useTaskHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  tasks,
  loading,
  selectedTask,
  selectedTaskGroupedLogs,
  showLogModal,
  moduleFilter,
  searchQuery,
  hasMore,
  fetchData,
  loadMore,
  fetchTasks,
  fetchTaskDetail,
  deleteTask,
  cleanupTasks,
  startPolling,
  stopPolling,
  getStatusTag,
  getModuleIcon,
  formatTime,
  formatDuration,
  getTaskStats,
  moduleOptions
} = useTaskHistory()

const dialog = useDialog()

const handleDeleteTask = (taskId: string) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这条任务历史记录吗？',
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => deleteTask(taskId)
  })
}

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

watch(moduleFilter, () => {
  fetchData(true)
})

watch(searchQuery, () => {
  fetchData(true)
})

// 实时日志自动滚动到底部
watch(selectedTaskGroupedLogs, async () => {
  if (showLogModal.value) {
    await nextTick()
    const scrollArea = document.querySelector('.log-scroll-area')
    if (scrollArea) {
      scrollArea.scrollTop = scrollArea.scrollHeight
    }
  }
})

onMounted(startPolling)
onUnmounted(() => {
  stopPolling()
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="task-history-view">
    <div class="page-header">
      <div>
        <h1>任务中心</h1>
        <div class="subtitle">任务执行历史与日志</div>
      </div>
      <n-space>
        <n-tabs type="line" animated v-model:value="moduleFilter" class="custom-tabs">
          <n-tab-pane name="all" tab="全部" />
          <n-tab-pane v-for="mod in moduleOptions.slice(1)" :key="mod" :name="mod" :tab="mod" />
        </n-tabs>
        <AppSearchField v-model:value="searchQuery" placeholder="搜索任务名称..." :loading="loading" style="width: 200px" />
        <n-button v-bind="getButtonStyle('secondary')" @click="fetchTasks">
          刷新
        </n-button>
        <n-popconfirm 
          @positive-click="cleanupTasks"
          positive-text="确定"
          negative-text="取消"
        >
          <template #trigger>
            <n-button v-bind="getButtonStyle('warning')">
              清理旧记录
            </n-button>
          </template>
          确定要清理超过 30 天的任务记录吗？
        </n-popconfirm>
      </n-space>
    </div>

    <n-card v-if="tasks.length === 0" embedded style="margin-top: var(--m-4)">
      <n-empty description="暂无任务记录" />
    </n-card>

    <div v-else class="task-list">
      <n-card v-for="task in tasks" :key="task.task_id" class="task-card" data-app-instance="task-history-card" hoverable :bordered="false">
        <div class="card-header">
          <div class="header-main">
            <n-tag size="small" round :bordered="false" :style="getStatusTag(task.status).style">
              {{ getStatusTag(task.status).label }}
            </n-tag>
            <span class="task-name">{{ task.name || task.module }}</span>
          </div>
          <span class="task-time">{{ formatTime(task.started_at) }}</span>
        </div>
        <div class="card-footer">
          <div class="task-meta">
            <span v-if="task.status === 'completed'" class="meta-item">
              耗时 {{ formatDuration(task.started_at, task.finished_at) }}
            </span>
            <span v-if="getTaskStats(task)" class="meta-item">
              {{ getTaskStats(task) }}
            </span>
            <span v-else class="meta-item">处理 {{ task.processed }} 项</span>
          </div>
          <div class="task-actions">
            <n-button v-bind="getButtonStyle('icon')" size="small" @click="fetchTaskDetail(task.task_id)">
              <template #icon><n-icon><LogIcon /></n-icon></template>
            </n-button>
            <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDeleteTask(task.task_id)">
              <template #icon><n-icon><DeleteIcon /></n-icon></template>
            </n-button>
          </div>
        </div>
      </n-card>

      <div ref="scrollTarget" class="load-more-sentinel">
        <n-spin v-if="loading" size="small" description="正在加载更多..." />
        <div v-else-if="!hasMore" class="end-of-list">
          <n-divider dashed>
            <span style="font-size: var(--text-sm); color: var(--text-tertiary)">到底了，共 {{ tasks.length }} 条记录</span>
          </n-divider>
        </div>
        <div v-else class="can-load-more">
           <n-icon size="16"><MoreIcon /></n-icon>
           向下滚动加载更多
        </div>
      </div>
    </div>

    <AppGlassModal appearance-key="task-history-modal" v-model:show="showLogModal" style="width: 960px;" title="任务日志">
      <template #header-extra>
        <n-tag v-if="selectedTask" size="small" round :bordered="false" :style="getStatusTag(selectedTask.status).style">
          {{ getStatusTag(selectedTask.status).label }}
        </n-tag>
      </template>
      <div v-if="selectedTask" class="log-scroll-area">
        <div class="log-container">
          <div v-for="group in selectedTaskGroupedLogs" :key="group.groupTime" class="log-group">
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
    </AppGlassModal>
  </div>
</template>

<style scoped>
.task-history-view { width: 100%; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-4);
}
.page-header h1 { margin: 0; font-size: var(--text-3xl); }
.subtitle { font-size: var(--text-sm); color: var(--n-primary-color); letter-spacing: var(--tracking-widest); font-weight: bold; }
.page-header :deep(.n-space) { align-items: center; }
/* 按钮高度、Tabs 高度/间距/内边距 由 global.css CSS 变量统一管理 */

.task-list { margin-bottom: var(--space-6); }
.task-list .task-card {
  margin-bottom: var(--space-4);
  transition: all var(--transition-normal);
}
.task-list .task-card :deep(.n-card__content) {
  padding: 16px 20px !important;
}
.task-list .task-card:hover {
  border-color: var(--n-primary-color) !important;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}
.header-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}
.task-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-time { color: var(--text-tertiary); font-size: var(--text-sm); white-space: nowrap; font-variant-numeric: tabular-nums; }
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.task-meta {
  display: flex;
  gap: var(--space-4);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}
.task-actions { display: flex; gap: var(--space-1); }

.log-container {
  font-family: var(--code-font);
  font-size: var(--text-sm);
  background: var(--app-surface-card-mixed);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
}
.log-group {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-light);
}
.log-group:last-child { border-bottom: none; }
.log-group-time {
  color: var(--n-primary-color);
  font-size: var(--text-xs);
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
  gap: var(--space-1);
}
.log-line {
  display: flex;
  gap: var(--space-2);
  padding: 2px 0;
}
.log-time { color: var(--text-tertiary); min-width: 75px; }
.log-level {
  min-width: 40px;
  font-weight: bold;
}
.log-level.info { color: #52c41a; }
.log-level.error { color: #ff4d4f; }
.log-level.warning { color: #faad14; }
.log-msg { flex: 1; word-break: break-all; }

.load-more-sentinel {
  padding: var(--space-6) 0 var(--space-12);
  display: flex;
  justify-content: center;
  align-items: center;
}

.end-of-list {
  width: 100%;
  opacity: var(--opacity-60);
}

.can-load-more {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--text-md);
  opacity: var(--opacity-80);
}

/* === 移动端适配: 任务日志弹框内容 === */
@media (max-width: 767px) {
  /* 日志容器: 缩小 padding 和字号 */
  .log-container { padding: var(--space-2); font-size: var(--text-xs); }
  .log-group { gap: var(--space-2); padding: var(--space-1) 0; }
  .log-group-time { min-width: 60px; font-size: var(--text-2xs); }
  .log-group-line { margin: 2px 0; }

  /* 日志行: 时间+级别独占一行, 消息换行到下一行 */
  .log-line { flex-wrap: wrap; gap: 4px; padding: 1px 0; }
  .log-time { font-size: var(--text-2xs); min-width: 0 !important; }
  .log-level { font-size: var(--text-2xs); min-width: 0 !important; }
  .log-msg { font-size: var(--text-xs); flex: none !important; width: 100%; }

  /* 任务卡片: 缩小 padding */
  .task-list .task-card :deep(.n-card__content) { padding: 12px !important; }
  .card-header { gap: var(--space-2); margin-bottom: var(--space-1); }
  .task-name { font-size: var(--text-sm); }
  .task-time { font-size: var(--text-2xs); }
  .card-footer { flex-wrap: wrap; gap: var(--space-2); }
  .task-meta { gap: var(--space-2); font-size: var(--text-2xs); }
}
</style>
