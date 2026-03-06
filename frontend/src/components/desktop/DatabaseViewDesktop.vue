<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { 
  NCard, NInput, NButton, 
  NSpace, NDataTable, NIcon, NPopconfirm, NSelect, NTabs, NTabPane, NAlert, NPopover
} from 'naive-ui'
import DatabaseConfig from '../../components/DatabaseConfig.vue'
import MaintenanceManager from '../../components/MaintenanceManager.vue'
import TmdbFullDataView from '../../views/TmdbFullDataView.vue'
import SecondaryRuleView from '../../views/SecondaryRuleView.vue'
import UserMappingView from '../../views/UserMappingView.vue'
import {
  PlayArrowOutlined as RunIcon,
  RefreshOutlined as RefreshIcon,
  DeleteOutlined as DeleteIcon,
  StorageOutlined as DbIcon,
  DnsOutlined as MetaIcon,
  TerminalOutlined as SqlIcon,
  SettingsOutlined as ConfigIcon,
  CategoryOutlined as RuleIcon,
  BuildOutlined as BuildIcon,
  LabelOutlined as MappingIcon
} from '@vicons/material'
import { useDatabase } from '../../composables/views/useDatabase'

const {
  activeTab,
  tables,
  loading,
  queryLoading,
  currentSql,
  queryResult,
  columns: rawColumns,
  searchText,
  currentTable,
  currentPk,
  editState,
  scrollX,
  filteredData,
  tableOptions,
  fetchTables,
  handleUpdate,
  deleteRow,
  handleManualRun,
  selectTable
} = useDatabase()

// Reconstruct DataTable columns definition
const dataTableColumns = computed(() => {
  if (!rawColumns.value || rawColumns.value.length === 0) return []
  
  const cols = rawColumns.value.map((col: string) => ({
    title: col, key: col, width: 200, ellipsis: { tooltip: false },
    render(row: any) {
        const rawVal = row[col]
        const displayStr = rawVal === null ? '(NULL)' : (typeof rawVal === 'object' ? JSON.stringify(rawVal) : String(rawVal))
        
        const isPk = col === currentPk.value
        const isEditing = currentPk.value && editState.value.rowPk === row[currentPk.value] && editState.value.colKey === col

        if (isEditing) {
            return h(NInput, {
                defaultValue: typeof rawVal === 'object' ? JSON.stringify(rawVal) : String(rawVal || ''),
                autofocus: true, size: 'small',
                onBlur: (e: FocusEvent) => handleUpdate(row, col, (e.target as HTMLInputElement).value),
                onKeyup: (e: KeyboardEvent) => {
                    if (e.key === 'Enter') handleUpdate(row, col, (e.target as HTMLInputElement).value)
                }
            })
        }

        const popoverContent = () => {
            if (rawVal === null) return h('span', { style: 'color: #666' }, '(NULL)')
            if (typeof rawVal === 'object') {
                return h('pre', { 
                    style: 'font-size: 12px; max-height: 400px; overflow: auto; margin: 0; color: #63e2b7;' 
                }, JSON.stringify(rawVal, null, 2))
            }
            return h('div', { style: 'max-width: 400px; word-break: break-all;' }, String(rawVal))
        }

        const cellDiv = h('div', {
            style: `cursor: ${isPk ? 'default' : 'text'}; min-height: 20px; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;`,
            onDblclick: () => { if (!isPk) editState.value = { rowPk: row[currentPk.value], colKey: col } }
        }, { default: () => displayStr })

        if (rawVal === null) return cellDiv

        return h(NPopover, { 
            trigger: 'hover', 
            placement: 'top', 
            style: 'max-width: 600px; background: #18181c; border: 1px solid #333;',
            showArrow: true,
            scrollable: true
        }, {
            trigger: () => cellDiv,
            default: popoverContent
        })
    }
  }))

  if (currentTable.value && currentPk.value) {
      cols.push({
          title: '操作', key: 'actions', width: 80, fixed: 'right',
          render(row: any) {
              return h(NPopconfirm, { 
                  onPositiveClick: () => deleteRow(row),
                  positiveText: '确认删除',
                  negativeText: '取消'
              }, {
                  trigger: () => h(NButton, { size: 'small', type: 'error', quaternary: true, circle: true }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) }),
                  default: () => `确认删除行?`
              })
          }
      })
  }
  return cols
})
</script>

