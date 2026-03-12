<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NTabs, NTabPane, NTag, NTooltip, NProgress, NEmpty
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  SaveOutlined as SaveIcon,
  PlayArrowOutlined as PlayIcon,
  ContentCopyOutlined as CopyIcon,
  DragIndicatorOutlined as DragIcon,
  BoltOutlined as BoltIcon,
  AccessTimeOutlined as ScheduleIcon,
  StopOutlined as StopIcon
} from '@vicons/material'
import draggable from 'vuedraggable'

import RuleEditModal from '../../components/RuleEditModal.vue'
import TaskEditModal from '../../components/TaskEditModal.vue'
import ExecutionLogModal from '../../components/ExecutionLogModal.vue'
import { useOrganizerView } from '../../composables/views/useOrganizerView'
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

const runningTasks = computed(() => backgroundTasks.value.filter(t => t.status === 'running'))
const finishedTasks = computed(() => backgroundTasks.value.filter(t => t.status !== 'running'))

onMounted(() => {
  fetchConfig()
  startBgTaskPolling()
})
onUnmounted(stopBgTaskPolling)
</script>

<template>
  <div class="organizer-view">
    <div class="page-header">
      <div>
        <h1>整理与重命名</h1>
        <div class="subtitle">任务管理与执行</div>
      </div>
      <n-button v-bind="getButtonStyle('primary')" size="large" :loading="loading" @click="saveConfig">
        强制保存配置
      </n-button>
    </div>

    <!-- 后台任务状态 -->
    <n-card v-if="backgroundTasks.length > 0" bordered embedded style="margin-bottom: 16px">
      <template #header>
        <n-space align="center">
          <span>后台任务</span>
          <n-tag size="small" :bordered="false">{{ runningTasks.length }} 运行中</n-tag>
        </n-space>
      </template>
      <n-space vertical size="small">
        <n-card v-for="task in runningTasks" :key="task.task_id" size="small" embedded>
          <n-space align="center" justify="space-between">
            <n-space align="center">
              <n-tag type="info" size="small">运行中</n-tag>
              <span>{{ task.name }}</span>
              <n-tag size="tiny" :bordered="false">{{ task.dry_run ? '预览' : '正式' }}</n-tag>
            </n-space>
            <n-space align="center">
              <span style="font-size: 12px; color: var(--n-text-color-3)">已处理: {{ task.processed }}</span>
              <n-button size="tiny" type="error" secondary @click="stopBackgroundTask(task.task_id)">
                <template #icon><n-icon><StopIcon /></n-icon></template>
                停止
              </n-button>
            </n-space>
          </n-space>
        </n-card>
        <n-card v-for="task in finishedTasks" :key="task.task_id" size="small" embedded>
          <n-space align="center" justify="space-between">
            <n-space align="center">
              <n-tag :type="task.status === 'completed' ? 'success' : task.status === 'stopped' ? 'warning' : 'error'" size="small">
                {{ task.status === 'completed' ? '已完成' : task.status === 'stopped' ? '已停止' : '错误' }}
              </n-tag>
              <span>{{ task.name }}</span>
              <span style="font-size: 12px; color: var(--n-text-color-3)">处理: {{ task.processed }}</span>
            </n-space>
            <n-button size="tiny" quaternary @click="deleteBackgroundTask(task.task_id)">清除</n-button>
          </n-space>
        </n-card>
      </n-space>
    </n-card>

    <n-tabs type="card" animated>
      <!-- 规则管理 Tab -->
      <n-tab-pane name="rules" tab="规则管理">
        <n-space vertical size="large">
          <n-space justify="end">
            <n-button v-bind="getButtonStyle('primary')" @click="openEditRule(-1)">
              创建重命名规则
            </n-button>
          </n-space>
          
          <draggable v-model="rules" item-key="id" @end="saveConfig" class="card-grid" handle=".drag-handle">
            <template #item="{element: rule, index: i}">
              <n-card bordered :class="['rule-card', 'clickable-card', { 'default-rule': i === 0 }]" @click="openEditRule(i)">
                <template #header>
                  <div class="card-title-box">
                    <n-icon class="drag-handle" @click.stop :color="i === 0 ? 'var(--n-primary-color)' : 'var(--text-muted)'"><DragIcon /></n-icon>
                    <span class="card-title-text">{{ rule.name }}</span>
                    <n-tag v-if="i === 0" size="tiny" type="success" round ghost>默认</n-tag>
                  </div>
                </template>
                <div class="rule-preview-mini">
                  <div class="p-item"><span>电影</span><code>{{ rule.movie_pattern || '未设置' }}</code></div>
                  <div class="p-item"><span>剧集</span><code>{{ rule.tv_pattern || '未设置' }}</code></div>
                </div>
                <template #action>
                  <n-space justify="end" @click.stop>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button v-bind="getButtonStyle('icon')" size="small" @click="duplicateRule(i)">
                          <template #icon><n-icon><CopyIcon /></n-icon></template>
                        </n-button>
                      </template>
                      复制规则
                    </n-tooltip>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="deleteRule(i)">
                          <template #icon><n-icon><DeleteIcon /></n-icon></template>
                        </n-button>
                      </template>
                      删除规则
                    </n-tooltip>
                  </n-space>
                </template>
              </n-card>
            </template>
          </draggable>
        </n-space>
      </n-tab-pane>

      <!-- 整理任务 Tab -->
      <n-tab-pane name="tasks" tab="整理任务">
        <n-space vertical size="large">
          <n-space justify="end"><n-button v-bind="getButtonStyle('primary')" @click="openEditTask(-1)">创建整理任务</n-button></n-space>
          
          <draggable v-model="tasks" item-key="id" @end="saveConfig" class="card-grid" handle=".drag-handle">
            <template #item="{element: task, index: i}">
              <n-card bordered embedded class="task-card clickable-card" @click="openEditTask(i)">
                <template #header>
                  <n-space align="center" justify="space-between" style="width: 100%">
                    <n-space align="center">
                      <n-icon class="drag-handle" @click.stop style="color: var(--n-primary-color)"><DragIcon /></n-icon>
                      <b>{{ task.name }}</b>
                    </n-space>
                    
                    <n-space>
                      <!-- 实时监控快速切换 -->
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button 
                            circle 
                            quaternary 
                            size="small" 
                            :type="task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode) ? 'info' : 'default'"
                            @click.stop="toggleTaskMonitor(task, 'incremental')"
                          >
                            <template #icon><n-icon><BoltIcon /></n-icon></template>
                          </n-button>
                        </template>
                        实时监控: {{ (task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode)) ? '开启 (' + (task.incremental_mode || task.monitor_mode || 'realtime') + ')' : '关闭' }} (点击切换)
                      </n-tooltip>

                      <!-- 定时扫描快速切换 -->
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button 
                            circle 
                            quaternary 
                            size="small" 
                            :type="task.scheduler_enabled || task.monitor_mode === 'scheduled' ? 'warning' : 'default'"
                            @click.stop="toggleTaskMonitor(task, 'scheduler')"
                          >
                            <template #icon><n-icon><ScheduleIcon /></n-icon></template>
                          </n-button>
                        </template>
                        定时扫描: {{ (task.scheduler_enabled || task.monitor_mode === 'scheduled') ? '开启' : '关闭' }} (点击切换)
                      </n-tooltip>
                    </n-space>
                  </n-space>
                </template>
                <div class="p-disp">
                  <div :title="task.source_dir"><span>源目录</span><code>{{ task.source_dir }}</code></div>
                  <div :title="task.target_dir"><span>目标</span><code>{{ task.target_dir }}</code></div>
                  <div>
                    <span>重命名规则</span>
                    <n-tag size="tiny" :bordered="false" type="info" style="margin-top: 4px; background: var(--color-info-bg)">
                      {{ rules.find(r => r.id === task.rule_id)?.name || '未指定规则' }}
                    </n-tag>
                  </div>
                </div>
                <template #action>
                  <n-space justify="end" align="center" @click.stop>
                    <n-space>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('icon')" size="small" @click="duplicateTask(i)">
                            <template #icon><n-icon><CopyIcon /></n-icon></template>
                          </n-button>
                        </template>
                        复制任务
                      </n-tooltip>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="deleteTask(i)">
                            <template #icon><n-icon><DeleteIcon /></n-icon></template>
                          </n-button>
                        </template>
                        删除任务
                      </n-tooltip>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="requestRunTask(task)">
                            <template #icon><n-icon><PlayIcon /></n-icon></template>
                          </n-button>
                        </template>
                        立即开始整理任务
                      </n-tooltip>
                    </n-space>
                  </n-space>
                </template>
              </n-card>
            </template>
          </draggable>
        </n-space>
      </n-tab-pane>
    </n-tabs>

    <!-- Modals -->
    <RuleEditModal v-model:show="showRuleModal" :rule-data="editingRule" :is-new="editingRuleIndex===-1" @save="handleSaveRule" />
    <TaskEditModal v-model:show="showTaskModal" :task-data="editingTask" :is-new="editingTaskIndex===-1" :available-rules="rules" :api-base="API_BASE" @save="handleSaveTask" />
    <ExecutionLogModal v-model:show="showExecModal" :is-dry-run="isDryRun" :is-running="isRunning" :logs="execLogs" :scanning-status="scanningStatus" :target-dir="editingTask?.target_dir || ''" @commit="requestCommitBatch" />
  </div>
