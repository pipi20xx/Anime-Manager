<script setup lang="ts">
/**
 * TasksTab — 整理任务
 *
 * 卡片网格展示整理任务列表
 * 操作: 添加 / 编辑 / 复制 / 删除 / 执行 / 切换监控
 */
import { ref, reactive } from 'vue'
import { organizerApi } from '@/api'
import { useNotification, useConfirm, useDragSort } from '@/composables'
import TaskEditModal from './TaskEditModal.vue'

defineOptions({ name: 'TasksTab' })

const { success, error: showError, info, warning } = useNotification()
const { confirm } = useConfirm()

const props = defineProps<{
  rules: any[]
  tasks: any[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:tasks': [tasks: any[]]
  save: []
}>()

// 拖拽排序（不可变模式：通过 getter 获取列表，回调返回新数组）
const { dragIndex, dragOverIndex, onDragStart, onDragOver, onDragEnd } = useDragSort(
  () => props.tasks,
  {
    onSort: (newList) => {
      emit('update:tasks', newList!)
      emit('save')
    },
  },
)

// --- 任务编辑弹窗 ---
const showTaskModal = ref(false)
const isNewTask = ref(false)
const editingTaskIndex = ref(-1)

const taskForm = reactive({
  id: '',
  name: '',
  rule_id: '',
  source_dir: '',
  target_dir: '',
  action_type: 'move',
  overwrite_mode: false,
  anime_priority: true,
  incremental_enabled: false,
  incremental_mode: 'realtime',
  monitor_interval: 10,
  scheduler_enabled: false,
  scheduler_interval: 3600,
  process_interval: 0,
  skip_rate_limit: false,
  skip_rate_limit_types: [] as string[],
  ignore_file_regex: [] as string[],
  ignore_dir_regex: [] as string[],
  trigger_strm: false,
  ignore_history: false,
  retry_failed: true,
  check_emby_exists: false,
  calculate_hash: false,
  clean_empty_dir: false,
  series_fingerprint: true,
})

function resetTaskForm() {
  taskForm.id = ''
  taskForm.name = ''
  taskForm.rule_id = ''
  taskForm.source_dir = ''
  taskForm.target_dir = ''
  taskForm.action_type = 'move'
  taskForm.overwrite_mode = false
  taskForm.anime_priority = true
  taskForm.incremental_enabled = false
  taskForm.incremental_mode = 'realtime'
  taskForm.monitor_interval = 10
  taskForm.scheduler_enabled = false
  taskForm.scheduler_interval = 3600
  taskForm.process_interval = 0
  taskForm.skip_rate_limit = false
  taskForm.skip_rate_limit_types = []
  taskForm.ignore_file_regex = []
  taskForm.ignore_dir_regex = []
  taskForm.trigger_strm = false
  taskForm.ignore_history = false
  taskForm.retry_failed = true
  taskForm.check_emby_exists = false
  taskForm.calculate_hash = false
  taskForm.clean_empty_dir = false
  taskForm.series_fingerprint = true
}

function openAddTask() {
  resetTaskForm()
  taskForm.id = 'task_' + Date.now()
  isNewTask.value = true
  editingTaskIndex.value = -1
  showTaskModal.value = true
}

function openEditTask(index: number) {
  resetTaskForm()
  isNewTask.value = false
  editingTaskIndex.value = index
  const rawData = JSON.parse(JSON.stringify(props.tasks[index]))

  // 处理旧版 monitor_mode 字段迁移
  if (rawData.monitor_mode) {
    if (rawData.monitor_mode === 'realtime') {
      rawData.incremental_enabled = true
      rawData.incremental_mode = 'realtime'
    } else if (rawData.monitor_mode === 'polling') {
      rawData.incremental_enabled = true
      rawData.incremental_mode = 'polling'
    } else if (rawData.monitor_mode === 'scheduled') {
      rawData.scheduler_enabled = true
    }
    delete rawData.monitor_mode
  }

  // 确保默认值
  if (rawData.incremental_enabled === undefined) rawData.incremental_enabled = false
  if (rawData.incremental_mode === undefined) rawData.incremental_mode = 'realtime'
  if (rawData.scheduler_enabled === undefined) rawData.scheduler_enabled = false
  if (rawData.scheduler_interval === undefined) rawData.scheduler_interval = 3600
  if (rawData.monitor_interval === undefined) rawData.monitor_interval = 10
  if (rawData.skip_rate_limit === undefined) rawData.skip_rate_limit = false
  if (rawData.skip_rate_limit_types === undefined) rawData.skip_rate_limit_types = []
  if (rawData.ignore_file_regex === undefined) rawData.ignore_file_regex = []
  if (rawData.ignore_dir_regex === undefined) rawData.ignore_dir_regex = []
  if (rawData.anime_priority === undefined) rawData.anime_priority = true
  if (rawData.retry_failed === undefined) rawData.retry_failed = true
  if (rawData.series_fingerprint === undefined) rawData.series_fingerprint = true

  Object.assign(taskForm, rawData)
  showTaskModal.value = true
}

async function handleSaveTask() {
  if (!taskForm.name) {
    warning('请输入任务名称')
    return
  }
  const payload = { ...taskForm }
  const newTasks = [...props.tasks]

  if (isNewTask.value) {
    newTasks.push(payload)
  } else {
    newTasks[editingTaskIndex.value] = payload
  }
  emit('update:tasks', newTasks)
  showTaskModal.value = false
  emit('save')
}

// --- 任务快捷操作 ---
async function deleteTask(index: number) {
  const taskName = props.tasks[index]?.name || ''
  const ok = await confirm({ title: '确认删除任务', content: `确定要删除任务 "${taskName}" 吗？`, confirmColor: 'error' })
  if (!ok) return
  const newTasks = [...props.tasks]
  newTasks.splice(index, 1)
  emit('update:tasks', newTasks)
  emit('save')
}

async function duplicateTask(index: number) {
  const newTask = { ...props.tasks[index] }
  newTask.id = 'task_' + Date.now()
  newTask.name = newTask.name + ' (副本)'
  const newTasks = [...props.tasks]
  newTasks.splice(index + 1, 0, newTask)
  emit('update:tasks', newTasks)
  emit('save')
  success('任务已复制')
}

const actionTypeMap: Record<string, string> = {
  move: '移动',
  copy: '复制',
  symlink: '符号链接',
  hardlink: '硬链接',
  hash_only: '仅哈希',
}

function actionTypeLabel(type: string) {
  return actionTypeMap[type] || type || '移动'
}

async function toggleTaskMonitor(task: any, type: 'incremental' | 'scheduler') {
  if (type === 'incremental') {
    task.incremental_enabled = !task.incremental_enabled
    if (task.incremental_enabled && !task.incremental_mode) task.incremental_mode = 'realtime'
    info(`${task.name} 实时监控已${task.incremental_enabled ? '开启' : '关闭'}`)
  } else {
    task.scheduler_enabled = !task.scheduler_enabled
    if (task.scheduler_enabled && !task.scheduler_interval) task.scheduler_interval = 3600
    info(`${task.name} 定时扫描已${task.scheduler_enabled ? '开启' : '关闭'}`)
  }
  // 直接调 API 保存，不触发全量 reload
  try {
    await organizerApi.saveConfig({
      rename_rules: props.rules,
      organize_tasks: props.tasks,
    })
  } catch (e) {
    showError('保存失败')
  }
}

async function runTask(task: any, dryRun = true) {
  try {
    const data = await organizerApi.startBackground(task, { dry_run: dryRun })
    if (data?.status === 'success') {
      success(dryRun ? '预览任务已启动' : '任务已在后台启动')
    } else {
      showError('启动失败: ' + (data?.message || '未知错误'))
    }
  } catch (e: any) {
    showError('启动失败: ' + e.message)
  }
}

async function requestRunTask(task: any) {
  const ok = await confirm({
    title: '启动整理任务',
    content: `您希望如何运行任务 "${task.name}"？`,
    confirmText: '后台静默执行',
    cancelText: '预览并手动执行',
  })
  if (ok) {
    runTask(task, false)
  } else {
    runTask(task, true)
  }
}
</script>

<template>
  <div>
    <div class="d-flex justify-end mb-4">
      <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openAddTask">添加任务</v-btn>
    </div>

    <v-row v-if="loading">
      <v-col v-for="i in 3" :key="i" cols="12" sm="6" md="4">
        <v-skeleton-loader type="card" />
      </v-col>
    </v-row>

    <v-row v-else-if="tasks.length > 0">
      <v-col
        v-for="(task, index) in tasks"
        :key="task.id"
        cols="12" sm="6" md="4"
        draggable="true"
        :class="{ 'drag-sorting': dragIndex === index, 'drag-over': dragOverIndex === index }"
        @dragstart="onDragStart(index, $event)"
        @dragover="onDragOver(index, $event)"
        @dragend="onDragEnd"
      >
        <v-card class="glass-card manage-card cursor-pointer" :class="{ 'hover-lift': dragIndex === -1 }" @click="dragIndex === -1 && openEditTask(index)">
          <!-- 标题行 -->
          <div class="manage-card__header">
            <div class="manage-card__title">{{ task.name }}</div>
            <v-chip size="small" variant="tonal" color="info" class="manage-card__badge">{{ actionTypeLabel(task.action_type) }}</v-chip>
          </div>

          <!-- 信息区 -->
          <div class="manage-card__body">
            <div class="manage-card__info">
              <v-icon size="14" class="mr-1">mdi-folder-outline</v-icon>
              <span class="manage-card__info-label">源</span>
              <span class="manage-card__info-value" :title="task.source_dir">{{ task.source_dir || '-' }}</span>
            </div>
            <div class="manage-card__info">
              <v-icon size="14" class="mr-1">mdi-folder-arrow-right-outline</v-icon>
              <span class="manage-card__info-label">目标</span>
              <span class="manage-card__info-value" :title="task.target_dir">{{ task.target_dir || '-' }}</span>
            </div>

            <div class="manage-card__tags">
              <v-chip
                size="small"
                :color="task.incremental_enabled ? 'info' : 'default'"
                variant="tonal"
                class="cursor-pointer"
                @click.stop="toggleTaskMonitor(task, 'incremental')"
              >
                <v-icon start size="14">{{ task.incremental_enabled ? 'mdi-eye-outline' : 'mdi-eye-off-outline' }}</v-icon>
                实时监控
              </v-chip>
              <v-chip
                size="small"
                :color="task.scheduler_enabled ? 'info' : 'default'"
                variant="tonal"
                class="cursor-pointer"
                @click.stop="toggleTaskMonitor(task, 'scheduler')"
              >
                <v-icon start size="14">mdi-clock-outline</v-icon>
                定时扫描
              </v-chip>
            </div>
          </div>

          <v-divider />
          <v-card-actions class="manage-card__actions">
            <v-spacer />
            <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play-outline" @click.stop="requestRunTask(task)">执行</v-btn>
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil-outline" @click.stop="openEditTask(index)">编辑</v-btn>
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-content-copy" @click.stop="duplicateTask(index)">复制</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteTask(index)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-folder-sync-outline</v-icon>
      <div class="text-h6 font-weight-medium">暂无整理任务</div>
      <div class="text-body-2 text-medium-emphasis mt-2">点击"添加任务"创建第一个整理任务</div>
    </div>

    <!-- 任务编辑弹窗 -->
    <TaskEditModal
      v-model="showTaskModal"
      :is-new="isNewTask"
      :task-form="taskForm"
      :rules="rules"
      @save="handleSaveTask"
    />
  </div>
</template>
