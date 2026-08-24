<script setup lang="ts">
/**
 * TaskCenterModal — 任务中心弹窗
 * 浏览所有任务历史，支持搜索、筛选、清理
 */
import { ref, watch } from 'vue'
import { taskHistoryApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getStatusTag } from '@/utils/taskStatus'
import ExecutionLogModal from './ExecutionLogModal.vue'

defineOptions({ name: 'TaskCenterModal' })

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// --- 日志弹窗联动 ---
const showLogModal = ref(false)
const logTaskId = ref('')

const taskCenterList = ref<any[]>([])
const taskCenterLoading = ref(false)
const taskCenterOffset = ref(0)
const taskCenterHasMore = ref(true)
const taskCenterModule = ref<string | undefined>(undefined)
const taskCenterSearch = ref('')

watch(() => props.modelValue, (val) => {
  if (val) {
    taskCenterList.value = []
    taskCenterOffset.value = 0
    taskCenterHasMore.value = true
    taskCenterModule.value = undefined
    taskCenterSearch.value = ''
    fetchTaskCenterList()
  }
})

async function fetchTaskCenterList() {
  taskCenterLoading.value = true
  try {
    const data = await taskHistoryApi.getTaskList({
      limit: 30,
      offset: taskCenterOffset.value,
      module: taskCenterModule.value,
      search: taskCenterSearch.value || undefined,
    })
    const items = Array.isArray(data) ? data : (data?.items || data?.data || [])
    taskCenterList.value = [...taskCenterList.value, ...items]
    taskCenterHasMore.value = items.length >= 30
    taskCenterOffset.value += items.length
  } catch (e) {
    // 静默
  } finally {
    taskCenterLoading.value = false
  }
}

function filterTaskCenter(module?: string) {
  taskCenterModule.value = module
  taskCenterList.value = []
  taskCenterOffset.value = 0
  taskCenterHasMore.value = true
  fetchTaskCenterList()
}

function searchTaskCenter() {
  taskCenterList.value = []
  taskCenterOffset.value = 0
  taskCenterHasMore.value = true
  fetchTaskCenterList()
}

function openLogModal(taskId: string) {
  logTaskId.value = taskId
  showLogModal.value = true
}

async function deleteTaskCenterRecord(taskId: string) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此任务记录吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await taskHistoryApi.deleteTask(taskId)
    success('已删除')
    taskCenterList.value = taskCenterList.value.filter((t: any) => t.task_id !== taskId)
  } catch (e) {
    showError('删除失败')
  }
}

async function cleanupTaskCenter() {
  const ok = await confirm({ title: '清理旧记录', content: '将清理超过 30 天或超过 500 条的旧记录，确认？', confirmColor: 'warning' })
  if (!ok) return
  try {
    await taskHistoryApi.cleanup({ max_records: 500, max_days: 30 })
    success('清理完成')
    taskCenterList.value = []
    taskCenterOffset.value = 0
    taskCenterHasMore.value = true
    fetchTaskCenterList()
  } catch (e) {
    showError('清理失败')
  }
}
</script>

<template>
  <v-dialog v-model="show" max-width="800" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="info">mdi-clipboard-list-outline</v-icon>
        任务中心
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="show = false" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 筛选 -->
        <div class="d-flex ga-2 mb-4 flex-wrap align-center">
          <v-text-field
            v-model="taskCenterSearch"
            label="搜索任务名称"
            density="compact"
            variant="outlined"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            class="org-search-field"
            @keyup.enter="searchTaskCenter"
            @click:clear="taskCenterSearch = ''; searchTaskCenter()"
          />
          <v-btn-toggle v-model="taskCenterModule" mandatory density="compact" variant="outlined" divided>
            <v-btn size="small" :value="undefined" @click="filterTaskCenter()">全部</v-btn>
            <v-btn size="small" value="整理" @click="filterTaskCenter('整理')">整理</v-btn>
            <v-btn size="small" value="STRM" @click="filterTaskCenter('STRM')">STRM</v-btn>
            <v-btn size="small" value="识别" @click="filterTaskCenter('识别')">识别</v-btn>
          </v-btn-toggle>
          <v-spacer />
          <v-btn variant="tonal" color="warning" size="small" prepend-icon="mdi-broom" @click="cleanupTaskCenter">清理旧记录</v-btn>
        </div>

        <v-skeleton-loader v-if="taskCenterLoading && taskCenterList.length === 0" type="list-item@5" />

        <div v-else-if="taskCenterList.length > 0">
          <div class="org-task-item" v-for="task in taskCenterList" :key="task.task_id">
            <div class="d-flex align-center">
              <div class="org-task-info flex-grow-1">
                <div class="d-flex align-center ga-2 mb-1">
                  <v-chip size="x-small" :color="getStatusTag(task.status).color" variant="tonal">
                    {{ getStatusTag(task.status).label }}
                  </v-chip>
                  <span class="text-subtitle-2 font-weight-medium">{{ task.name || task.task_id }}</span>
                </div>
                <div class="d-flex ga-3 text-caption text-medium-emphasis">
                  <span v-if="task.module">
                    <v-icon size="12" class="mr-1">mdi-tag-outline</v-icon>{{ task.module }}
                  </span>
                  <span v-if="task.created_at">
                    <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>{{ task.created_at }}
                  </span>
                </div>
              </div>
              <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-file-document-outline" class="flex-shrink-0 ml-auto" @click.stop="openLogModal(task.task_id)">日志</v-btn>
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" class="flex-shrink-0" @click.stop="deleteTaskCenterRecord(task.task_id)">删除</v-btn>
            </div>
          </div>

          <div v-if="taskCenterHasMore" class="text-center pa-4">
            <v-btn variant="tonal" :loading="taskCenterLoading" @click="fetchTaskCenterList">加载更多</v-btn>
          </div>
        </div>

        <div v-else class="text-center pa-8">
          <v-icon size="64" color="primary" class="mb-4">mdi-clipboard-list-outline</v-icon>
          <div class="text-h6 font-weight-medium">暂无任务记录</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="show = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 日志弹窗（放在外层，避免双滚动条） -->
  <ExecutionLogModal v-model="showLogModal" :task-id="logTaskId" />
</template>
