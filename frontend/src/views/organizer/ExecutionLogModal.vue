<script setup lang="ts">
/**
 * ExecutionLogModal — 执行日志弹窗
 *
 * 支持两种模式：
 * 1. 任务历史日志模式（taskId prop）: 查看后台任务的详细日志
 * 2. 流式整理模式（logs/isDryRun/isRunning props）: 文件浏览器的实时整理预览/执行
 */
import { ref, nextTick, watch, computed } from 'vue'
import { taskHistoryApi } from '@/api'
import { useNotification } from '@/composables'
import { getStatusTag } from '@/utils/taskStatus'

defineOptions({ name: 'ExecutionLogModal' })

const { error: showError } = useNotification()

const props = defineProps<{
  modelValue: boolean
  // 任务历史模式
  taskId?: string
  // 流式整理模式
  isDryRun?: boolean
  isRunning?: boolean
  logs?: any[]
  scanningStatus?: string
  targetDir?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  commit: []
}>()

// 任务历史模式状态
const logDetail = ref<any>(null)
const logLoading = ref(false)
const logContainerRef = ref<any>(null)

// 判断模式
const isStreamMode = computed(() => !!props.logs)
const title = computed(() => {
  if (isStreamMode.value) {
    return props.isDryRun ? '整理任务预览' : '正式执行日志'
  }
  return `执行日志 — ${props.taskId || ''}`
})

// --- 任务历史模式 ---
watch(() => props.modelValue, (val) => {
  if (val && props.taskId && !isStreamMode.value) {
    fetchLogDetail(props.taskId)
  }
})

async function fetchLogDetail(taskId: string) {
  logLoading.value = true
  logDetail.value = null
  try {
    const data = await taskHistoryApi.getTaskDetail(taskId)
    logDetail.value = data
  } catch (e) {
    logDetail.value = null
  } finally {
    logLoading.value = false
  }
}

function logLineClass(level: string): string {
  if (level === 'ERROR') return 'org-log-line org-log-error'
  if (level === 'WARN') return 'org-log-line org-log-warn'
  return 'org-log-line'
}

// --- 流式整理模式 ---
function getFileName(source: string | undefined): string {
  if (!source) return '未知文件'
  return String(source).split('/').pop() || source
}

function getTargetDisplay(log: any): string {
  if (log.message) return log.message
  if (log.target) return log.target.replace(props.targetDir || '', '')
  return log.reason || ''
}

function getStatusIcon(log: any): string {
  if (log.status === 'success') return 'mdi-check-circle'
  if (log.type === 'skip' || log.status === 'skipped') return 'mdi-skip-next'
  return 'mdi-alert-circle'
}

function getStatusColor(log: any): string {
  if (log.status === 'success') return 'success'
  if (log.type === 'skip' || log.status === 'skipped') return 'warning'
  return 'error'
}

function isStartOrInfo(log: any): boolean {
  return log.type === 'start' || log.type === 'info'
}

