<script setup lang="ts">
import { ref, computed } from 'vue'
import { 
  NCard, NInput, NButton, 
  NSpace, NIcon, NTabs, NTabPane, NAlert, NList, NListItem, NThing, NTag, NCollapse, NCollapseItem, NCollapseTransition,
  NDrawer, NDrawerContent
} from 'naive-ui'
import DatabaseConfig from '../../components/DatabaseConfig.vue'
import MaintenanceManager from '../../components/MaintenanceManager.vue'
import TmdbFullDataView from '../../views/TmdbFullDataView.vue'
import SecondaryRuleView from '../../views/SecondaryRuleView.vue'
import UserMappingView from '../../views/UserMappingView.vue'
import {
  PlayArrowOutlined as RunIcon,
  RefreshOutlined as RefreshIcon,
  StorageOutlined as DbIcon,
  TableChartOutlined as TableIcon
} from '@vicons/material'
import { useDatabase } from '../../composables/views/useDatabase'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  activeTab,
  loading,
  queryLoading,
  currentSql,
  queryResult,
  columns,
  searchText,
  currentTable,
  filteredData,
  tableOptions,
  fetchTables,
  runQuery,
  handleManualRun,
  selectTable
} = useDatabase()

const showSql = ref(false)
const showTableDrawer = ref(false)

const handleTableSelect = (tableName: string) => {
  selectTable(tableName)
  showTableDrawer.value = false
}
</script>

