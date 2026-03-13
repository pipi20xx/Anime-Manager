<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue'
import {
  NButton, NIcon, NTabs, NTabPane, NTag, NDrawer, NDrawerContent, NSpace
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  PlayArrowOutlined as PlayIcon,
  BoltOutlined as BoltIcon,
  AccessTimeOutlined as ScheduleIcon,
  MoreVertOutlined as MoreIcon,
  FolderCopyOutlined as TaskIcon,
  TextFormatOutlined as RuleIcon,
  StopOutlined as StopIcon,
  ContentCopyOutlined as CopyIcon,
  DeleteOutlined as DeleteIcon,
  AddOutlined as AddIcon
} from '@vicons/material'

import RuleEditModal from '../../components/RuleEditModal.vue'
import TaskEditModal from '../../components/TaskEditModal.vue'
import ExecutionLogModal from '../../components/ExecutionLogModal.vue'
import { useOrganizerView } from '../../composables/views/useOrganizerView'
import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  API_BASE,
  rules,
  tasks,
  loading,
  showRuleModal,
  editingRule,
  editingRuleIndex,
  showTaskModal,
  editingTask,
  editingTaskIndex,
  showExecModal,
  isRunning,
  isDryRun,
  execLogs,
  scanningStatus,
  backgroundTasks,
  fetchBackgroundTasks,
  stopBackgroundTask,
  deleteBackgroundTask,
  startBgTaskPolling,
  stopBgTaskPolling,
  fetchConfig,
  saveConfig,
  openEditRule,
  handleSaveRule,
  deleteRule,
  duplicateRule,
  openEditTask,
  handleSaveTask,
  deleteTask,
  duplicateTask,
  toggleTaskMonitor,
  requestRunTask,
  requestCommitBatch
} = useOrganizerView()

useBackClose(showRuleModal)
useBackClose(showTaskModal)
useBackClose(showExecModal)

const runningTasks = computed(() => backgroundTasks.value.filter(t => t.status === 'running'))
const finishedTasks = computed(() => backgroundTasks.value.filter(t => t.status !== 'running'))

// 操作抽屉状态
const showRuleActionDrawer = ref(false)
const showTaskActionDrawer = ref(false)
const currentRuleIndex = ref<number>(-1)
const currentTaskIndex = ref<number>(-1)

useBackClose(showRuleActionDrawer)
useBackClose(showTaskActionDrawer)

const openRuleActions = (index: number, e: Event) => {
  e.stopPropagation()
  currentRuleIndex.value = index
  showRuleActionDrawer.value = true
}

const openTaskActions = (index: number, e: Event) => {
  e.stopPropagation()
  currentTaskIndex.value = index
  showTaskActionDrawer.value = true
}

const handleRuleAction = (action: string) => {
  showRuleActionDrawer.value = false
  setTimeout(() => {
    if (action === 'duplicate') duplicateRule(currentRuleIndex.value)
    else if (action === 'delete') deleteRule(currentRuleIndex.value)
  }, 300)
}

const handleTaskAction = (action: string) => {
  showTaskActionDrawer.value = false
  setTimeout(() => {
    if (action === 'duplicate') duplicateTask(currentTaskIndex.value)
    else if (action === 'delete') deleteTask(currentTaskIndex.value)
  }, 300)
}

