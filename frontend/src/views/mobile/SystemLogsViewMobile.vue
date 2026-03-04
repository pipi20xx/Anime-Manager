<script setup lang="ts">
import { 
  NCard, NList, NListItem, NThing, NSpace, NButton, NIcon, NInput, NSelect, NTag, NCollapse, NCollapseItem
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

const loadMore = () => {
  if (data.value.length < pagination.itemCount) {
    pagination.pageSize += 20
    fetchLogs()
  }
}
</script>

<template>
  <div class="system-logs-mobile">
    <div class="mobile-header">
      <div class="header-title">系统日志</div>
      <n-space>
        <n-button circle secondary @click="showConsole = true">
          <template #icon><n-icon><TerminalIcon /></n-icon></template>
        </n-button>
        <n-button circle secondary @click="exportLogs">
          <template #icon><n-icon><ExportIcon /></n-icon></template>
        </n-button>
      </n-space>
    </div>

    <n-card :bordered="false" size="small" style="margin-bottom: 12px">
      <n-collapse>
        <n-collapse-item title="筛选与搜索" name="1">
          <n-space vertical>
            <n-select v-model:value="filters.module" placeholder="模块" clearable :options="[{label: '识别', value: '识别'}, {label: '整理', value: '整理'}, {label: 'STRM', value: 'STRM'}, {label: 'RSS', value: 'RSS'}, {label: '订阅', value: '订阅'}, {label: '系统', value: '系统'}, {label: '网络', value: '网络'}, {label: '数据库', value: '数据库'}]" />
            <n-select v-model:value="filters.level" placeholder="等级" clearable :options="[{label: 'INFO', value: 'INFO'}, {label: 'WARNING', value: 'WARNING'}, {label: 'ERROR', value: 'ERROR'}, {label: 'DEBUG', value: 'DEBUG'}]" />
            <n-input v-model:value="filters.keyword" placeholder="搜索内容..." @keypress.enter="fetchLogs">
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
            <n-button block type="primary" @click="fetchLogs" :loading="loading">查询</n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </n-card>

    <div class="log-list">
      <n-list hoverable>
        <n-list-item v-for="log in data" :key="log.id">
          <n-thing>
            <template #header>
              <div class="log-header">
                <n-tag :type="log.level === 'ERROR' ? 'error' : (log.level === 'WARNING' ? 'warning' : 'info')" size="tiny" round>{{ log.level }}</n-tag>
                <span class="log-module">{{ log.module }}</span>
                <span class="log-time">{{ log.timestamp?.split('T')[1]?.split('.')[0] }}</span>
              </div>
            </template>
            <template #description>
              <div class="log-msg">{{ log.message }}</div>
            </template>
          </n-thing>
        </n-list-item>
      </n-list>
      
      <div style="padding: 16px; text-align: center;">
        <n-button v-if="data.length < pagination.itemCount" text type="primary" @click="loadMore" :loading="loading">
          加载更多...
        </n-button>
        <span v-else style="color: #666; font-size: 12px">已加载全部</span>
      </div>
    </div>

    <LogConsoleModal v-model:show="showConsole" />
  </div>
</template>

<style scoped>
.system-logs-mobile { padding: 12px; }
.mobile-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-title { font-size: 18px; font-weight: bold; }

.log-header { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.log-module { font-weight: bold; color: var(--n-text-color-2); }
.log-time { margin-left: auto; color: #888; font-family: monospace; }
.log-msg { font-size: 13px; color: var(--n-text-color-1); word-break: break-all; margin-top: 4px; }
</style>