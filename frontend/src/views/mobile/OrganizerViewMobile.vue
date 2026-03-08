<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { 
  NButton, NIcon, NTabs, NTabPane, NTag, NDropdown, NCard, NSpace
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  SaveOutlined as SaveIcon,
  PlayArrowOutlined as PlayIcon,
  ContentCopyOutlined as CopyIcon,
  BoltOutlined as BoltIcon,
  AccessTimeOutlined as ScheduleIcon,
  MoreVertOutlined as MoreIcon,
  FolderCopyOutlined as TaskIcon,
  TextFormatOutlined as RuleIcon,
  StopOutlined as StopIcon
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

const getRuleActions = (index: number) => [
  { label: '复制规则', key: 'duplicate', props: { onClick: () => duplicateRule(index) } },
  { label: '删除规则', key: 'delete', props: { onClick: () => deleteRule(index) } }
]

const getTaskActions = (index: number, task: any) => [
  { label: '复制任务', key: 'duplicate', props: { onClick: () => duplicateTask(index) } },
  { label: '删除任务', key: 'delete', props: { onClick: () => deleteTask(index) } }
]

onMounted(() => {
  fetchConfig()
  startBgTaskPolling()
})
onUnmounted(stopBgTaskPolling)
</script>

<template>
  <div class="organizer-mobile">
    <div class="header-mobile">
      <h1>整理与重命名</h1>
      <n-button v-bind="getButtonStyle('primary')" circle :loading="loading" @click="saveConfig">
      </n-button>
    </div>

    <!-- 后台任务状态 -->
    <n-card v-if="backgroundTasks.length > 0" size="small" style="margin: 8px 12px">
      <template #header>
        <n-space align="center" :size="8">
          <span style="font-size: 14px">后台任务</span>
          <n-tag size="small" :bordered="false">{{ runningTasks.length }} 运行中</n-tag>
        </n-space>
      </template>
      <n-space vertical size="small">
        <div v-for="task in runningTasks" :key="task.task_id" class="bg-task-item">
          <n-space align="center" justify="space-between">
            <n-space align="center" :size="8">
              <n-tag type="info" size="small">运行中</n-tag>
              <span style="font-size: 13px">{{ task.name }}</span>
            </n-space>
            <n-button size="tiny" type="error" secondary @click="stopBackgroundTask(task.task_id)">
              <template #icon><n-icon><StopIcon /></n-icon></template>
            </n-button>
          </n-space>
        </div>
        <div v-for="task in finishedTasks" :key="task.task_id" class="bg-task-item">
          <n-space align="center" justify="space-between">
            <n-space align="center" :size="8">
              <n-tag :type="task.status === 'completed' ? 'success' : task.status === 'stopped' ? 'warning' : 'error'" size="small">
                {{ task.status === 'completed' ? '完成' : task.status === 'stopped' ? '停止' : '错误' }}
              </n-tag>
              <span style="font-size: 13px">{{ task.name }}</span>
            </n-space>
            <n-button size="tiny" quaternary @click="deleteBackgroundTask(task.task_id)">清除</n-button>
          </n-space>
        </div>
      </n-space>
    </n-card>

    <n-tabs type="line" animated class="mobile-tabs" pane-class="mobile-tab-pane">
      <!-- 规则管理 Tab -->
      <n-tab-pane name="rules" tab="规则">
        <div class="tab-content">
          <n-button v-bind="getButtonStyle('primary')" block dashed class="mb-4" @click="openEditRule(-1)">
            新建规则
          </n-button>
          
          <div class="card-list">
            <n-card v-for="(rule, i) in rules" :key="rule.id" class="mobile-card" size="small" @click="openEditRule(i)">
              <div class="card-header">
                <div class="title-row">
                  <n-icon :color="i === 0 ? 'var(--n-primary-color)' : '#888'" size="20"><RuleIcon /></n-icon>
                  <span class="item-title">{{ rule.name }}</span>
                  <n-tag v-if="i === 0" size="tiny" type="success" round ghost>默认</n-tag>
                </div>
                <n-dropdown trigger="click" :options="getRuleActions(i)" size="large">
                   <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop>
                     <template #icon><n-icon><MoreIcon /></n-icon></template>
                   </n-button>
                </n-dropdown>
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
            </n-card>
          </div>
        </div>
      </n-tab-pane>

      <!-- 整理任务 Tab -->
      <n-tab-pane name="tasks" tab="任务">
        <div class="tab-content">
          <n-button v-bind="getButtonStyle('primary')" block dashed class="mb-4" @click="openEditTask(-1)">
            新建任务
          </n-button>
          
          <div class="card-list">
            <n-card v-for="(task, i) in tasks" :key="task.id" class="mobile-card" size="small" @click="openEditTask(i)">
              <div class="card-header">
                <div class="title-row">
                  <n-icon style="color: var(--n-primary-color)" size="20"><TaskIcon /></n-icon>
                  <span class="item-title">{{ task.name }}</span>
                </div>
                <div class="action-row">
                   <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click.stop="requestRunTask(task)" style="margin-right: 4px">
                     <template #icon><n-icon><PlayIcon /></n-icon></template>
                   </n-button>
                   <n-dropdown trigger="click" :options="getTaskActions(i, task)" size="large">
                      <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop>
                        <template #icon><n-icon><MoreIcon /></n-icon></template>
                      </n-button>
                   </n-dropdown>
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
                  <!-- 实时监控快速切换 -->
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

                  <!-- 定时扫描快速切换 -->
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
            </n-card>
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- Modals -->
    <RuleEditModal v-model:show="showRuleModal" :rule-data="editingRule" :is-new="editingRuleIndex===-1" @save="handleSaveRule" />
    <TaskEditModal v-model:show="showTaskModal" :task-data="editingTask" :is-new="editingTaskIndex===-1" :available-rules="rules" :api-base="API_BASE" @save="handleSaveTask" />
    <ExecutionLogModal v-model:show="showExecModal" :is-dry-run="isDryRun" :is-running="isRunning" :logs="execLogs" :scanning-status="scanningStatus" :target-dir="editingTask?.target_dir || ''" @commit="requestCommitBatch" />
  </div>
</template>

<style scoped>
.organizer-mobile {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--app-background);
  padding-bottom: 80px;
}

