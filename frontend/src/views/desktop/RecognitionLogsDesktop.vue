<script setup lang="ts">
import { NCard, NTag, NScrollbar } from 'naive-ui'
import { useRecognitionLogs } from '../../composables/views/useRecognitionLogs'

const { recognitionState, getLogClass, logScrollbar } = useRecognitionLogs()
</script>

<template>
  <div class="logs-view">
    <div class="page-header">
      <div>
        <h1>系统审计日志</h1>
        <div class="subtitle">实时识别流程审计</div>
      </div>
      <n-tag type="info" size="large" round ghost>
        {{ recognitionState.loading ? '正在执行...' : '就绪' }}
      </n-tag>
    </div>

    <n-card size="small" bordered class="log-card" title="审计流水线" content-style="padding: 0;">
      <template #header-extra>
        <n-tag size="small" round :bordered="false" type="info" ghost>{{ recognitionState.logs.length }} 行</n-tag>
      </template>
      <div class="log-container-wrapper">
        <n-scrollbar ref="logScrollbar" style="height: 100%" trigger="none">
          <div class="log-content">
            <div v-for="(log, i) in (Array.isArray(recognitionState.logs) ? recognitionState.logs : [])" :key="i" :class="['log-line', getLogClass(log)]">
              <span class="line-num">{{ String(i+1).padStart(2, '0') }}</span><span class="line-text">{{ String(log) }}</span>
            </div>
          </div>
        </n-scrollbar>
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.logs-view { 
  width: 100%; 
  display: flex; 
  flex-direction: column;
}

.header h1 { margin: 0; font-size: 28px; color: var(--text-primary); }
.subtitle { font-size: 12px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }

.log-card { 
  flex-grow: 1; 
  display: flex; 
  flex-direction: column;
  background: var(--app-surface-card);
}

.log-container-wrapper {
  height: calc(100vh - 220px); 
  min-height: 500px;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: var(--code-radius, 4px);
}

.log-content {
  padding: 12px;
  font-family: var(--code-font);
  font-size: 12px;
}

.log-line { display: flex; gap: 12px; padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.02); }
.line-num { color: var(--text-muted); min-width: 24px; text-align: right; font-size: 10px; user-select: none; }
.log-header { color: var(--n-primary-color); font-weight: bold; margin: 8px 0; border-bottom: 1px solid var(--app-border-light); }
.log-debug { color: var(--n-info-color); }
.log-success { color: var(--n-primary-color); }
.log-warning { color: var(--n-warning-color); }
.log-result { background: var(--warning-light); border-left: 3px solid var(--n-warning-color); padding-left: 12px; font-weight: bold; margin: 8px 0; }
</style>
