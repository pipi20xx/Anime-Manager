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

// --- 识别任务元数据展示 ---
function getEpInfo(stats: any): string {
  if (!stats || stats.category !== '剧集' || stats.season == null) return ''
  return `S${stats.season}E${stats.episode ?? '-'}`
}

function getRelatedIcon(status: string | undefined): string {
  if (status === 'success') return 'mdi-check-circle'
  if (status === 'skipped') return 'mdi-skip-next'
  return 'mdi-alert-circle'
}

function getRelatedColor(status: string | undefined): string {
  if (status === 'success') return '#1B8134'
  if (status === 'skipped') return '#E65100'
  return '#EF4444'
}

function copyText(text: string) {
  navigator.clipboard?.writeText(text).catch(() => {})
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

// 状态图标固定色值（圆形底 + 白色符号），不随白天/夜晚主题切换
function getStatusColor(log: any): string {
  if (log.status === 'success') return '#1B8134'
  if (log.type === 'skip' || log.status === 'skipped') return '#E65100'
  return '#EF4444'
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
        <table class="stream-table">
          <thead>
            <tr>
              <th>源文件</th>
              <th width="60" class="text-center">状态</th>
              <th>目标相对路径 / 原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(log, i) in logs" :key="i">
              <td :colspan="isStartOrInfo(log) ? 3 : 1" class="source-cell">
                <template v-if="isStartOrInfo(log)">
                  <v-icon size="16" class="mr-2">
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
              <!-- 计数：键存在才显示，避免识别等单文件任务出现无意义的 0 -->
              <v-chip v-if="logDetail.stats.success != null" size="small" variant="tonal" color="success" class="mr-2">成功: {{ logDetail.stats.success }}</v-chip>
              <v-chip v-if="logDetail.stats.skipped != null" size="small" variant="tonal" color="info" class="mr-2">跳过: {{ logDetail.stats.skipped }}</v-chip>
              <v-chip v-if="logDetail.stats.errors != null" size="small" variant="tonal" color="error" class="mr-2">失败: {{ logDetail.stats.errors }}</v-chip>
              <v-chip v-if="logDetail.stats.message" size="small" variant="tonal" color="warning">{{ logDetail.stats.message }}</v-chip>
            </div>

            <!-- 识别任务元数据：识别结果 + 目标路径 -->
            <div
              v-if="logDetail.stats && (logDetail.stats.title || logDetail.stats.target_path)"
              class="mt-3 recog-meta"
            >
              <div v-if="logDetail.stats.title" class="recog-meta-row">
                <span class="recog-meta-label">识别结果</span>
                <span class="recog-meta-value">
                  <span>{{ logDetail.stats.title }}</span>
                  <span v-if="getEpInfo(logDetail.stats)" class="recog-meta-gap">{{ getEpInfo(logDetail.stats) }}</span>
                  <a
                    v-if="logDetail.stats.tmdb_id"
                    :href="`https://www.themoviedb.org/${logDetail.stats.category === '电影' ? 'movie' : 'tv'}/${logDetail.stats.tmdb_id}`"
                    target="_blank"
                    class="recog-meta-gap"
                  >TMDB: {{ logDetail.stats.tmdb_id }}</a>
                </span>
              </div>
              <div v-if="logDetail.stats.target_path" class="recog-meta-row">
                <span class="recog-meta-label">目标路径</span>
                <span class="recog-meta-value recog-meta-path" :title="logDetail.stats.target_path" @click="copyText(logDetail.stats.target_path)">
                  {{ logDetail.stats.target_path }}
                  <v-icon size="12" class="ml-1">mdi-content-copy</v-icon>
                </span>
              </div>
            </div>

            <!-- 随行文件（字幕/音轨）去向 -->
            <div v-if="logDetail.stats?.related_files?.length" class="mt-3">
              <div class="related-files-title">
                <v-icon size="14" class="mr-1">mdi-paperclip</v-icon>随行文件 ({{ logDetail.stats.related_files.length }})
              </div>
              <div v-for="(rf, i) in logDetail.stats.related_files" :key="i" class="related-file-item">
                <div class="related-file-head">
                  <v-icon size="14" :color="getRelatedColor(rf.status)">{{ getRelatedIcon(rf.status) }}</v-icon>
                  <span class="related-file-name">{{ rf.filename }}</span>
                </div>
                <div
                  v-if="rf.target_path"
                  class="related-file-target"
                  :title="rf.target_path"
                  @click="copyText(rf.target_path)"
                >→ {{ rf.target_path }}</div>
              </div>
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
          variant="tonal" color="warning"
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
/* 识别任务元数据 */
.recog-meta {
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recog-meta-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.recog-meta-label {
  flex-shrink: 0;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
}

.recog-meta-value {
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
  min-width: 0;
}

.recog-meta-gap {
  margin-left: 8px;
}

.recog-meta-path {
  cursor: pointer;
}

.recog-meta-path:hover {
  color: rgb(var(--v-theme-primary));
}

/* 随行文件（字幕/音轨）：文件名一行、目标路径一行 */
.related-files-title {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
  margin-bottom: 4px;
}

.related-file-item {
  padding: 2px 0 2px 6px;
}

.related-file-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.related-file-name {
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
}

.related-file-target {
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
  padding-left: 22px;
  cursor: pointer;
}

.related-file-target:hover {
  color: rgb(var(--v-theme-primary));
}

/* 流式整理模式 */
.stream-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.stream-table th {
  text-align: left;
  padding: 12px;
  white-space: nowrap;
  color: rgb(var(--v-theme-on-surface));
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  font-weight: 600;
}

.stream-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  color: rgb(var(--v-theme-on-surface));
}

.source-cell {
  font-family: monospace;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
}

.target-cell {
  font-family: monospace;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
}

.start-msg {
  font-weight: bold;
  margin-left: 8px;
}

.info-msg {
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