onMounted(() => {
  fetchConfig()
  startBgTaskPolling()
})
onUnmounted(stopBgTaskPolling)
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- 页面头部 -->
    <div class="m-header m-header-plain">
      <h1 class="m-header-title">整理与重命名</h1>
      <n-button v-bind="getButtonStyle('primary')" :loading="loading" @click="saveConfig">
        <template #icon><n-icon><SaveIcon /></n-icon></template>
        保存
      </n-button>
    </div>

    <!-- 后台任务状态 -->
    <div v-if="backgroundTasks.length > 0" class="m-card m-card-compact m-mb-md" style="margin: var(--m-spacing-md);">
      <div class="m-card-header">
        <div class="m-flex m-items-center m-gap-sm">
          <span class="m-card-title">后台任务</span>
          <n-tag size="small" :bordered="false">{{ runningTasks.length }} 运行中</n-tag>
        </div>
      </div>
      <div class="m-list">
        <div v-for="task in runningTasks" :key="task.task_id" class="m-list-item">
          <div class="m-flex m-items-center m-gap-sm">
            <n-tag type="info" size="small">运行中</n-tag>
            <span class="m-list-item-title">{{ task.name }}</span>
          </div>
          <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="stopBackgroundTask(task.task_id)">
            <template #icon><n-icon><StopIcon /></n-icon></template>
          </n-button>
        </div>
        <div v-for="task in finishedTasks" :key="task.task_id" class="m-list-item">
          <div class="m-flex m-items-center m-gap-sm">
            <n-tag :type="task.status === 'completed' ? 'success' : task.status === 'stopped' ? 'warning' : 'error'" size="small">
              {{ task.status === 'completed' ? '完成' : task.status === 'stopped' ? '停止' : '错误' }}
            </n-tag>
            <span class="m-list-item-title">{{ task.name }}</span>
          </div>
          <n-button v-bind="getButtonStyle('text')" size="small" @click="deleteBackgroundTask(task.task_id)">清除</n-button>
        </div>
      </div>
    </div>

    <n-tabs type="line" animated class="m-tabs" pane-class="m-tab-content">
      <!-- 规则管理 Tab -->
      <n-tab-pane name="rules" tab="规则">
        <div class="m-tab-content">
          <div class="m-action-bar m-mb-lg">
            <n-button type="primary" dashed size="small" @click="openEditRule(-1)">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              新建规则
            </n-button>
          </div>
          
          <div class="m-card-list">
            <div
              v-for="(rule, i) in rules"
              :key="rule.id"
              class="m-card-item m-card-touchable m-touchable"
              @click="openEditRule(i)"
            >
              <div class="card-header">
                <div class="title-row">
                  <n-icon :color="i === 0 ? 'var(--n-primary-color)' : 'var(--text-muted)'" size="20"><RuleIcon /></n-icon>
                  <span class="item-title m-truncate">{{ rule.name }}</span>
                  <n-tag v-if="i === 0" size="tiny" type="success" round ghost>默认</n-tag>
                </div>
                <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop="openRuleActions(i, $event)">
                  <template #icon><n-icon><MoreIcon /></n-icon></template>
                </n-button>
              </div>
              
              <div class="rule-details">
                <div class="detail-row">
                  <span class="label">电影</span>
                  <code class="pattern">{{ rule.movie_pattern || '未设置' }}</code>
                </div>
                <div class="detail-row">
                  <span class="label">剧集</span>
                  <code class="pattern">{{ rule.tv_pattern || '未设置' }}</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </n-tab-pane>

      <!-- 整理任务 Tab -->
      <n-tab-pane name="tasks" tab="任务">
        <div class="m-tab-content">
          <div class="m-action-bar m-mb-lg">
            <n-button type="primary" dashed size="small" @click="openEditTask(-1)">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              新建任务
            </n-button>
          </div>
          
          <div class="m-card-list">
            <div
              v-for="(task, i) in tasks"
              :key="task.id"
              class="m-card-item m-card-touchable m-touchable"
              @click="openEditTask(i)"
            >
              <div class="card-header">
                <div class="title-row">
                  <n-icon style="color: var(--n-primary-color)" size="20"><TaskIcon /></n-icon>
                  <span class="item-title m-truncate">{{ task.name }}</span>
                </div>
                <div class="action-row">
                   <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click.stop="requestRunTask(task)">
                     <template #icon><n-icon><PlayIcon /></n-icon></template>
                   </n-button>
                   <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop="openTaskActions(i, $event)">
                     <template #icon><n-icon><MoreIcon /></n-icon></template>
                   </n-button>
                </div>
              </div>
              
              <div class="task-details">
                 <div class="path-box">
                   <span class="path-label">源</span>
                   <div class="path-val">{{ task.source_dir }}</div>
                 </div>
                 <div class="path-box">
                   <span class="path-label">目标</span>
                   <div class="path-val">{{ task.target_dir }}</div>
                 </div>
                 <div class="rule-tag">
                    <n-tag size="tiny" :bordered="false" type="info">
                      {{ rules.find(r => r.id === task.rule_id)?.name || '未指定规则' }}
                    </n-tag>
                 </div>
              </div>

              <div class="card-footer">
                  <n-button 
                    size="tiny" 
                    secondary
                    round
                    :type="task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode) ? 'info' : 'default'"
                    @click.stop="toggleTaskMonitor(task, 'incremental')"
                  >
                    <template #icon><n-icon><BoltIcon /></n-icon></template>
                    实时监控
                  </n-button>

                  <n-button 
                    size="tiny" 
                    secondary
                    round
                    :type="task.scheduler_enabled || task.monitor_mode === 'scheduled' ? 'warning' : 'default'"
                    @click.stop="toggleTaskMonitor(task, 'scheduler')"
                  >
                    <template #icon><n-icon><ScheduleIcon /></n-icon></template>
                    定时扫描
                  </n-button>
              </div>
            </div>
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- Modals -->
    <RuleEditModal v-model:show="showRuleModal" :rule-data="editingRule" :is-new="editingRuleIndex===-1" @save="handleSaveRule" />
    <TaskEditModal v-model:show="showTaskModal" :task-data="editingTask" :is-new="editingTaskIndex===-1" :available-rules="rules" :api-base="API_BASE" @save="handleSaveTask" />
    <ExecutionLogModal v-model:show="showExecModal" :is-dry-run="isDryRun" :is-running="isRunning" :logs="execLogs" :scanning-status="scanningStatus" :target-dir="editingTask?.target_dir || ''" @commit="requestCommitBatch" />

    <!-- 规则操作抽屉 -->
    <n-drawer v-model:show="showRuleActionDrawer" placement="bottom" :height="200" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content closable title="规则操作">
        <div class="action-list">
          <div class="action-item" @click="handleRuleAction('duplicate')">
            <div class="action-icon">
              <n-icon size="22"><CopyIcon /></n-icon>
            </div>
            <span class="action-label">复制规则</span>
          </div>
          <div class="action-item danger" @click="handleRuleAction('delete')">
            <div class="action-icon">
              <n-icon size="22"><DeleteIcon /></n-icon>
            </div>
            <span class="action-label">删除规则</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- 任务操作抽屉 -->
    <n-drawer v-model:show="showTaskActionDrawer" placement="bottom" :height="200" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content closable title="任务操作">
        <div class="action-list">
          <div class="action-item" @click="handleTaskAction('duplicate')">
            <div class="action-icon">
              <n-icon size="22"><CopyIcon /></n-icon>
            </div>
            <span class="action-label">复制任务</span>
          </div>
          <div class="action-item danger" @click="handleTaskAction('delete')">
            <div class="action-icon">
              <n-icon size="22"><DeleteIcon /></n-icon>
            </div>
            <span class="action-label">删除任务</span>
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

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--m-spacing-md);
}

