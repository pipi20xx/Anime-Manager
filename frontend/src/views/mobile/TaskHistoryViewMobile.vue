<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { NCard, NSpace, NTag, NButton, NIcon, NEmpty, NModal, NScrollbar, NPopconfirm, NSpin, NDivider, NText, NRadioGroup, NRadioButton } from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  RefreshOutlined as RefreshIcon,
  VisibilityOutlined as ViewIcon,
  ClearAllOutlined as ClearIcon,
  KeyboardDoubleArrowDownOutlined as MoreIcon
} from '@vicons/material'
import { useTaskHistory } from '../../composables/views/useTaskHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  tasks,
  loading,
  selectedTask,
  showLogModal,
  moduleFilter,
  hasMore,
  fetchData,
  loadMore,
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

onMounted(startPolling)
onUnmounted(() => {
  stopPolling()
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="mobile-task-history-view">
    <div class="mobile-header">
      <div class="header-left">
        <span class="header-title">任务中心</span>
      </div>
      <div class="header-right">
        <n-button v-bind="getButtonStyle('icon')" @click="startPolling">
          <template #icon><n-icon><RefreshIcon /></n-icon></template>
        </n-button>
        <n-popconfirm 
          @positive-click="cleanupTasks"
          positive-text="确定"
          negative-text="取消"
        >
          <template #trigger>
            <n-button v-bind="getButtonStyle('icon')">
              <template #icon><n-icon><ClearIcon /></n-icon></template>
            </n-button>
          </template>
          确定要清理超过 30 天的任务记录吗？
        </n-popconfirm>
      </div>
    </div>

    <div class="filter-bar">
      <n-radio-group v-model:value="moduleFilter" size="small">
        <n-radio-button value="all">全部</n-radio-button>
        <n-radio-button v-for="mod in moduleOptions.slice(1)" :key="mod" :value="mod">
          {{ mod }}
        </n-radio-button>
      </n-radio-group>
    </div>

    <n-card v-if="tasks.length === 0" embedded style="margin-top: 16px">
      <n-empty description="暂无任务记录" />
    </n-card>

    <div v-else class="task-list">
      <n-card v-for="task in tasks" :key="task.task_id" class="task-item" embedded>
        <div class="task-header">
          <div class="task-main">
            <span class="task-name">{{ task.name || task.module }}</span>
          </div>
          <n-tag size="small" round :bordered="false" :style="getStatusTag(task.status).style">
            {{ getStatusTag(task.status).label }}
          </n-tag>
        </div>
        <div class="task-time">{{ formatTime(task.started_at) }}</div>
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
          <n-button v-bind="getButtonStyle('secondary')" size="small" @click="fetchTaskDetail(task.task_id)">
            查看日志
          </n-button>
          <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="deleteTask(task.task_id)">
            <template #icon><n-icon><DeleteIcon /></n-icon></template>
          </n-button>
        </div>
      </n-card>

      <div ref="scrollTarget" class="load-more-sentinel">
        <n-spin v-if="loading" size="small" description="正在加载..." />
        <div v-else-if="!hasMore" class="end-of-list">
          <n-divider dashed>
            <span style="font-size: 11px; color: var(--text-tertiary)">到底了 (共{{ tasks.length }}条)</span>
          </n-divider>
        </div>
        <div v-else class="can-load-more">
           <n-icon size="14"><MoreIcon /></n-icon>
           向上滑动加载更多
        </div>
      </div>
    </div>

    <n-modal v-model:show="showLogModal" preset="card" style="width: 90vw; max-height: 80vh" title="任务日志">
      <template #header-extra>
        <n-tag v-if="selectedTask" size="small" round :bordered="false" :style="getStatusTag(selectedTask.status).style">
          {{ getStatusTag(selectedTask.status).label }}
        </n-tag>
      </template>
      <n-scrollbar v-if="selectedTask" style="max-height: 60vh">
        <div class="log-container">
          <div v-for="(log, i) in selectedTask.logs" :key="i" class="log-line">
            <span class="log-time">{{ log.time }}</span>
            <span :class="['log-level', log.level.toLowerCase()]">{{ log.level }}</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
        </div>
      </n-scrollbar>
    </n-modal>
  </div>
</template>

<style scoped>
.mobile-task-history-view {
  padding-bottom: var(--m-spacing-lg);
}

.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--m-spacing-xs) var(--m-spacing-md) var(--m-spacing-xs);
}

.header-left {
  display: flex;
  align-items: center;
}

.header-title {
  font-size: var(--m-text-xl);
  font-weight: 700;
}

.filter-bar {
  background: var(--app-surface-inner);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-spacing-lg);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.filter-bar :deep(.n-radio-group) {
  display: flex;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.filter-bar :deep(.n-radio-button) {
  flex-shrink: 0;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.task-item {
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.task-item:active {
  transform: scale(0.98);
  box-shadow: var(--shadow-sm);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--m-spacing-sm);
}

.task-main {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  flex: 1;
}

.module-icon {
  font-size: var(--m-text-md);
}

.task-name {
  font-weight: 600;
  font-size: var(--m-text-md);
}

.task-time {
  color: var(--text-tertiary);
  font-size: var(--m-text-xs);
  margin-bottom: var(--m-spacing-sm);
}

.task-meta {
  display: flex;
  gap: var(--m-spacing-lg);
  color: var(--text-tertiary);
  font-size: var(--m-text-xs);
  margin-bottom: var(--m-spacing-md);
}

.task-actions {
  display: flex;
  gap: var(--m-spacing-sm);
}

.log-container {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: var(--m-text-xs);
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  padding: var(--m-spacing-sm);
}

.log-line {
  display: flex;
  gap: var(--m-spacing-sm);
  padding: var(--m-spacing-xs) 0;
  border-bottom: 1px solid var(--border-light);
}

.log-line:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--text-tertiary);
  min-width: 50px;
}

.log-level {
  min-width: 35px;
  font-weight: bold;
}

.log-level.info {
  color: var(--n-info-color);
}

.log-level.error {
  color: var(--n-error-color);
}

.log-level.warning {
  color: var(--n-warning-color);
}

.log-msg {
  flex: 1;
  word-break: break-all;
}

.load-more-sentinel {
  padding: var(--m-spacing-xl) 0 var(--m-spacing-3xl);
  display: flex;
  justify-content: center;
  align-items: center;
}

.end-of-list {
  width: 100%;
  opacity: 0.6;
}

.can-load-more {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  color: var(--text-tertiary);
  font-size: var(--m-text-sm);
  opacity: 0.8;
}
</style>
