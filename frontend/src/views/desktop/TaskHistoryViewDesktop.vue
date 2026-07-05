<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { NCard, NSpace, NTag, NButton, NIcon, NEmpty, NModal, NPopconfirm, NSpin, NDivider, NText, NTabs, NTabPane, NList, NListItem } from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  RefreshOutlined as RefreshIcon,
  VisibilityOutlined as ViewIcon,
  ClearAllOutlined as ClearIcon,
  KeyboardDoubleArrowDownOutlined as MoreIcon
} from '@vicons/material'
import AppGlassModal from '../../components/AppGlassModal.vue'
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
  <div class="task-history-view">
    <div class="page-header">
      <div>
        <h1>任务中心</h1>
        <div class="subtitle">任务执行历史与日志</div>
      </div>
      <n-space>
        <n-tabs type="segment" v-model:value="moduleFilter" size="medium" class="filter-tabs" style="height: var(--space-8)">
          <n-tab-pane name="all" tab="全部" />
          <n-tab-pane v-for="mod in moduleOptions.slice(1)" :key="mod" :name="mod" :tab="mod" />
        </n-tabs>
        <n-button v-bind="getButtonStyle('secondary')" @click="startPolling">
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
      <n-list hoverable :show-divider="false">
        <n-list-item v-for="task in tasks" :key="task.task_id" class="task-item">
          <div class="task-row">
            <div class="task-main">
              <n-tag size="small" round :bordered="false" :style="getStatusTag(task.status).style">
                {{ getStatusTag(task.status).label }}
              </n-tag>
              <span class="task-time">{{ formatTime(task.started_at) }}</span>
              <span class="task-name">{{ task.name || task.module }}</span>
            </div>
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
          </div>
        </n-list-item>
      </n-list>

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
          <div v-for="(log, i) in selectedTask.logs" :key="i" class="log-line">
            <span class="log-time">{{ log.time }}</span>
            <span :class="['log-level', log.level.toLowerCase()]">{{ log.level }}</span>
            <span class="log-msg">{{ log.message }}</span>
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
.page-header :deep(.n-space) { align-items: stretch; }
.page-header :deep(.n-button) { height: var(--space-8); }
.filter-tabs { height: var(--space-8); }
.filter-tabs :deep(.n-tabs-rail) { height: 100% !important; gap: 4px !important; padding: 3px !important; }
.filter-tabs :deep(.n-tabs-tab) { height: 26px !important; padding: 0 12px !important; display: flex !important; align-items: center !important; }

.task-list { margin-bottom: var(--space-6); }
.task-list :deep(.n-list) { background: transparent; }
.task-list :deep(.n-list-item) {
  background: var(--app-surface-list-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4) !important;
  margin-bottom: var(--space-2);
}

/* 原task-item样式已迁移到n-list-item */
.task-item { /* 内部元素样式 */ }

.task-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.task-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
}
.module-icon { font-size: var(--text-xl); }
.task-name { font-weight: 500; }
.task-time { color: var(--text-tertiary); font-size: var(--text-sm); white-space: nowrap; font-variant-numeric: tabular-nums; }
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
.log-line {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-0) 0;
  border-bottom: 1px solid var(--border-light);
}
.log-line:last-child { border-bottom: none; }
.log-time { color: var(--text-tertiary); min-width: 60px; }
.log-level {
  min-width: 40px;
  font-weight: bold;
}
.log-level.info { color: var(--n-info-color); }
.log-level.error { color: var(--n-error-color); }
.log-level.warning { color: var(--n-warning-color); }
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
</style>