<template>
  <div class="db-view">
    <div class="page-header">
      <div class="d-flex align-center gap-3">
        <div>
          <h1>数据中心</h1>
          <div class="subtitle">高性能 PostgreSQL 引擎与超级元数据资产管理</div>
        </div>
      </div>
    </div>

    <n-tabs type="card" animated v-model:value="activeTab" class="main-tabs">
      <n-tab-pane name="metadata" tab="元数据资产">
        <template #tab><n-space :size="4" align="center"><n-icon><MetaIcon /></n-icon> 元数据资产</n-space></template>
        <div class="pane-content"><TmdbFullDataView /></div>
      </n-tab-pane>

      <n-tab-pane name="rules" tab="二级分类规则">
        <template #tab><n-space :size="4" align="center"><n-icon><RuleIcon /></n-icon> 二级分类规则</n-space></template>
        <div class="pane-content"><SecondaryRuleView /></div>
      </n-tab-pane>

      <n-tab-pane name="mapping" tab="ID映射管理">
        <template #tab><n-space :size="4" align="center"><n-icon><MappingIcon /></n-icon> ID映射管理</n-space></template>
        <div class="pane-content"><UserMappingView /></div>
      </n-tab-pane>

      <n-tab-pane name="lab" tab="SQL 实验室">
        <template #tab><n-space :size="4" align="center"><n-icon><SqlIcon /></n-icon> SQL 实验室</n-space></template>
        <n-space vertical size="large" class="pane-content">
          <n-alert type="warning" title="高级操作提示">此处直接操作生产数据库。如果您不熟悉 SQL 语法，请谨慎执行修改操作。</n-alert>
          <n-card bordered size="small">
            <template #header-extra>
              <n-button circle quaternary @click="fetchTables" :loading="loading" size="small">
                <template #icon><n-icon><RefreshIcon /></n-icon></template>
              </n-button>
            </template>
            <n-select v-model:value="currentTable" filterable placeholder="🔍 选择数据表进行浏览..." :options="tableOptions" :loading="loading" @update:value="selectTable" />
          </n-card>
          <n-card bordered size="small">
            <div class="sql-box">
              <n-input v-model:value="currentSql" type="textarea" placeholder="输入 SQL..." :autosize="{ minRows: 2, maxRows: 5 }" class="sql-input" />
              <n-button type="primary" ghost class="run-btn" :loading="queryLoading" @click="handleManualRun">
                <template #icon><n-icon><RunIcon /></n-icon></template>执行
              </n-button>
            </div>
          </n-card>
          <n-card bordered title="执行结果" size="small" class="result-card">
            <template #header-extra><n-input v-model:value="searchText" placeholder="在结果中搜索..." size="small" clearable style="width: 250px" /></template>
            <n-data-table :columns="dataTableColumns" :data="filteredData" :loading="queryLoading" :max-height="500" :scroll-x="scrollX" virtual-scroll size="small" :single-line="false" />
            <template #footer><div class="footer-info">显示 {{ filteredData.length }} / 共 {{ queryResult.length }} 条记录</div></template>
          </n-card>
        </n-space>
      </n-tab-pane>

      <n-tab-pane name="config" tab="引擎配置">
        <template #tab><n-space :size="4" align="center"><n-icon><ConfigIcon /></n-icon> 引擎配置</n-space></template>
        <div class="pane-content"><DatabaseConfig /></div>
      </n-tab-pane>

      <n-tab-pane name="maintenance" tab="维护中心">
        <template #tab><n-space :size="4" align="center"><n-icon><BuildIcon /></n-icon> 维护中心</n-space></template>
        <div class="pane-content">
          <MaintenanceManager />
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.db-view { width: 100%; height: 100%; }
.page-header { padding-bottom: 16px; margin-bottom: 12px; }
.pane-content { padding-top: 16px; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-3 { gap: 12px; }
.sql-box { display: flex; gap: 12px; }
.sql-input { font-family: 'JetBrains Mono', monospace; background: var(--app-surface-inner); border-radius: 4px; }
.run-btn { height: auto; border-radius: 4px; }
.result-card { background: var(--app-surface-card) !important; border: 1px solid var(--app-border-light) !important; min-height: 400px; border-radius: 12px !important; }
.footer-info { font-size: 12px; color: var(--n-text-color-3); text-align: right; }
:deep(.n-tabs-nav) { background: transparent; }
:deep(.n-tabs-pane-wrapper) { padding: 0; }
</style>
