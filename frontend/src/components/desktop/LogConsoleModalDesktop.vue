<script setup lang="ts">
import { watch } from 'vue'
import {
  NCard, NSpace, NButton, NIcon, NTag, NSwitch, NSelect, NSpin, useDialog
} from 'naive-ui'
import AppSelectField from '../AppSelectField.vue'
import AppGlassModal from '../AppGlassModal.vue'
import {
  TrashIcon as ClearIcon,
  ArrowDownIcon as ScrollIcon,
  ArrowTopRightOnSquareIcon as OpenIcon
} from '@heroicons/vue/24/outline'
import {
  PauseCircleIcon as PauseIcon,
  PlayCircleIcon as PlayIcon
} from '@heroicons/vue/24/solid'
import { useLogConsole } from '../../composables/components/useLogConsole'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])

const {
  consoleLogs,
  groupedConsoleLogs,
  isPaused,
  autoScroll,
  logContainerRef,
  socketStatus,
  logDates,
  selectedDate,
  isLoadingHistory,
  isInitialLoading,
  hasMore,
  handleDateChange,
  loadMoreHistory,
  handleScroll,
  scrollToBottom,
  clearConsole,
  openFullLog
} = useLogConsole()

const dialog = useDialog()

const handleClearConsole = () => {
  dialog.warning({
    title: '确认清空',
    content: '确定要清空当前控制台日志吗？',
    positiveText: '确定清空',
    negativeText: '取消',
    onPositiveClick: () => clearConsole()
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    setTimeout(() => {
      scrollToBottom()
    }, 100)
  }
})
</script>

