<script setup lang="ts">
import { 
  NCard, NButton, NIcon, NPopconfirm, NAlert, NTag, NSpin, NList, NListItem, NThing
} from 'naive-ui'
import {
  CleaningServicesOutlined as CleanIcon,
  StorageOutlined as DbIcon
} from '@vicons/material'
import { useMaintenance } from '../../composables/components/useMaintenance'

const {
  loading,
  maintenanceLoading,
  groupedTables,
  tableDescriptions,
  handleTruncate
} = useMaintenance()
</script>

<template>
  <div class="maintenance-manager-mobile">
    <n-alert type="warning" title="危险区域" style="margin-bottom: 16px;">
      永久删除表数据，无法撤销。
    </n-alert>

    <n-spin :show="loading">
      <div v-for="(groupTables, schema) in groupedTables" :key="schema" class="schema-group">
        <div class="group-header">
          <n-icon size="20"><DbIcon /></n-icon>
          <h3>命名空间: {{ schema.toUpperCase() }}</h3>
        </div>
        
        <div class="maintenance-grid">
          <div v-for="table in groupTables" :key="table.name" class="maintenance-card">
            <div class="m-card-header">
              <span class="table-name">{{ table.name.split('.')[1] }}</span>
              <n-popconfirm 
                @positive-click="handleTruncate(table.name)"
                positive-text="清理"
                negative-text="取消"
              >
                <template #trigger>
                  <n-button 
                    size="tiny" 
                    secondary 
                    type="error" 
                    circle
                    :loading="maintenanceLoading[table.name]"
                  >
                    <template #icon><n-icon><CleanIcon /></n-icon></template>
                  </n-button>
                </template>
                确认清空 {{ table.name }}?
              </n-popconfirm>
            </div>
            <div class="m-card-body">
              <div class="table-desc">{{ tableDescriptions[table.name] || '暂无说明' }}</div>
              <div class="table-meta">
                <n-tag :type="table.count > 0 ? 'warning' : 'info'" size="tiny" round ghost>
                  {{ table.count }} 行数据
                </n-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.maintenance-manager-mobile { 
  width: 100%; 
  padding: 8px; 
  box-sizing: border-box;
  overflow-x: hidden;
}
.schema-group { margin-bottom: 24px; }
.group-header { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  margin-bottom: 8px; 
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border-light);
  color: var(--n-primary-color);
}
.group-header h3 { margin: 0; font-size: 14px; letter-spacing: 1px; }

.maintenance-grid { display: flex; flex-direction: column; gap: 10px; }
.maintenance-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
}
.m-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.table-name { font-weight: bold; font-size: 14px; color: var(--n-text-color-1); font-family: monospace; }
.table-desc { font-size: 12px; color: var(--text-tertiary); line-height: 1.4; margin-bottom: 8px; }
.table-meta { display: flex; gap: 8px; }
</style>
