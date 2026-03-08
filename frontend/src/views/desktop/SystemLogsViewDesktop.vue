<script setup lang="ts">
import { h } from 'vue'
import { 
  NCard, NDataTable, NSpace, NButton, NIcon, NInput, NSelect, NTag, NText, NGrid, NGi
} from 'naive-ui'
import {
  HistoryOutlined as LogIcon,
  DeleteSweepOutlined as ClearIcon,
  RefreshOutlined as RefreshIcon,
  FileDownloadOutlined as ExportIcon,
  SearchOutlined as SearchIcon,
  TerminalOutlined as TerminalIcon
} from '@vicons/material'
import LogConsoleModal from '../../components/LogConsoleModal.vue'
import { useSystemLogs } from '../../composables/views/useSystemLogs'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  loading,
  showConsole,
  data,
  filters,
  pagination,
  fetchLogs,
  clearLogs,
  exportLogs
} = useSystemLogs()

const columns = [
  { title: '时间', key: 'timestamp', width: 180 },
  { title: '等级', key: 'level', width: 90, render(row: any) {
    const typeMap: any = { 'INFO': 'info', 'WARNING': 'warning', 'ERROR': 'error', 'DEBUG': 'default' }
    return h(NTag, { type: typeMap[row.level] || 'info', size: 'small', round: true, bordered: false }, { default: () => row.level })
  }},
  { title: '模块', key: 'module', width: 100, render(row: any) {
    return h(NText, { strong: true, depth: 2 }, { default: () => row.module })
  }},
  { title: '动作', key: 'action', width: 120, render(row: any) {
    return h(NText, { code: true, size: 'small' }, { default: () => row.action })
  }},
  { title: '消息内容', key: 'message', ellipsis: { tooltip: true } }
]
</script>

<template>
  <div class="system-logs">
    <div class="page-header">
      <div>
        <h1>系统审计日志</h1>
        <div class="subtitle">AUDIT LOGS & CONSOLE</div>
      </div>
      <n-space>
        <n-button type="primary" @click="showConsole = true" color="#2080f0">
          <template #icon><n-icon><TerminalIcon /></n-icon></template>
          打开实时控制台
        </n-button>
        <n-button quaternary type="error" @click="clearLogs">
          <template #icon><n-icon><ClearIcon /></n-icon></template>清空历史
        </n-button>
        <n-button secondary @click="exportLogs">
          <template #icon><n-icon><ExportIcon /></n-icon></template>导出
        </n-button>
      </n-space>
    </div>

    <n-card bordered class="mt-4">
      <template #header>
        <div class="d-flex align-center gap-2">
          <n-icon style="color: var(--n-primary-color)"><LogIcon /></n-icon>
          <span>历史操作记录</span>
        </div>
      </template>
      <template #header-extra>
        <n-button v-bind="getButtonStyle('icon')" @click="fetchLogs" :loading="loading">
          <template #icon><n-icon><RefreshIcon /></n-icon></template>
        </n-button>
      </template>

      <n-space vertical>
        <n-grid :cols="4" :x-gap="12">
          <n-gi :span="1">
            <n-select 
              v-model:value="filters.module" 
              placeholder="模块" 
              clearable 
              :options="[{label: '识别', value: '识别'}, {label: '整理', value: '整理'}, {label: 'STRM', value: 'STRM'}, {label: 'RSS', value: 'RSS'}, {label: '订阅', value: '订阅'}, {label: '系统', value: '系统'}, {label: '网络', value: '网络'}, {label: '数据库', value: '数据库'}]" 
            />
          </n-gi>
          <n-gi :span="1">
            <n-select 
              v-model:value="filters.level" 
              placeholder="等级" 
              clearable 
              :options="[{label: 'INFO', value: 'INFO'}, {label: 'WARNING', value: 'WARNING'}, {label: 'ERROR', value: 'ERROR'}, {label: 'DEBUG', value: 'DEBUG'}]" 
            />
          </n-gi>
          <n-gi :span="2">
            <n-input v-model:value="filters.keyword" placeholder="搜索..." @keypress.enter="fetchLogs">
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </n-gi>
        </n-grid>

        <n-data-table
          remote
          striped
          size="small"
          :loading="loading"
          :columns="columns"
          :data="data"
          :pagination="pagination"
          :row-key="(row: any) => row.id"
          @update:page="p => { pagination.page = p; fetchLogs() }"
          @update:page-size="s => { pagination.pageSize = s; fetchLogs() }"
        />
      </n-space>
    </n-card>

    <LogConsoleModal v-model:show="showConsole" />
  </div>
</template>

<style scoped>
.system-logs { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-2 { gap: 8px; }
.mt-4 { margin-top: 16px; }
</style>