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

const syncModeMap: Record<string, string> = {
  local: '本地文件扫描',
  tree_file: '目录树文件',
  cd2_api: 'CD2 API',
  webdav: 'WebDAV'
}

import StrmTaskModal from '../../components/StrmTaskModal.vue'
import AppGlassCard from '../../components/AppGlassCard.vue'
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

    <div v-if="tasks.length > 0" class="task-grid">
      <AppGlassCard
        v-for="(task, index) in tasks"
        :key="task.id"
        appearance-key="strm-task-card"
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
                  ghost
                  size="small"
                  :type="task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode) ? 'info' : 'primary'"
                  @click.stop="toggleTaskMonitor(task, 'incremental')"
                >
                  <template #icon><n-icon :color="task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode) ? undefined : 'var(--text-primary)'"><BoltIcon /></n-icon></template>
                </n-button>
              </template>
              实时监控: {{ (task.incremental_enabled || ['realtime', 'polling'].includes(task.monitor_mode)) ? '开启 (' + (task.incremental_mode || task.monitor_mode || 'realtime') + ')' : '关闭' }} (点击切换)
            </n-tooltip>

            <!-- 定时扫描 -->
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  circle
                  ghost
                  size="small"
                  :type="task.scheduler_enabled || task.monitor_mode === 'scheduled' ? 'warning' : 'primary'"
                  @click.stop="toggleTaskMonitor(task, 'scheduler')"
                >
                  <template #icon><n-icon :color="task.scheduler_enabled || task.monitor_mode === 'scheduled' ? undefined : 'var(--text-primary)'"><ScheduleIcon /></n-icon></template>
                </n-button>
              </template>
              定时扫描: {{ (task.scheduler_enabled || task.monitor_mode === 'scheduled') ? '开启' : '关闭' }} (点击切换)
            </n-tooltip>
          </n-space>
        </div>
        <div class="p-disp">
          <div class="p-row" :title="task.source_path || task.source_dir"><span class="p-label">源路径</span><div class="v">{{ task.source_path || task.source_dir }}</div></div>
          <div class="p-row" :title="task.target_path || task.target_dir"><span class="p-label">目标路径</span><div class="v">{{ task.target_path || task.target_dir }}</div></div>
          <div class="p-row">
            <span class="p-label">同步模式</span>
            <div class="v">{{ syncModeMap[task.sync_mode] || task.sync_mode || '本地文件扫描' }}</div>
          </div>
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
                <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="runTask(task.id)">
                  <template #icon><n-icon><RunIcon /></n-icon></template>
                </n-button>
              </template>
              立即运行任务
            </n-tooltip>
          </n-space>
        </template>
      </AppGlassCard>
    </div>
    <n-empty v-else description="暂无任务" />

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
.header h1 { margin: 0; font-size: var(--text-2xl); color: var(--text-primary); }
.subtitle { font-size: var(--text-sm); color: var(--n-primary-color); letter-spacing: var(--tracking-widest); font-weight: bold; }
.task-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.task-card { height: 100%; transition: transform var(--transition-fast); border: 1px solid var(--app-border-light); background: var(--app-surface-card-mixed); }
.clickable-card { cursor: pointer; }
.task-card:hover { transform: translateY(-4px); border-color: var(--n-primary-color); }
.task-header { display: flex; justify-content: space-between; align-items: center; }
.task-name { font-weight: bold; font-size: var(--text-xl); color: var(--text-secondary); }
.p-disp { flex-grow: 1; padding: var(--space-2) 0; display: flex; flex-direction: column; gap: var(--space-2); }
.p-disp .p-row { display: flex; align-items: center; gap: 8px; }
.p-disp .p-label { 
  font-size: var(--text-sm); 
  color: var(--text-tertiary); 
  font-weight: 600; 
  min-width: 70px;
  flex-shrink: 0;
}
.p-disp .v { 
  flex: 1;
  font-size: var(--text-sm); 
  font-family: var(--code-font);
  background: var(--app-surface-card-mixed); 
  padding: var(--space-1) var(--space-2); 
  border-radius: var(--card-border-radius, var(--button-border-radius, 4px)); 
  color: var(--text-secondary); 
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; 
  border: 1px solid var(--app-border-light);
}
.mb-4 { margin-bottom: 16px; }
</style>
