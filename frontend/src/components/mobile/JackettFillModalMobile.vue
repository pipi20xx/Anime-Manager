<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NModal, NProgress, NScrollbar, NList, NListItem, NIcon,
  NButton, NSpace, NText, NResult, NSelect
} from 'naive-ui'
import AppSelectField from '../AppSelectField.vue'
import {
  SearchOutlined as SearchIcon,
  ErrorOutlineOutlined as ErrorIcon,
  DownloadOutlined as DownloadIcon,
  StopCircleOutlined as StopIcon,
  PlayCircleOutlineOutlined as StartIcon,
  CloseOutlined as CloseIcon
} from '@vicons/material'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps({
  show: Boolean,
  subId: Number | null,
  subTitle: String,
  apiBase: String
})

const emit = defineEmits(['update:show', 'finish'])

const logs = ref<any[]>([])
const progress = ref(0)
const statusMsg = ref('就绪，请选择搜寻范围')
const isRunning = ref(false)
const pushedCount = ref(0)
const scrollInst = ref<any>(null)
let abortController: AbortController | null = null

const indexers = ref<any[]>([])
const selectedIndexerId = ref<string>("all")

const fetchIndexers = async () => {
  try {
    const res = await fetch(`${props.apiBase}/api/jackett/indexers`)
    const data = await res.json()
    indexers.value = [{ id: 'all', name: '所有站点 (全局)' }, ...data]
  } catch (e) {
    console.error('Failed to fetch indexers', e)
  }
}

const startProcess = async () => {
  if (!props.subId) return
  
  abortController = new AbortController()
  isRunning.value = true
  logs.value = []
  progress.value = 0
  pushedCount.value = 0
  statusMsg.value = '正在建立连接...'

  try {
    const url = `${props.apiBase}/api/subscriptions/${props.subId}/fill?indexer=${selectedIndexerId.value}`
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
        } catch (e) {
          console.error('Parse chunk error', e, line)
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

const stopProcess = () => {
  if (abortController) {
    abortController.abort()
  }
}

const handleUpdate = (data: any) => {
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
    const count = data.pushed !== undefined ? data.pushed : (data.message.match(/\d+/) || [0])[0]
    pushedCount.value = parseInt(count)
    logs.value.push({ type: 'finish', message: `搜索结束，共补全推送了 ${count} 个集数` })
  }
  
  if (scrollInst.value) {
    setTimeout(() => {
      scrollInst.value?.scrollTo({ position: 'bottom', silent: true })
    }, 50)
  }
}

const handleClose = () => {
  stopProcess()
  emit('update:show', false)
}

watch(() => props.show, (newVal) => {
  if (newVal) {
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
  <n-modal 
    :show="show" 
    @update:show="handleClose"
    :mask-closable="!isRunning"
    transform-origin="center"
  >
    <div class="mobile-fill-modal">
      <div class="mobile-header">
        <div class="header-title">
          <n-icon size="20"><SearchIcon /></n-icon>
          <span>搜寻补全</span>
        </div>
        <n-button 
          v-bind="getButtonStyle('icon')" 
          size="small" 
          @click="handleClose"
          :disabled="isRunning"
        >
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
      </div>

      <div class="mobile-subtitle" v-if="subTitle">{{ subTitle }}</div>

      <div class="mobile-content">
        <div class="control-section">
          <div class="control-row">
            <AppSelectField 
              v-model:value="selectedIndexerId" 
              label="搜寻范围"
              :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
              :disabled="isRunning"
              :loading="indexers.length <= 1"
              placeholder="选择站点"
            />
          </div>

          <div class="action-row">
            <n-button 
              v-if="!isRunning" 
              v-bind="getButtonStyle('primary')" 
              size="small" 
              @click="startProcess"
              :disabled="!subId"
              block
            >
              <template #icon><n-icon><StartIcon /></n-icon></template>
              开始搜寻补全
            </n-button>
            <n-button 
              v-else 
              v-bind="getButtonStyle('danger')" 
              size="small" 
              @click="stopProcess"
              block
            >
              <template #icon><n-icon><StopIcon /></n-icon></template>
              停止执行
            </n-button>
          </div>
        </div>

        <div class="progress-section">
          <div class="status-text">{{ statusMsg }}</div>
          <n-progress 
            type="line" 
            :percentage="progress" 
            :processing="isRunning"
            :indicator-placement="'inside'"
            :height="18"
          />
        </div>

        <div class="log-section">
          <div class="log-header">
            <span>执行日志</span>
            <span class="log-count">{{ logs.length }} 条</span>
          </div>
          <n-scrollbar ref="scrollInst" class="log-scroll">
            <n-list size="small" hoverable>
              <n-list-item v-for="(log, idx) in logs" :key="idx">
                <template #prefix>
                  <n-icon v-if="log.type === 'hit'" style="color: var(--n-primary-color)"><DownloadIcon /></n-icon>
                  <n-icon v-else-if="log.type === 'error'" style="color: var(--n-error-color)"><ErrorIcon /></n-icon>
                  <n-icon v-else-if="log.type === 'process'" depth="3" style="opacity: 0.6"><SearchIcon /></n-icon>
                  <n-icon v-else style="color: var(--n-info-color)"><SearchIcon /></n-icon>
                </template>
                <n-text 
                  :type="log.type === 'hit' ? 'success' : log.type === 'error' ? 'danger' : 'default'" 
                  :depth="log.type === 'process' ? 3 : undefined"
                  size="small"
                  :style="log.type === 'process' ? 'font-style: italic; font-size: 11px;' : ''"
                >
                  {{ log.message }}
                </n-text>
              </n-list-item>
            </n-list>
            <div v-if="logs.length === 0" class="empty-log">
              <n-result status="404" title="就绪" description="请选择站点并点击开始补全" size="small" />
            </div>
          </n-scrollbar>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.mobile-fill-modal {
  width: 100vw;
  height: 100vh;
  background: var(--app-surface-card);
  display: flex;
  flex-direction: column;
}

.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-spacing-md);
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface-inner);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-lg);
  font-weight: bold;
  color: var(--text-primary);
}

.mobile-subtitle {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  background: var(--app-surface-inner);
  border-bottom: 1px solid var(--app-border-light);
}

.mobile-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: var(--m-spacing-md);
  gap: var(--m-spacing-md);
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.control-row {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.control-label {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}

.action-row {
  margin-top: var(--m-spacing-xs);
}

.progress-section {
  background: var(--app-surface-inner);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  border: 1px solid var(--app-border-light);
}

.status-text {
  font-size: var(--m-text-sm);
  font-weight: bold;
  color: var(--text-primary);
  margin-bottom: var(--m-spacing-sm);
}

.log-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  border: 1px solid var(--app-border-light);
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  border-bottom: 1px solid var(--app-border-light);
  font-size: var(--m-text-sm);
  font-weight: bold;
  color: var(--text-secondary);
}

.log-count {
  font-weight: normal;
  color: var(--text-tertiary);
  font-size: var(--m-text-xs);
}

.log-scroll {
  flex: 1;
  padding: var(--m-spacing-sm);
}

.empty-log {
  padding: var(--m-spacing-xl) 0;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
