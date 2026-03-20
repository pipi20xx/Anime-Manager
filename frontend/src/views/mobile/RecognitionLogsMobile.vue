<script setup lang="ts">
import { NTag, NScrollbar } from 'naive-ui'
import { useRecognitionLogs } from '../../composables/views/useRecognitionLogs'

const { recognitionState, getLogClass, logScrollbar } = useRecognitionLogs()
</script>

<template>
  <div class="logs-mobile">
    <div class="header-mobile">
      <h1>审计日志</h1>
      <n-tag size="small" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">
        {{ recognitionState.loading ? '执行中...' : '就绪' }} | {{ recognitionState.logs.length }} 行
      </n-tag>
    </div>

    <div class="log-area">
        <div class="log-content">
          <div v-for="(log, i) in (Array.isArray(recognitionState.logs) ? recognitionState.logs : [])" :key="i" :class="['log-line', getLogClass(log)]">
            <span class="line-num">{{ i+1 }}</span>
            <span class="line-text">{{ String(log) }}</span>
          </div>
          <!-- 底部锚点，用于自动滚动 -->
          <div ref="logScrollbar"></div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.logs-mobile {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--app-background);
  padding-bottom: var(--m-safe-bottom);
}

.header-mobile {
  padding: var(--m-spacing-md) var(--m-spacing-lg);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
  background-color: var(--app-surface-color);
}
.header-mobile h1 { margin: 0; font-size: var(--m-text-xl); font-weight: 700; }

.log-area {
  flex: 1;
  overflow-y: auto;
  background: var(--app-surface-inner);
  -webkit-overflow-scrolling: touch;
}

.log-content {
  padding: var(--m-spacing-md);
  font-family: 'SF Mono', Monaco, monospace;
  font-size: var(--m-text-xs);
}

.log-line {
  display: flex;
  gap: var(--m-spacing-sm);
  padding: var(--m-spacing-xs) 0;
  border-bottom: 1px solid var(--border-light);
  align-items: flex-start;
}

.line-num {
  color: var(--text-muted);
  min-width: 24px;
  text-align: right;
  font-size: var(--m-text-xs);
  user-select: none;
  flex-shrink: 0;
}

.line-text {
  word-break: break-all;
  white-space: pre-wrap;
  line-height: 1.5;
  flex: 1;
}

/* 日志颜色适配 */
:deep(.log-header) { color: var(--n-primary-color); font-weight: bold; margin: var(--m-spacing-sm) 0; border-bottom: 1px solid var(--app-border-light); }
:deep(.log-debug) { color: var(--n-info-color); }
:deep(.log-success) { color: var(--n-primary-color); }
:deep(.log-warning) { color: var(--n-warning-color); }
:deep(.log-result) {
  background: var(--warning-light);
  border-left: 2px solid var(--n-warning-color);
  padding: var(--m-spacing-sm);
  font-weight: bold;
  margin: var(--m-spacing-sm) 0;
  border-radius: var(--m-radius-sm);
}
</style>
