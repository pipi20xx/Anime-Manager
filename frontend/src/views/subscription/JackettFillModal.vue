<script setup lang="ts">
/**
 * JackettFillModal — 搜寻补全弹窗
 *
 * 对标旧前端 JackettFillModal：
 * - 站点选择器（Jackett Indexers）
 * - SSE 流式日志实时显示
 * - 进度条 + 状态信息
 * - 开始/停止控制
 */
import { ref, watch, nextTick } from 'vue'
import { subscriptionApi, clientsApi } from '@/api'
import { useNotification } from '@/composables'

const props = defineProps<{
  show: boolean
  subId: number | null | undefined
  subTitle: string
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'finish'): void
}>()

const { success, error: showError } = useNotification()

const logs = ref<{ type: string; message: string }[]>([])
const progress = ref(0)
const statusMsg = ref('就绪，请选择搜寻范围')
const isRunning = ref(false)
const pushedCount = ref(0)
const logContainerRef = ref<HTMLElement | null>(null)

// 站点列表
const indexers = ref<{ id: string; name: string }[]>([])
const selectedIndexerId = ref('all')

let abortController: AbortController | null = null

async function fetchIndexers() {
  try {
    const data = await clientsApi.getJackettIndexers()
    indexers.value = [{ id: 'all', name: '所有站点 (全局)' }, ...(data || [])]
  } catch { /* Jackett 可能未配置 */ }
}

async function startProcess() {
  if (!props.subId) return

  abortController = new AbortController()
  isRunning.value = true
  logs.value = []
  progress.value = 0
  pushedCount.value = 0
  statusMsg.value = '正在建立连接...'

  try {
    // 使用 fetch + ReadableStream 实现 SSE
    const apiBase = (import.meta.env.VITE_API_BASE as string) || ''
    const url = `${apiBase}/api/subscriptions/${props.subId}/fill?indexer=${selectedIndexerId.value}`
    const response = await fetch(url, {
      method: 'POST',
      signal: abortController.signal
    })

    if (!response.body) throw new Error('ReadableStream not supported')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          handleUpdate(data)
        } catch {
          // 忽略解析错误
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      logs.value.push({ type: 'warn', message: '操作已被用户中断' })
    } else {
      logs.value.push({ type: 'error', message: `连接中断: ${err.message}` })
    }
  } finally {
    isRunning.value = false
    statusMsg.value = pushedCount.value > 0 ? `补全结束，共推送 ${pushedCount.value} 个` : '搜寻结束'
    abortController = null
    emit('finish')
  }
}

function stopProcess() {
  if (abortController) abortController.abort()
}

function handleUpdate(data: any) {
  if (data.type === 'start') {
    statusMsg.value = data.message
  } else if (data.type === 'info') {
    logs.value.push({ type: 'info', message: data.message })
    statusMsg.value = data.message
  } else if (data.type === 'process') {
    progress.value = Math.round((data.index / data.total) * 100)
    statusMsg.value = `正在分析: ${data.title}`
    logs.value.push({ type: 'process', message: `正在分析: ${data.title}` })
  } else if (data.type === 'hit') {
    logs.value.push({ type: 'hit', message: data.message })
  } else if (data.type === 'warn') {
    logs.value.push({ type: 'warn', message: data.message })
  } else if (data.type === 'error') {
    logs.value.push({ type: 'error', message: data.message })
    statusMsg.value = '发生错误'
  } else if (data.type === 'finish') {
    progress.value = 100
    const count = data.pushed !== undefined ? data.pushed : (data.message?.match(/\d+/) || [0])[0]
    pushedCount.value = parseInt(count)
    logs.value.push({ type: 'finish', message: `搜索结束，共补全推送了 ${count} 个集数` })
  }

  // 自动滚动到底部
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}

function handleClose() {
  stopProcess()
  emit('update:show', false)
}

function getLogColor(type: string): string {
  switch (type) {
    case 'hit': return 'success'
    case 'error': return 'error'
    case 'warn': return 'warning'
    case 'finish': return 'primary'
    default: return 'default'
  }
}

function getLogIcon(type: string): string {
  switch (type) {
    case 'hit': return 'mdi-download'
    case 'error': return 'mdi-alert-circle-outline'
    case 'warn': return 'mdi-alert-outline'
    case 'process': return 'mdi-magnify'
    case 'finish': return 'mdi-check-circle-outline'
    default: return 'mdi-information-outline'
  }
}

watch(() => props.show, (val) => {
  if (val) {
    logs.value = []
    progress.value = 0
    pushedCount.value = 0
    isRunning.value = false
    statusMsg.value = '就绪，请选择搜寻范围'
    if (indexers.value.length === 0) fetchIndexers()
  }
})
</script>

<template>
  <v-dialog :model-value="show" max-width="700" scrollable @update:model-value="handleClose">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-magnify</v-icon>
        搜寻补全: {{ subTitle }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" :disabled="isRunning" @click="handleClose" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 控制区 -->
        <div class="fill-control-panel mb-4">
          <div class="d-flex align-center justify-space-between mb-3">
            <v-select
              v-model="selectedIndexerId"
              label="搜寻范围"
              :items="indexers.map(i => ({ title: i.name, value: i.id }))"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 260px;"
              :disabled="isRunning"
            />
            <div class="d-flex ga-2">
              <v-btn
                v-if="!isRunning"
                color="primary"
                variant="flat"
                size="small"
                prepend-icon="mdi-play"
                :disabled="!subId"
                @click="startProcess"
              >开始搜寻补全</v-btn>
              <v-btn
                v-else
                color="error"
                variant="tonal"
                size="small"
                prepend-icon="mdi-stop"
                @click="stopProcess"
              >停止执行</v-btn>
            </div>
          </div>

          <div class="text-body-2 font-weight-bold mb-1">{{ statusMsg }}</div>
          <v-progress-linear
            :model-value="progress"
            :color="isRunning ? 'primary' : 'success'"
            height="8"
            rounded="pill"
            :stream="isRunning"
          />
        </div>

        <!-- 日志区 -->
        <div v-if="logs.length > 0" class="fill-log-box" ref="logContainerRef">
          <div v-for="(log, idx) in logs" :key="idx" class="fill-log-item">
            <v-icon size="14" :color="getLogColor(log.type)" class="mr-2 flex-shrink-0">
              {{ getLogIcon(log.type) }}
            </v-icon>
            <span
              :class="[
                'text-body-2',
                log.type === 'process' ? 'font-italic text-medium-emphasis' : '',
                log.type === 'hit' ? 'text-success' : '',
                log.type === 'error' ? 'text-error' : '',
                log.type === 'warn' ? 'text-warning' : '',
                log.type === 'finish' ? 'text-primary font-weight-bold' : ''
              ]"
            >{{ log.message }}</span>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else class="text-center pa-8">
          <v-icon size="48" color="primary" class="mb-3">mdi-magnify</v-icon>
          <div class="text-body-1 text-medium-emphasis">请选择站点并点击开始补全</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" :disabled="isRunning" @click="handleClose">关闭窗口</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.fill-control-panel {
  background: rgba(var(--v-theme-on-surface), 0.04);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.fill-log-box {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.02);
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
}
.fill-log-item {
  display: flex;
  align-items: flex-start;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}
.fill-log-item:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.font-italic {
  font-style: italic;
  font-size: 12px !important;
}
</style>
