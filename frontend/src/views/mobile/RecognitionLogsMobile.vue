<script setup lang="ts">
import { NTag, NScrollbar } from 'naive-ui'
import { useRecognitionLogs } from '../../composables/views/useRecognitionLogs'

const { recognitionState, getLogClass, logScrollbar } = useRecognitionLogs()
</script>

<template>
  <div class="logs-mobile">
    <div class="header-mobile">
      <h1>审计日志</h1>
      <n-tag type="info" size="small" round ghost>
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
  padding-bottom: 80px; /* Space for bottom nav */
}

.header-mobile {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  border-bottom: 1px solid var(--n-border-color);
  background-color: var(--app-surface-color);
}
.header-mobile h1 { margin: 0; font-size: 18px; font-weight: 800; }

.log-area {
  flex: 1;
  overflow-y: auto;
  background: var(--app-surface-inner);
}

.log-content {
  padding: 12px;
  font-family: monospace; /* 移动端默认等宽字体 */
  font-size: 11px;
}

.log-line { 
  display: flex; 
  gap: 8px; 
  padding: 4px 0; 
  border-bottom: 1px solid rgba(255,255,255,0.02); 
  align-items: flex-start; /* 对齐顶部，防止行号错位 */
}

.line-num { 
  color: var(--text-muted); 
  min-width: 20px; 
  text-align: right; 
  font-size: 10px; 
  user-select: none;
  flex-shrink: 0;
}

.line-text {
  word-break: break-all; /* 关键：允许在任意字符间换行 */
  white-space: pre-wrap; /* 保留空白符，但允许换行 */
  line-height: 1.4;
  flex: 1; /* 占据剩余宽度 */
}

/* 日志颜色适配 */
:deep(.log-header) { color: var(--n-primary-color); font-weight: bold; margin: 8px 0; border-bottom: 1px solid var(--app-border-light); }
:deep(.log-debug) { color: var(--n-info-color); }
:deep(.log-success) { color: var(--n-primary-color); }
:deep(.log-warning) { color: var(--n-warning-color); }
:deep(.log-result) { 
  background: color-mix(in srgb, var(--n-warning-color), transparent 90%); 
  border-left: 2px solid var(--n-warning-color); 
  padding: 8px; 
  font-weight: bold; 
  margin: 8px 0; 
  border-radius: 4px;
}
</style>