<template>
  <AppGlassModal
    appearance-key="log-console-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    transform-origin="center"
    style="width: 96vw; height: 96vh;"
    content-style="padding: 0; display: flex; flex-direction: column; height: 100%; overflow: hidden;"
    :bordered="false"
    size="small"
    aria-modal="true"
  >
      <template #header>
        <div class="console-header">
          <div class="d-flex align-center gap-2">
            <span class="title">{{ selectedDate ? `历史记录: ${selectedDate}` : '实时系统日志 (Live)' }}</span>
            <n-tag v-if="!selectedDate" size="small" round :bordered="false" :style="socketStatus === 'connected' ? { color: '#fff', backgroundColor: '#10B981', borderColor: 'transparent' } : { color: '#fff', backgroundColor: '#ef4444', borderColor: 'transparent' }">
              <template #icon>
                <div v-if="socketStatus === 'connected'" class="pulse-dot"></div>
              </template>
              {{ socketStatus === 'connected' ? '就绪' : '断开' }}
            </n-tag>
            <n-tag v-else size="small" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">历史归档</n-tag>
          </div>
          <div class="header-controls">
             <n-space align="center">
              <AppSelectField 
                v-model:value="selectedDate"
                label="历史日志回溯"
                placeholder="选择日志日期"
                style="width: 260px;"
                :options="[
                  { label: '🔴 实时日志流', value: null },
                  ...logDates.map(d => ({ label: `📅 ${d}`, value: d }))
                ]"
                @update:value="handleDateChange"
              />
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="autoScroll = !autoScroll" :type="autoScroll ? 'primary' : 'default'" title="自动置底">
                {{ autoScroll ? '跟随' : '自由' }}
              </n-button>
              <n-button v-if="!selectedDate" v-bind="getButtonStyle('secondary')" size="tiny" @click="isPaused = !isPaused" :type="isPaused ? 'warning' : 'default'">
                {{ isPaused ? '恢复' : '暂停' }}
              </n-button>
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="openFullLog">
                查看导出
              </n-button>
              <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="handleClearConsole">
                清空
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
          <div ref="logContainerRef" class="log-scroll-container" @scroll="handleScroll">
            <div class="log-container">
              <div v-for="group in groupedConsoleLogs" :key="group.groupTime" class="log-group">
                <div class="log-group-time">{{ group.groupTime }}</div>
                <div class="log-group-line"></div>
                <div class="log-group-items">
                  <div v-for="log in group.logs" :key="log.id" class="log-line">
                    <span class="log-time">{{ log.time || '--:--:--' }}</span>
                    <span :class="['log-level', log.level.toLowerCase()]">{{ log.level }}</span>
                    <span class="log-msg">{{ log.message }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="isLoadingHistory && consoleLogs.length > 0" class="loading-more">
             <n-spin size="small" />
             <span>正在加载更多历史日志...</span>
          </div>
          <div v-if="!hasMore && selectedDate && consoleLogs.length > 0" class="end-tip">
             --- 已加载全部历史日志 ---
          </div>
        </n-spin>
      </div>
  </AppGlassModal>
</template>

<style scoped>
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: transparent;
  flex-shrink: 0;
}
.title { font-weight: bold; color: var(--text-primary); font-size: 14px; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-2 { gap: 8px; }

.pulse-dot {
  width: 6px;
  height: 6px;
  background-color: #fff;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.9); opacity: var(--opacity-secondary); }
  50% { transform: scale(1.1); opacity: var(--opacity-full); }
  100% { transform: scale(0.9); opacity: var(--opacity-secondary); }
}

.console-body {
  flex: 1;
  background-color: transparent;
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

:deep(.n-card) {
  border-radius: var(--card-border-radius, 12px) !important;
  overflow: hidden;
  border: 1px solid var(--app-border-light) !important;
  background: var(--app-modal-bg) !important;
}

/* 日志滚动容器 (使用 div + overflow 替代 n-virtual-list，支持动态分组高度) */
.log-scroll-container {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.log-container {
  font-family: var(--code-font, 'Fira Code', 'JetBrains Mono', monospace);
  font-size: var(--text-sm);
  background: var(--app-surface-card-mixed);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
}

/* 分组样式 — 与任务中心日志 (MoviePilot 风格) 对齐 */
.log-group {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-light);
}
.log-group:last-child { border-bottom: none; }
.log-group-time {
  color: var(--n-primary-color);
  font-size: var(--text-xs);
  min-width: 75px;
  flex-shrink: 0;
  padding-top: 2px;
  font-weight: 700;
}
.log-group-line {
  width: 2px;
  background-color: var(--n-primary-color);
  border-radius: 1px;
  flex-shrink: 0;
  align-self: stretch;
  margin: 4px 0;
  opacity: 0.6;
}
.log-group-items {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.log-line {
  display: flex;
  gap: var(--space-2);
  padding: 2px 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.log-time { color: var(--text-tertiary); min-width: 75px; flex-shrink: 0; }
.log-level {
  min-width: 40px;
  font-weight: bold;
  flex-shrink: 0;
}
.log-level.info { color: #52c41a; }
.log-level.error { color: #ff4d4f; }
.log-level.warning { color: #faad14; }
.log-level.debug { color: #8c8c8c; }
.log-level.critical { color: #ff4d4f; }
.log-msg { flex: 1; min-width: 0; }

.empty-tip { color: var(--text-tertiary); text-align: center; position: absolute; width: 100%; top: 100px; z-index: 10; font-style: italic; }

.loading-more, .end-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

/* === 移动端适配 === */
@media (max-width: 767px) {
  /* 头部: 纵向堆叠 */
  .console-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 12px;
  }
  .header-controls { width: 100%; }
  .header-controls :deep(.n-space) { flex-wrap: wrap; gap: 4px !important; width: 100%; }
  .header-controls :deep(.app-select-field[style*="width"]) { width: 100% !important; }

  /* 日志容器: 缩小 padding 和字号 */
  .log-container { padding: var(--space-2); font-size: var(--text-xs); }
  .log-group { gap: var(--space-2); padding: var(--space-1) 0; }
  .log-group-time { min-width: 60px; font-size: var(--text-2xs); }
  .log-group-line { margin: 2px 0; }

  /* 日志行: 时间+级别独占一行, 消息换行到下一行 */
  .log-line { flex-wrap: wrap; gap: 4px; padding: 1px 0; }
  .log-time { font-size: var(--text-2xs); min-width: 0 !important; flex-shrink: 0; }
  .log-level { font-size: var(--text-2xs); min-width: 0 !important; flex-shrink: 0; }
  .log-msg { font-size: var(--text-xs); flex: none !important; width: 100%; }
}
</style>