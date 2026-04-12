<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NList, NListItem, NThing, NButton, NIcon, NDrawer, NDrawerContent, NTag, NSpace, NCard
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  MoreVertOutlined as MoreIcon,
  BoltOutlined as BoltIcon,
  AccessTimeOutlined as ScheduleIcon,
  PlayArrowOutlined as RunIcon,
  LinkOutlined as LinkIcon,
  ContentCopyOutlined as CopyIcon,
  DeleteOutlined as DeleteIcon
} from '@vicons/material'

import StrmTaskModal from '../../components/StrmTaskModal.vue'
import { useStrmGeneratorView } from '../../composables/views/useStrmGeneratorView'
import { useBackClose } from '../../composables/useBackClose'
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

useBackClose(showModal)

// 操作抽屉状态
const showActionDrawer = ref(false)
const currentTaskIndex = ref<number>(-1)
useBackClose(showActionDrawer)

const taskActions = [
  { key: 'duplicate', label: '复制任务', icon: CopyIcon },
  { key: 'delete', label: '删除任务', icon: DeleteIcon, danger: true },
]

const openTaskActions = (index: number, e: Event) => {
  e.stopPropagation()
  currentTaskIndex.value = index
  showActionDrawer.value = true
}

const handleAction = (key: string) => {
  showActionDrawer.value = false
  setTimeout(() => {
    if (key === 'duplicate') duplicateTask(currentTaskIndex.value)
    else if (key === 'delete') deleteTask(currentTaskIndex.value)
  }, 300)
}

onMounted(fetchTasks)
</script>

<template>
  <div class="strm-mobile">
    <div class="header-mobile">
      <h1>虚拟 STRM 库</h1>
      <n-button v-bind="getButtonStyle('icon')" @click="openEdit(-1)">
        <template #icon><n-icon><AddIcon /></n-icon></template>
      </n-button>
    </div>

    <div class="content-mobile">
       <div class="card-list">
         <n-card v-for="(task, index) in tasks" :key="task.id" class="mobile-card" size="small" @click="openEdit(index)">
           <div class="card-header">
             <div class="title-row">
               <n-icon size="20" class="link-icon"><LinkIcon /></n-icon>
               <span class="task-title">{{ task.name }}</span>
             </div>
             <div class="action-row">
                <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click.stop="runTask(task.id)" style="margin-right: 4px">
                   <template #icon><n-icon><RunIcon /></n-icon></template>
                </n-button>
                <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop="openTaskActions(index, $event)">
                  <template #icon><n-icon><MoreIcon /></n-icon></template>
                </n-button>
             </div>
           </div>
           
           <div class="path-details">
             <div class="path-row">
               <span class="label">源路径</span>
               <div class="val">{{ task.source_path || task.source_dir }}</div>
             </div>
             <div class="path-row">
               <span class="label">目标路径</span>
               <div class="val">{{ task.target_path || task.target_dir }}</div>
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
         </n-card>
       </div>
    </div>

    <!-- 配置组件 -->
    <StrmTaskModal
      v-model:show="showModal"
      :task-data="editingTask"
      :is-new="editingIndex === -1"
      :api-base="API_BASE"
      @save="handleSaveTask"
    />

    <!-- 操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="taskActions.length * 100 + 60" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content :title="tasks[currentTaskIndex]?.name || '任务操作'" closable :native-scrollbar="false">
        <div class="action-list">
          <div
            v-for="action in taskActions"
            :key="action.key"
            class="action-item"
            :class="{ danger: action.danger }"
            @click="handleAction(action.key)"
          >
            <div class="action-icon">
              <n-icon size="22"><component :is="action.icon" /></n-icon>
            </div>
            <span class="action-label">{{ action.label }}</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.strm-mobile {
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

.content-mobile {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px 16px;
}

.card-list { display: flex; flex-direction: column; gap: 12px; }
.mobile-card { border-radius: 12px; background: var(--app-surface-card); }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.title-row { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
.task-title { font-weight: 600; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.action-row { display: flex; align-items: center; flex-shrink: 0; }

.path-details { display: flex; flex-direction: column; gap: 8px; }
.path-row { display: flex; flex-direction: column; min-width: 0; }
.path-row .label { font-size: 10px; color: var(--text-tertiary); }
.path-row .val { 
  font-family: monospace; 
  background: var(--app-surface-input); 
  padding: 6px 8px; 
  border-radius: 6px; 
  font-size: 12px;
  word-break: break-all;
  line-height: 1.4;
}

.card-footer {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.link-icon { color: var(--n-primary-color); }

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
</style>