.title-row {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  flex: 1;
  min-width: 0;
}

.item-title {
  font-weight: 600;
  font-size: var(--m-text-md);
}

.action-row {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-xs);
  flex-shrink: 0;
}

/* 规则详情 */
.rule-details {
  margin-top: var(--m-spacing-sm);
}

.detail-row {
  display: flex;
  flex-direction: column;
  margin-bottom: var(--m-spacing-sm);
}

.detail-row .label {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  margin-bottom: var(--m-spacing-xs);
}

.detail-row .pattern {
  font-family: monospace;
  background: var(--app-surface-inner);
  padding: var(--m-spacing-sm);
  border-radius: var(--m-radius-sm);
  font-size: var(--m-text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 任务详情 */
.task-details {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.path-box {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.path-label {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--m-spacing-xs);
}

.path-val {
  font-family: monospace;
  background: var(--app-surface-inner);
  padding: var(--m-spacing-sm);
  border-radius: var(--m-radius-sm);
  font-size: var(--m-text-sm);
  word-break: break-all;
  line-height: 1.4;
}

.rule-tag {
  margin-top: var(--m-spacing-xs);
}

.card-footer {
  margin-top: var(--m-spacing-md);
  padding-top: var(--m-spacing-md);
  border-top: 1px solid var(--border-light);
  display: flex;
  justify-content: flex-end;
  gap: var(--m-spacing-sm);
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
</style>
