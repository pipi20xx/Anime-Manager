<script setup lang="ts">
import { 
  NCard, NButton, NSpace, NIcon, NPopconfirm, NAlert, NGrid, NGridItem, NTag, NSpin
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
  <div class="maintenance-manager">
    <n-alert type="warning" title="危险区域" style="margin-bottom: 20px;">
      以下操作将永久删除数据库表中的所有数据（TRUNCATE）。执行后无法撤销，请务必确认操作目标。
    </n-alert>

    <n-spin :show="loading">
      <div v-for="(groupTables, schema) in groupedTables" :key="schema" class="schema-group">
        <div class="group-header">
          <n-icon size="20"><DbIcon /></n-icon>
          <h3>命名空间: {{ schema.toUpperCase() }}</h3>
        </div>
        
        <n-grid x-gap="12" y-gap="12" cols="1 s:2 m:3 l:4" responsive="screen">
          <n-grid-item v-for="table in groupTables" :key="table.name">
            <n-card bordered size="small" class="table-card">
              <div class="table-info">
                <div class="table-name" :title="table.name">{{ table.name.split('.')[1] }}</div>
                <div class="table-desc">{{ tableDescriptions[table.name] || '暂无说明' }}</div>
                <n-tag :type="table.count > 0 ? 'warning' : 'info'" size="small" round ghost style="align-self: flex-start;">
                  {{ table.count }} 行数据
                </n-tag>
              </div>
              <div class="actions">
                <n-popconfirm 
                  @positive-click="handleTruncate(table.name)"
                  positive-text="确认清理"
                  negative-text="取消"
                >
                  <template #trigger>
                    <n-button 
                      block 
                      secondary 
                      type="error" 
                      size="small"
                      :loading="maintenanceLoading[table.name]"
                    >
                      <template #icon><n-icon><CleanIcon /></n-icon></template>
                      清空数据
                    </n-button>
                  </template>
                  确认要清空数据库表 <code style="color: #e88080; font-weight: bold;">[{{ table.name }}]</code> 吗？
                </n-popconfirm>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.maintenance-manager { width: 100%; }
.schema-group { margin-bottom: 32px; }
.group-header { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  margin-bottom: 16px; 
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border-light);
  color: var(--n-primary-color);
}
.group-header h3 { margin: 0; font-size: 16px; letter-spacing: 1px; }

.table-card {
  height: 100%;
  transition: all 0.3s ease;
  background: var(--app-surface-card);
}
.table-card:hover {
  border-color: var(--n-error-color-suppl) !important;
  transform: translateY(-2px);
}

.table-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.table-name {
  font-weight: bold;
  font-size: 14px;
  word-break: break-all;
  color: var(--n-primary-color);
}
.table-desc {
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 1.4;
}
.actions { margin-top: auto; }
</style>
