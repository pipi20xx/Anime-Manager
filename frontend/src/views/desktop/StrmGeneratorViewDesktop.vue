<script setup lang="ts">
import { onMounted } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NEmpty, NTooltip
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  PlayArrowOutlined as RunIcon,
  DeleteOutlined as DeleteIcon,
  VideoLibraryOutlined as LinkIcon,
  ContentCopyOutlined as CopyIcon,
  BoltOutlined as BoltIcon,
  AccessTimeOutlined as ScheduleIcon
} from '@vicons/material'

import StrmTaskModal from '../../components/StrmTaskModal.vue'
import { useStrmGeneratorView } from '../../composables/views/useStrmGeneratorView'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  API_BASE,
  tasks,
  showModal,
  editingTask,
  editingIndex,
  fetchTasks,
  duplicateTask,
  openEdit,
  handleSaveTask,
  runTask,
  deleteTask,
  toggleTaskMonitor
} = useStrmGeneratorView()

onMounted(fetchTasks)
</script>

<template>
  <div class="strm-view">
    <div class="page-header">
      <div>
        <h1>虚拟 STRM 库</h1>
        <div class="subtitle">虚拟 STRM 生成器</div>
      </div>
      <n-button v-bind="getButtonStyle('primary')" size="large" @click="openEdit(-1)">
        新建任务
      </n-button>
    </div>

    <n-space vertical size="large">
      <n-card bordered>
        <template #header>
          <div class="card-title-box">
            <span class="card-title-text">STRM 任务管理</span>
          </div>
        </template>
        <div v-if="tasks.length > 0" class="task-grid">
          <n-card 
            v-for="(task, index) in tasks" 
            :key="task.id" 
            bordered 
            embedded 
            class="task-card clickable-card"
            @click="openEdit(index)"
          >
            <div class="task-header mb-2">
              <span class="task-name">{{ task.name }}</span>
              <n-space>
                <!-- 实时监控 -->
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

                <!-- 定时扫描 -->
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
            </div>
            <div class="path-info">
              <div class="l">源路径</div><div class="v" :title="task.source_path || task.source_dir">{{ task.source_path || task.source_dir }}</div>
              <div class="l mt-1">目标路径</div><div class="v" :title="task.target_path || task.target_dir">{{ task.target_path || task.target_dir }}</div>
            </div>
            <template #action>
              <n-space justify="end" @click.stop>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button v-bind="getButtonStyle('icon')" size="small" @click="duplicateTask(index)">
                      <template #icon><n-icon><CopyIcon /></n-icon></template>
                    </n-button>
                  </template>
                  复制任务
                </n-tooltip>

                <n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="deleteTask(index)">
                      <template #icon><n-icon><DeleteIcon /></n-icon></template>
                    </n-button>
                  </template>
                  删除任务
                </n-tooltip>

                <n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button circle type="primary" size="small" @click="runTask(task.id)">
                      <template #icon><n-icon><RunIcon /></n-icon></template>
                    </n-button>
                  </template>
                  立即运行任务
                </n-tooltip>
              </n-space>
            </template>
          </n-card>
        </div>
        <n-empty v-else description="暂无任务" />
      </n-card>
    </n-space>

    <!-- 配置组件 -->
    <StrmTaskModal 
      v-model:show="showModal"
      :task-data="editingTask"
      :is-new="editingIndex === -1"
      :api-base="API_BASE"
      @save="handleSaveTask"
    />
  </div>
</template>

<style scoped>
.strm-view { width: 100%; }
.header h1 { margin: 0; font-size: 24px; color: #fff; }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.task-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.task-card { height: 100%; transition: transform 0.2s; border: 1px solid #333; }
.clickable-card { cursor: pointer; }
.task-card:hover { transform: translateY(-4px); border-color: var(--n-primary-color); }
.task-header { display: flex; justify-content: space-between; align-items: center; }
.task-name { font-weight: bold; font-size: 15px; color: #eee; }
.path-info .l { font-size: 10px; color: var(--n-text-color-3); opacity: 0.6; }
.path-info .v { 
  font-size: 12px; 
  font-family: monospace; 
  color: var(--n-text-color-2); 
  background: var(--app-surface-inner); 
  padding: 4px 8px; 
  border-radius: var(--button-border-radius, 4px); 
  border: 1px solid var(--app-border-light);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; 
}
.mb-4 { margin-bottom: 16px; }
</style>
