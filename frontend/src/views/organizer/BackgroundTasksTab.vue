<script setup lang="ts">
/**
 * BackgroundTasksTab — 后台任务
 *
 * 卡片网格展示后台任务列表
 * 操作: 查看日志 / 停止 / 删除
 */
import { ref } from 'vue'
import { organizerApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getStatusTag } from '@/utils/taskStatus'
import ExecutionLogModal from './ExecutionLogModal.vue'

defineOptions({ name: 'BackgroundTasksTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const props = defineProps<{
  backgroundTasks: any[]
}>()

const emit = defineEmits<{
  refresh: []
}>()

async function stopBackgroundTask(taskId: string) {
  try {
    const data = await organizerApi.stopBackgroundTask(taskId)
    if (data?.status === 'success') {
      success('已发送停止指令')
      emit('refresh')
    }
  } catch (e) {
    showError('停止失败')
  }
}

async function deleteBackgroundTask(taskId: string) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此后台任务记录吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    const data = await organizerApi.deleteBackgroundTask(taskId)
    if (data?.status === 'success') {
      success('任务记录已删除')
      emit('refresh')
    }
  } catch (e) {
    showError('删除失败')
  }
}

// --- 日志弹窗 ---
const showLogModal = ref(false)
const logTaskId = ref('')

function openLogModal(taskId: string) {
  logTaskId.value = taskId
  showLogModal.value = true
}
</script>

<template>
  <div>
    <v-row v-if="backgroundTasks.length > 0">
      <v-col v-for="bgTask in backgroundTasks" :key="bgTask.task_id" cols="12" sm="6" md="4" lg="3">
        <v-card class="glass-card item-card fill-height">
          <v-card-text class="pb-0">
            <div class="d-flex align-start justify-space-between mb-1">
              <div class="text-subtitle-2 font-weight-bold text-truncate flex-grow-1 mr-2">{{ bgTask.name || bgTask.task_id }}</div>
              <v-chip
                size="x-small"
                :color="getStatusTag(bgTask.status).color"
                variant="tonal"
              >
                {{ getStatusTag(bgTask.status).label }}
              </v-chip>
            </div>
            <div class="d-flex align-center ga-2 text-caption text-medium-emphasis">
              <v-icon size="12">mdi-identifier</v-icon>
              <span class="text-truncate">{{ bgTask.task_id }}</span>
              <v-spacer />
              <v-chip v-if="bgTask.dry_run" size="x-small" variant="tonal" color="warning">预览</v-chip>
            </div>
          </v-card-text>

          <v-card-text class="pt-0 pb-2">
            <div v-if="bgTask.total" class="mb-2">
              <div class="d-flex justify-space-between text-caption text-medium-emphasis mb-1">
                <span>进度</span>
                <span>{{ bgTask.processed ?? 0 }} / {{ bgTask.total }}</span>
              </div>
              <v-progress-linear
                :model-value="bgTask.total ? ((bgTask.processed ?? 0) / bgTask.total) * 100 : 0"
                color="primary"
                height="6"
                rounded="pill"
              />
            </div>
            <div v-if="bgTask.message" class="text-caption text-medium-emphasis text-truncate">
              {{ bgTask.message }}
            </div>
          </v-card-text>

          <v-divider />
          <v-card-actions class="pa-2">
            <v-btn v-if="bgTask.status === 'running'" size="small" variant="tonal" color="warning" prepend-icon="mdi-stop-outline" @click="stopBackgroundTask(bgTask.task_id)">停止</v-btn>
            <v-spacer />
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-text-box-outline" @click="openLogModal(bgTask.task_id)">日志</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteBackgroundTask(bgTask.task_id)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-cloud-off-outline</v-icon>
      <div class="text-h6 font-weight-medium">暂无后台任务</div>
      <div class="text-body-2 text-medium-emphasis mt-2">执行整理任务后会在这里显示</div>
    </div>

    <!-- 执行日志弹窗 -->
    <ExecutionLogModal v-model="showLogModal" :task-id="logTaskId" />
  </div>
</template>
