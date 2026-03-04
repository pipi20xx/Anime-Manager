<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import {
  NModal, NProgress, NScrollbar, NList, NListItem, NIcon,
  NButton, NSpace, NText, NResult, NSelect
} from 'naive-ui'
import {
  SearchOutlined as SearchIcon,
  ErrorOutlineOutlined as ErrorIcon,
  DownloadOutlined as DownloadIcon,
  StopCircleOutlined as StopIcon,
  PlayCircleOutlineOutlined as StartIcon
} from '@vicons/material'

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
    // 不一定每一项都进 log，但既然用户反馈想看，我们就加进去
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
    nextTick(() => {
      scrollInst.value.scrollTo({ position: 'bottom', silent: true })
    })
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
    preset="card" 
    style="width: 700px" 
    :title="`搜寻补全: ${subTitle}`"
    :closable="true"
    :mask-closable="!isRunning"
  >
    <div class="fill-container">
      <div class="header-status">
        <n-space vertical size="large">
          <!-- 站点选择区 -->
          <n-space align="center" justify="space-between">
            <n-space align="center">
              <n-text depth="3">搜寻范围:</n-text>
              <n-select 
                v-model:value="selectedIndexerId" 
                :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
                size="small"
                style="width: 220px"
                :disabled="isRunning"
                :loading="indexers.length <= 1"
              />
            </n-space>
            
            <n-space>
              <n-button 
                v-if="!isRunning" 
                type="primary" 
                size="small" 
                @click="startProcess"
                :disabled="!subId"
              >
                <template #icon><n-icon><StartIcon /></n-icon></template>
                开始搜寻补全
              </n-button>
              <n-button v-else size="small" type="error" ghost @click="stopProcess">
                <template #icon><n-icon><StopIcon /></n-icon></template>
                停止执行
              </n-button>
            </n-space>
          </n-space>

          <n-space vertical size="small">
            <div class="status-text">{{ statusMsg }}</div>
            <n-progress 
              type="line" 
              :percentage="progress" 
              :processing="isRunning"
              :indicator-placement="'inside'"
            />
          </n-space>
        </n-space>
      </div>

      <div class="log-box">
        <n-scrollbar ref="scrollInst" style="max-height: 400px">
          <n-list size="small" hoverable clickable>
            <n-list-item v-for="(log, idx) in logs" :key="idx">
              <template #prefix>
                <n-icon v-if="log.type === 'hit'" color="#63e2b7"><DownloadIcon /></n-icon>
                <n-icon v-else-if="log.type === 'error'" style="color: var(--n-error-color)"><ErrorIcon /></n-icon>
                <n-icon v-else-if="log.type === 'process'" depth="3" style="opacity: 0.5"><SearchIcon /></n-icon>
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
        </n-scrollbar>
      </div>
      
      <div v-if="!isRunning && logs.length === 0" class="empty-results">
        <n-result status="404" title="就绪" description="请选择站点并点击开始补全" />
      </div>
    </div>

    <template #action>
      <n-space justify="end">
        <n-button @click="handleClose" :disabled="isRunning">关闭窗口</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.fill-container { display: flex; flex-direction: column; gap: 16px; }
.header-status { 
  background: var(--app-surface-card); 
  padding: 16px;
  border-radius: var(--card-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.log-box { 
  border: 1px solid var(--app-border-light);
  border-radius: var(--button-border-radius, 4px);
  background: var(--app-surface-inner);
}
.empty-results { padding: 40px 0; }
.status-text { font-size: 13px; font-weight: bold; }
</style>