// 自动滚动到底部
watch(() => props.logs?.length, () => {
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
})
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="950" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="info">mdi-text-box-outline</v-icon>
        {{ title }}
        <v-spacer />
        <v-chip v-if="isStreamMode && isRunning" size="small" color="info" variant="tonal">
          <v-progress-circular indeterminate size="12" class="mr-1" />
          运行中
        </v-chip>
      </v-card-title>
      <v-divider />

      <!-- 流式整理模式 -->
      <v-card-text v-if="isStreamMode" class="pa-0" style="max-height: 65vh; overflow-y: auto" ref="logContainerRef">
        <v-card class="glass-card" variant="flat">
          <table class="stream-table">
            <thead>
              <tr>
                <th>源文件</th>
                <th width="60" class="text-center">状态</th>
                <th>目标相对路径 / 原因</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(log, i) in logs"
                :key="i"
                :class="{
                  'start-row': log.type === 'start',
                  'stream-info-row': log.type === 'info',
                }"
              >
                <td :colspan="isStartOrInfo(log) ? 3 : 1" class="source-cell">
                  <template v-if="isStartOrInfo(log)">
                    <v-icon
                      size="16"
                      :color="log.type === 'start' ? 'primary' : 'info'"
                      class="mr-2"
                    >
                      {{ log.type === 'start' ? 'mdi-play' : 'mdi-skip-next' }}
                    </v-icon>
                    <span :class="log.type === 'start' ? 'start-msg' : 'info-msg'">{{ log.message }}</span>
                  </template>
                  <template v-else>
                    {{ log.path || getFileName(log.source) }}
                  </template>
                </td>
                <td v-if="!isStartOrInfo(log)" class="text-center">
                  <v-icon size="18" :color="getStatusColor(log)">{{ getStatusIcon(log) }}</v-icon>
                </td>
                <td v-if="!isStartOrInfo(log)" class="target-cell">
                  {{ getTargetDisplay(log) }}
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 运行中进度 -->
          <div v-if="isRunning" class="pa-4">
            <v-progress-linear indeterminate color="primary" />
            <div v-if="scanningStatus" class="scanning-text mt-2">
              正在扫描: {{ scanningStatus }}
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="logs?.length === 0 && !isRunning" class="text-center text-medium-emphasis pa-8">
            <v-icon size="40" color="primary" class="mb-2">mdi-check-circle-outline</v-icon>
            <div class="text-body-2">没有需要处理的文件</div>
          </div>
        </div>
      </v-card-text>

      <!-- 任务历史模式 -->
      <v-card-text v-else class="pa-4">
        <v-skeleton-loader v-if="logLoading" type="list-item@8" />

        <template v-else-if="logDetail">
          <!-- 任务概要 -->
          <div class="org-log-summary mb-4">
            <div class="d-flex ga-3 flex-wrap">
              <div>
                <span class="text-caption text-medium-emphasis">模块</span>
                <div class="text-subtitle-2 font-weight-medium">{{ logDetail.module || '-' }}</div>
              </div>
              <div>
                <span class="text-caption text-medium-emphasis">名称</span>
                <div class="text-subtitle-2 font-weight-medium">{{ logDetail.name || '-' }}</div>
              </div>
              <div>
                <span class="text-caption text-medium-emphasis">状态</span>
                <div>
                  <v-chip size="small" :color="getStatusTag(logDetail.status).color" variant="tonal">
                    {{ getStatusTag(logDetail.status).label }}
                  </v-chip>
                </div>
              </div>
              <div v-if="logDetail.created_at">
                <span class="text-caption text-medium-emphasis">开始时间</span>
                <div class="text-subtitle-2">{{ logDetail.created_at }}</div>
              </div>
              <div v-if="logDetail.finished_at">
                <span class="text-caption text-medium-emphasis">完成时间</span>
                <div class="text-subtitle-2">{{ logDetail.finished_at }}</div>
              </div>
            </div>
            <div v-if="logDetail.stats" class="mt-3">
              <v-chip size="small" variant="tonal" color="success" class="mr-2">成功: {{ logDetail.stats.success ?? 0 }}</v-chip>
              <v-chip size="small" variant="tonal" color="info" class="mr-2">跳过: {{ logDetail.stats.skipped ?? 0 }}</v-chip>
              <v-chip size="small" variant="tonal" color="error">失败: {{ logDetail.stats.errors ?? 0 }}</v-chip>
            </div>
          </div>

          <!-- 日志行 -->
          <div class="org-log-container">
            <div v-if="logDetail.logs && logDetail.logs.length > 0">
              <div v-for="(line, i) in logDetail.logs" :key="i" :class="logLineClass(line.level || '')">
                <span v-if="line.timestamp" class="org-log-time">{{ line.timestamp }}</span>
                <span class="org-log-msg">{{ line.message || line }}</span>
              </div>
            </div>
            <div v-else class="text-center text-medium-emphasis pa-4">暂无日志</div>
          </div>
        </template>

        <div v-else class="text-center text-medium-emphasis pa-4">未找到任务记录</div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('update:modelValue', false)">关闭</v-btn>
        <v-btn v-if="!isStreamMode && taskId" variant="tonal" color="info" prepend-icon="mdi-refresh" @click="fetchLogDetail(taskId)">刷新</v-btn>
        <v-btn
          v-if="isStreamMode && !isRunning && isDryRun && (logs?.length ?? 0) > 0"
          color="warning"
          variant="flat"
          prepend-icon="mdi-check-all"
          @click="emit('commit')"
        >
          确认无误，开始正式执行
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 流式整理模式 */
.log-stream-box {
  border-radius: 0;
}

.stream-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.stream-table th {
  text-align: left;
  padding: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-surface), 0.8);
  font-weight: 600;
}

.stream-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.source-cell {
  font-family: monospace;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.target-cell {
  font-family: monospace;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.start-row {
  background: rgba(var(--v-theme-primary), 0.06);
}

.stream-info-row {
  background: rgba(var(--v-theme-info), 0.06);
}

.start-msg {
  color: rgb(var(--v-theme-primary));
  font-weight: bold;
  margin-left: 8px;
}

.info-msg {
  color: rgb(var(--v-theme-info));
  font-style: italic;
  margin-left: 8px;
}

.scanning-text {
  font-size: 11px;
  color: rgb(var(--v-theme-primary));
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