</template>

<style scoped>
.organizer-view { width: 100%; }
.header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.rule-card, .task-card { 
  height: 100%; 
  display: flex; 
  flex-direction: column; 
  border-radius: var(--card-border-radius, 12px) !important;
  border: 1px solid var(--app-border-light) !important;
  background: var(--app-surface-card) !important;
  transition: all 0.3s ease;
}
.clickable-card { cursor: pointer; }
.rule-card:hover, .task-card:hover {
  border-color: var(--n-primary-color) !important;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.drag-handle { cursor: grab; opacity: 0.6; transition: opacity 0.2s; }
.drag-handle:hover { opacity: 1; }
.rule-preview-mini { flex-grow: 1; padding: 12px 0; }
.rule-preview-mini .p-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.rule-preview-mini span { font-size: 10px; color: var(--n-text-color-3); font-weight: bold; text-transform: uppercase; }
.rule-preview-mini code { 
  font-size: 11px; 
  font-family: var(--code-font);
  color: var(--n-info-color); 
  background: var(--app-surface-inner); 
  padding: 4px 8px; 
  border-radius: var(--button-border-radius, 4px); 
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; 
  border: 1px solid var(--app-border-light);
}
.p-disp { flex-grow: 1; padding: 12px 0; display: flex; flex-direction: column; gap: 8px; }
.p-disp div { display: flex; flex-direction: column; gap: 2px; }
.p-disp span { font-size: 9px; color: var(--n-text-color-3); font-weight: bold; text-transform: uppercase; }
.p-disp code { 
  font-size: 11px; 
  font-family: var(--code-font);
  background: var(--app-surface-inner); 
  padding: 4px 8px; 
  border-radius: var(--button-border-radius, 4px); 
  color: var(--n-text-color-2); 
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; 
  border: 1px solid var(--app-border-light);
}
.mb-4 { margin-bottom: 16px; }
</style>
