<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { 
  NModal, NScrollbar, NIcon, NProgress, NSpace, NButton
} from 'naive-ui'
import {
  CheckCircleOutlined as SuccessIcon,
  ErrorOutlineOutlined as ErrorIcon,
  FastForwardOutlined as SkipIcon,
  PlayArrowOutlined as PlayIcon
} from '@vicons/material'

const props = defineProps<{
  show: boolean
  isDryRun: boolean
  isRunning: boolean
  logs: any[]
  targetDir: string
  scanningStatus: string // 新增：正在扫描的路径
}>()

const emit = defineEmits(['update:show', 'commit'])

const logContainerRef = ref<any>(null)

const getFileName = (source: string | undefined) => {
  if (!source) return '未知文件'
  return String(source).split('/').pop() || source
}

watch(() => props.logs.length, () => {
  nextTick(() => {
    if (logContainerRef.value?.contentRef) {
      logContainerRef.value.contentRef.scrollTop = logContainerRef.value.contentRef.scrollHeight
    }
  })
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 950px; max-width: 95vw; max-height: 90vh; display: flex; flex-direction: column;" 
    :title="isDryRun ? '整理任务预览' : '正式执行日志'"
    :segmented="{
      content: true,
      footer: 'soft'
    }"
  >
    <div class="log-stream-box">
      <n-scrollbar style="max-height: calc(90vh - 220px)" ref="logContainerRef">
        <table class="stream-table">
          <thead>
            <tr>
              <th>源文件</th>
              <th width="60" class="text-center">状态</th>
              <th>目标相对路径 / 原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(log, i) in logs" :key="i" :class="{'start-row': log.type === 'start', 'info-row': log.type === 'info'}">
              <td class="mf" :colspan="log.type === 'start' || log.type === 'info' ? 3 : 1">
                <template v-if="log.type === 'start' || log.type === 'info'">
                  <n-icon :style="{ color: log.type === 'start' ? 'var(--n-primary-color)' : 'var(--n-info-color)' }">
                    <component :is="log.type === 'start' ? PlayIcon : SkipIcon" />
                  </n-icon> 
                  <span :class="log.type === 'start' ? 'start-msg' : 'info-msg'">{{ log.message }}</span>
                </template>
                <template v-else>
                  {{ log.path || getFileName(log.source) }}
                </template>
              </td>
              <td class="text-center" v-if="log.type !== 'start' && log.type !== 'info'">
                <template v-if="log.type !== 'start'">
                  <n-icon v-if="log.status==='success'" style="color: var(--n-primary-color)"><SuccessIcon /></n-icon>
                  <n-icon v-else-if="log.type==='skip' || log.status==='skipped'" style="color: var(--n-warning-color)"><SkipIcon /></n-icon>
                  <n-icon v-else style="color: var(--n-error-color)"><ErrorIcon /></n-icon>
                </template>
              </td>
              <td class="mt" v-if="log.type !== 'start' && log.type !== 'info'">
                <template v-if="log.type !== 'start'">
                  {{ log.message || (log.target ? log.target.replace(targetDir, '') : log.reason) }}
                </template>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="isRunning" class="lb-pulse">
          <n-progress type="line" processing :show-indicator="false" status="info" />
          <div class="scanning-text" v-if="scanningStatus">
            正在扫描: {{ scanningStatus }}
          </div>
        </div>
      </n-scrollbar>
    </div>
    <template #action>
      <n-space justify="end" style="width: 100%">
        <n-button size="large" @click="emit('update:show', false)">关闭</n-button>
        <n-button 
          v-if="!isRunning && isDryRun && logs.length > 0" 
          type="warning" 
          size="large"
          @click="emit('commit')"
        >
          确认无误，开始正式执行
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.log-stream-box { 
  background: var(--app-surface-inner); 
  border-radius: var(--button-border-radius, 4px); 
  border: 1px solid var(--app-border-light); 
}
.stream-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.stream-table th { 
  text-align: left; padding: 12px; 
  color: var(--n-text-color-3); 
  border-bottom: 1px solid var(--app-border-medium); 
  background: var(--app-surface-subtle); 
}
.stream-table td { padding: 10px 12px; border-bottom: 1px solid var(--app-border-light); color: var(--n-text-color-2); }
.mf { font-family: monospace; color: var(--n-text-color-1); }
.mt { font-family: monospace; color: var(--n-text-color-3); }
.start-row { background: var(--primary-subtle); }
.info-row { background: var(--info-subtle); }
.start-msg { color: var(--n-primary-color); font-weight: bold; margin-left: 8px; }
.info-msg { color: var(--n-info-color); font-style: italic; margin-left: 8px; }
.lb-pulse { padding: 16px; }
.scanning-text { font-size: 11px; color: var(--n-primary-color); margin-top: 8px; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.text-center { text-align: center; }
</style>