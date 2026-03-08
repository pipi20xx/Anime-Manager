<script setup lang="ts">
import { watch } from 'vue'
import { 
  NModal, NCard, NSpace, NButton, NIcon, NTag, NSwitch, NVirtualList, NSelect, NSpin
} from 'naive-ui'
import {
  TerminalRound as TerminalIcon,
  PauseCircleRound as PauseIcon,
  PlayCircleRound as PlayIcon,
  DeleteSweepRound as ClearIcon,
  VerticalAlignBottomRound as ScrollIcon,
  CloseRound as CloseIcon,
  OpenInNewRound as OpenIcon
} from '@vicons/material'
import { useLogConsole } from '../../composables/components/useLogConsole'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])

const {
  consoleLogs,
  isPaused,
  autoScroll,
  virtualListInst,
  socketStatus,
  logDates,
  selectedDate,
  isLoadingHistory,
  isInitialLoading,
  hasMore,
  logSource,
  handleSourceChange,
  handleDateChange,
  loadMoreHistory,
  scrollToTop,
  clearConsole,
  openFullLog
} = useLogConsole()

const close = () => {
  emit('update:show', false)
}

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 10) {
    if (selectedDate.value && !isLoadingHistory.value && hasMore.value) {
      loadMoreHistory()
    }
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    setTimeout(() => {
      scrollToTop()
    }, 100)
  }
})
</script>

<template>
  <n-modal :show="show" @update:show="val => emit('update:show', val)" transform-origin="center">
    <n-card
      style="width: 96vw; height: 96vh; display: flex; flex-direction: column;"
      content-style="padding: 0; display: flex; flex-direction: column; height: 100%; overflow: hidden;"
      :bordered="false"
      size="small"
      aria-modal="true"
    >
      <template #header>
        <div class="console-header">
          <div class="d-flex align-center gap-2">
            <n-icon size="20" style="color: var(--n-primary-color)"><TerminalIcon /></n-icon>
            <span class="title">{{ selectedDate ? `历史记录: ${selectedDate}` : '实时系统日志 (Live)' }}</span>
            <n-tag v-if="!selectedDate" :type="socketStatus === 'connected' ? 'success' : 'error'" size="tiny" bordered round>
              <template #icon>
                <div v-if="socketStatus === 'connected'" class="pulse-dot"></div>
              </template>
              {{ socketStatus === 'connected' ? '就绪' : '断开' }}
            </n-tag>
            <n-tag v-else type="info" size="tiny" bordered round>历史归档</n-tag>
          </div>
          <div class="header-controls">
             <n-space align="center">
              <n-select 
                v-model:value="selectedDate"
                placeholder="历史日志回溯"
                size="tiny"
                style="width: 160px;"
                :options="[
                  { label: '🔴 实时日志流', value: null },
                  ...logDates.map(d => ({ label: `📅 ${d}`, value: d }))
                ]"
                @update:value="handleDateChange"
              />
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="autoScroll = !autoScroll" :type="autoScroll ? 'primary' : 'default'" title="自动置顶">
                {{ autoScroll ? '跟随' : '自由' }}
              </n-button>
              <n-button v-if="!selectedDate" v-bind="getButtonStyle('secondary')" size="tiny" @click="isPaused = !isPaused" :type="isPaused ? 'warning' : 'default'">
                {{ isPaused ? '恢复' : '暂停' }}
              </n-button>
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="openFullLog">
                查看导出
              </n-button>
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="clearConsole">
                清空
              </n-button>
              <n-button v-bind="getButtonStyle('iconPrimary')" size="tiny" @click="close">
                <template #icon><n-icon><CloseIcon /></n-icon></template>
              </n-button>
            </n-space>
          </div>
        </div>
      </template>

      <div class="console-body">
        <n-spin :show="isInitialLoading" class="log-spin">
          <div v-if="consoleLogs.length === 0 && !isLoadingHistory" class="empty-tip">
            {{ selectedDate ? '该日期暂无日志记录' : '等待系统日志流中...' }}
          </div>
          <n-virtual-list
            ref="virtualListInst"
            class="log-list"
            :items="consoleLogs"
            :item-size="20"
            key-field="id"
            @scroll="handleScroll"
          >
            <template #default="{ item }">
              <div class="log-line" :id="`log-${item.id}`">{{ item.content }}</div>
            </template>
          </n-virtual-list>
          <div v-if="isLoadingHistory && consoleLogs.length > 0" class="loading-more">
             <n-spin size="small" />
             <span>正在加载更多历史日志...</span>
          </div>
          <div v-if="!hasMore && selectedDate && consoleLogs.length > 0" class="end-tip">
             --- 已加载全部历史日志 ---
          </div>
        </n-spin>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--app-surface-card);
  border-bottom: 1px solid var(--app-border-light);
  flex-shrink: 0;
}
.title { font-weight: bold; color: var(--n-text-color-1); font-size: 14px; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-2 { gap: 8px; }

.pulse-dot {
  width: 6px;
  height: 6px;
  background-color: var(--n-primary-color);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--n-primary-color);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: 0.6; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.6; }
}

.console-body {
  flex: 1;
  background-color: var(--app-surface-inner);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.log-spin {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

:deep(.n-spin-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.log-list {
  flex: 1;
  height: 100%;
}

:deep(.n-card) {
  border-radius: var(--card-border-radius, 12px) !important;
  overflow: hidden;
  border: 1px solid var(--app-border-light) !important;
}

.log-line {
  padding: 0 16px;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 20px;
  color: var(--n-text-color);
  opacity: 0.8;
  white-space: pre-wrap;
  word-break: break-all;
  transition: background 0.2s ease;
}

.log-line:hover {
  background-color: var(--bg-surface);
}

.empty-tip { color: var(--n-text-color-3); text-align: center; position: absolute; width: 100%; top: 100px; z-index: 10; font-style: italic; }

.loading-more, .end-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 0;
  color: var(--n-text-color-3);
  font-size: 12px;
}
</style>