.header-mobile {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.header-mobile h1 { margin: 0; font-size: 20px; font-weight: 800; }

.mobile-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) { padding: 0 16px; }
:deep(.n-tabs-pane-wrapper) { flex: 1; overflow: hidden; }
:deep(.mobile-tab-pane) { height: 100%; overflow-y: auto; }

.tab-content { padding: 16px; }
.mb-4 { margin-bottom: 16px; }

.card-list { display: flex; flex-direction: column; gap: 12px; }
.mobile-card { border-radius: 12px; }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.title-row { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
.item-title { font-weight: 600; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.action-row { display: flex; align-items: center; flex-shrink: 0; }

.rule-details { margin-top: 8px; }
.detail-row { display: flex; flex-direction: column; margin-bottom: 6px; }
.detail-row .label { font-size: 10px; color: var(--text-tertiary); text-transform: uppercase; }
.detail-row .pattern { 
  font-family: monospace; 
  background: var(--app-surface-inner); 
  padding: 4px 6px; 
  border-radius: 4px; 
  font-size: 12px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.task-details { display: flex; flex-direction: column; gap: 8px; }
.path-box { display: flex; flex-direction: column; min-width: 0; } /* min-width: 0 is crucial for flex child truncation */
.path-label { font-size: 10px; color: var(--text-tertiary); }
.path-val { 
  font-family: monospace; 
  background: var(--app-surface-inner); 
  padding: 6px 8px; 
  border-radius: 6px; 
  font-size: 12px;
  word-break: break-all; /* Allow path to wrap */
  line-height: 1.4;
}

.card-footer { 
  margin-top: 12px; 
  padding-top: 8px; 
  border-top: 1px solid var(--n-border-color); 
  display: flex; 
  justify-content: flex-end; 
  gap: 8px; 
}

.bg-task-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--n-border-color);
}
.bg-task-item:last-child {
  border-bottom: none;
}
</style>