<template>
  <div class="db-view-mobile">
    <div class="mobile-header">
      <div class="header-left">
        <n-icon size="24" color="var(--n-primary-color)"><DbIcon /></n-icon>
        <span class="header-title">数据中心</span>
      </div>
    </div>

    <n-tabs type="line" animated v-model:value="activeTab" style="flex: 1; display: flex; flex-direction: column; width: 100%; box-sizing: border-box;">
      <n-tab-pane name="metadata" tab="元数据" style="padding: 0; box-sizing: border-box;">
        <div class="horizontal-scroll-wrapper">
          <TmdbFullDataView />
        </div>
      </n-tab-pane>

      <n-tab-pane name="rules" tab="规则" style="padding: 0; box-sizing: border-box;">
        <div class="horizontal-scroll-wrapper">
          <SecondaryRuleView />
        </div>
      </n-tab-pane>

      <n-tab-pane name="mapping" tab="映射" style="padding: 0; box-sizing: border-box;">
        <div class="horizontal-scroll-wrapper">
          <UserMappingView />
        </div>
      </n-tab-pane>

      <n-tab-pane name="lab" tab="SQL" style="padding: 12px; overflow-y: auto; box-sizing: border-box;">
        
        <!-- Table Selector Area -->
        <div style="background: var(--app-surface-card); border: 1px solid var(--app-border-light); border-radius: var(--card-border-radius, 8px); padding: 12px; margin-bottom: 12px; box-sizing: border-box;">
          <div style="font-size: 12px; color: var(--n-text-color-3); margin-bottom: 8px; font-weight: bold; display: flex; justify-content: space-between;">
            <span>操作数据表</span>
            <span>共 {{ tableOptions.length }} 张表</span>
          </div>
          
          <div 
            @click="showTableDrawer = true"
            style="background: var(--app-surface-inner); padding: 10px; border-radius: 4px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; border: 1px solid var(--app-border-light);"
          >
            <span style="font-weight: bold; color: var(--n-primary-color);">
              {{ currentTable || '点击选择数据表...' }}
            </span>
            <n-icon><TableIcon /></n-icon>
          </div>
        </div>

        <!-- Advanced SQL Area -->
        <n-card size="small" :bordered="true" title="自定义 SQL" style="margin-bottom: 12px; background: var(--app-surface-inner); box-sizing: border-box;">
            <template #header-extra>
               <n-button v-bind="getButtonStyle('secondary')" @click="showSql = !showSql" size="small">
                 {{ showSql ? '收起' : '展开编辑器' }}
               </n-button>
            </template>
            <n-collapse-transition :show="showSql">
              <div style="padding-top: 8px;">
                <n-input 
                  v-model:value="currentSql" 
                  type="textarea" 
                  placeholder="SELECT * FROM ..." 
                  :autosize="{ minRows: 3, maxRows: 8 }" 
                  style="font-family: monospace; margin-bottom: 8px;"
                />
                <n-button v-bind="getButtonStyle('primary')" block size="small" :loading="queryLoading" @click="handleManualRun">
                  执行 SQL
                </n-button>
              </div>
            </n-collapse-transition>
        </n-card>

        <!-- Results Area -->
        <div v-if="queryResult.length > 0" style="margin-top: 16px;">
          <div class="result-header">
            <span>结果: {{ filteredData.length }} 行</span>
            <n-input v-model:value="searchText" placeholder="结果搜索..." size="tiny" style="width: 120px" />
          </div>
          
          <div class="result-card-list">
            <div v-for="(row, idx) in filteredData" :key="idx" class="sql-result-card">
              <div class="card-header">
                <span class="row-index">#{{ idx + 1 }}</span>
              </div>
              <div class="row-kv">
                <div v-for="col in columns.slice(0, 10)" :key="col" class="kv-item">
                  <span class="k">{{ col }}:</span>
                  <span class="v">{{ row[col] }}</span>
                </div>
                <div v-if="columns.length > 10" class="more-indicator">
                  ... 还有 {{ columns.length - 10 }} 列
                </div>
              </div>
            </div>
          </div>
        </div>
        <n-alert v-else-if="!queryLoading" type="info" :show-icon="false" style="margin-top: 16px;">
          暂无查询结果，请选择数据表或执行 SQL
        </n-alert>
      </n-tab-pane>

      <n-tab-pane name="config" tab="配置" style="padding: 8px; overflow-y: auto; box-sizing: border-box;">
        <DatabaseConfig />
      </n-tab-pane>

      <n-tab-pane name="maintenance" tab="维护" style="padding: 8px; overflow-y: auto; box-sizing: border-box;">
        <MaintenanceManager />
      </n-tab-pane>
    </n-tabs>

    <n-drawer v-model:show="showTableDrawer" placement="bottom" height="60vh" style="border-radius: 16px 16px 0 0;">
      <n-drawer-content title="选择数据表" closable>
        <n-list clickable>
          <n-list-item v-for="t in tableOptions" :key="t.value" @click="handleTableSelect(t.value)">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span :style="{ fontWeight: currentTable === t.value ? 'bold' : 'normal', color: currentTable === t.value ? 'var(--n-primary-color)' : 'inherit' }">
                {{ t.value }}
              </span>
              <n-tag size="small" round :type="currentTable === t.value ? 'primary' : 'default'">{{ t.label.split('(')[1].replace(')', '') }}</n-tag>
            </div>
          </n-list-item>
        </n-list>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>
<style scoped>
.db-view-mobile { 
  height: 100%; 
  display: flex; 
  flex-direction: column; 
  width: 100%; 
  overflow-x: hidden; 
  box-sizing: border-box;
}
.mobile-header { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid var(--app-border-light); }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-title { font-size: 18px; font-weight: bold; }

.horizontal-scroll-wrapper { 
  width: 100%; 
  overflow-x: auto; 
  -webkit-overflow-scrolling: touch; 
  box-sizing: border-box;
}

.result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 12px; color: #666; }
.result-card-list { 
  display: flex; 
  flex-direction: column; 
  gap: 12px; 
  width: 100%;
  box-sizing: border-box;
}
.sql-result-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
}
.card-header { margin-bottom: 8px; border-bottom: 1px solid var(--app-border-light); padding-bottom: 4px; }
.row-index { font-family: monospace; color: var(--n-primary-color); font-weight: bold; font-size: 13px; }
.row-kv { display: flex; flex-direction: column; gap: 4px; }
.kv-item { display: flex; gap: 6px; font-size: 11px; align-items: flex-start; }
.k { color: #555; flex-shrink: 0; font-weight: bold; min-width: 40px; }
.v { color: var(--n-text-color-2); word-break: break-all; line-height: 1.4; }
.more-indicator { font-size: 10px; color: #444; margin-top: 4px; font-style: italic; }
</style>
