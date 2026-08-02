<script setup lang="ts">
/**
 * SqlLabTab — SQL 实验室
 *
 * 对标旧前端 useDatabase + DatabaseViewDesktop:
 * - 选择表后一次性加载大量数据（LIMIT 10000），前端分页/搜索
 * - SQL 手动查询
 * - 单元格编辑（双击）、行删除
 * - 行详情弹窗
 * - 鼠标拖拽横向滚动
 */
import { ref, computed, onMounted, onActivated, watch, onUnmounted } from 'vue'
import { dataCenterApi } from '@/api'
import { useNotification, useConfirm, formatDbSize } from '@/composables'

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()

// ===== 表列表 =====
const tables = ref<any[]>([])
const loading = ref(false)
const currentTable = ref('')
const currentPk = ref('id')

// ===== 数据浏览 =====
const queryResult = ref<any[]>([])
const columns = ref<string[]>([])
const queryLoading = ref(false)
const searchText = ref('')

// ===== 分页（客户端） =====
const sqlPage = ref(1)
const sqlPageSize = ref(20)

// ===== SQL 查询 =====
const currentSql = ref('')

// ===== 单元格编辑 =====
const editState = ref<{ rowPk: any; colKey: string } | null>(null)
const editInputValue = ref('')

// ===== 行详情弹窗 =====
const showDbRowDetail = ref(false)
const dbRowDetailItem = ref<any>(null)

// ===== 拖拽滚动（直接实现，确保绑定时机正确） =====
const tableWrapperRef = ref<HTMLElement | null>(null)
let dragState = { isDragging: false, startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0, hasMoved: false }

function onDragMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  const el = tableWrapperRef.value
  if (!el) return
  // 忽略在 input / button 上的拖拽
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'BUTTON' || tag === 'A' || tag === 'SELECT') return

  dragState = { isDragging: true, hasMoved: false, startX: e.pageX, startY: e.pageY, scrollLeft: el.scrollLeft, scrollTop: el.scrollTop }
  el.style.cursor = 'grabbing'
  el.style.userSelect = 'none'
  e.preventDefault()
}

function onDragMouseMove(e: MouseEvent) {
  if (!dragState.isDragging) return
  const el = tableWrapperRef.value
  if (!el) return
  const dx = e.pageX - dragState.startX
  const dy = e.pageY - dragState.startY
  if (!dragState.hasMoved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) dragState.hasMoved = true
  if (dragState.hasMoved) {
    el.scrollLeft = dragState.scrollLeft - dx
    el.scrollTop = dragState.scrollTop - dy
  }
}

function onDragMouseUp() {
  if (!dragState.isDragging) return
  dragState.isDragging = false
  const el = tableWrapperRef.value
  if (el) { el.style.cursor = 'grab'; el.style.userSelect = '' }
}

// 全局监听 move/up（确保鼠标移出容器后也能继续拖拽）
window.addEventListener('mousemove', onDragMouseMove)
window.addEventListener('mouseup', onDragMouseUp)

onUnmounted(() => {
  window.removeEventListener('mousemove', onDragMouseMove)
  window.removeEventListener('mouseup', onDragMouseUp)
})

// ===== 客户端过滤 + 分页 =====
watch(searchText, () => { sqlPage.value = 1 })

const filteredData = computed(() => {
  if (!searchText.value) return queryResult.value
  const q = searchText.value.toLowerCase()
  return queryResult.value.filter((row: any) =>
    Object.values(row).some((v: any) => v != null && String(v).toLowerCase().includes(q))
  )
})

const sqlTotal = computed(() => filteredData.value.length)

const paginatedData = computed(() => {
  const start = (sqlPage.value - 1) * sqlPageSize.value
  return filteredData.value.slice(start, start + sqlPageSize.value)
})

// ===== 表列表获取 =====
async function fetchTables() {
  loading.value = true
  try {
    const res = await dataCenterApi.getDbTables()
    tables.value = res?.tables || []
  } catch (e) { showError('加载数据库表列表失败') }
  finally { loading.value = false }
}

// 表选项（用于下拉选择）
const tableOptions = computed(() => {
  return tables.value.map((t: any) => ({
    title: `${t.name} (${t.count}行, ${formatDbSize(t.size_bytes)})`,
    value: t.name,
  }))
})

// ===== 选择表 =====
async function selectTable(tableName: string) {
  currentTable.value = tableName
  currentPk.value = 'id'
  searchText.value = ''
  sqlPage.value = 1

  // 获取主键信息
  try {
    const infoRes = await dataCenterApi.getTableInfo(tableName)
    if (infoRes?.pk) currentPk.value = infoRes.pk
  } catch (e) { /* 默认 id */ }

  // 一次性加载大量数据（对标旧前端 LIMIT 10000）
  await runQuery(`SELECT * FROM ${tableName} ORDER BY 1 DESC LIMIT 10000`)
}

// ===== 执行 SQL 查询 =====
async function runQuery(sql?: string) {
  const sqlToRun = sql || currentSql.value
  if (!sqlToRun?.trim()) { warning('请输入 SQL 语句'); return }

  currentSql.value = sqlToRun
  queryLoading.value = true
  queryResult.value = []
  columns.value = []

  try {
    const res = await dataCenterApi.queryDb(sqlToRun)
    if (res?.status === 'error') {
      showError(res.message || '查询失败')
    } else {
      queryResult.value = res?.data || []
      columns.value = res?.columns || []
      if (!sql) {
        // 手动执行查询时，如果 SQL 不包含当前选中的表，清除表关联
        if (currentTable.value && !sqlToRun.toLowerCase().includes(currentTable.value.toLowerCase())) {
          currentTable.value = ''
          currentPk.value = 'id'
        }
        success(`查询成功: ${queryResult.value.length} 行`)
      }
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.response?.data?.message || '查询失败'
    showError(msg)
  } finally { queryLoading.value = false }
}

// ===== 手动执行 SQL =====
function handleManualRun() {
  runQuery()
}

// ===== 单元格编辑 =====
function startEditCell(row: any, col: string) {
  if (col === currentPk.value) return
  editState.value = { rowPk: row[currentPk.value], colKey: col }
  editInputValue.value = typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '')
}

async function confirmEditCell(row: any, col: string) {
  if (!editState.value) return
  const newVal = editInputValue.value
  if (newVal === String(row[col] ?? '')) { editState.value = null; return }
  try {
    await dataCenterApi.updateDbCell({
      table: currentTable.value,
      pk_col: currentPk.value,
      pk_val: row[currentPk.value],
      col,
      val: newVal,
    })
    success('单元格已更新')
    row[col] = newVal
  } catch (e) { showError('更新失败') }
  editState.value = null
}

function cancelEditCell() { editState.value = null }

// ===== 行删除 =====
async function deleteDbRow(row: any) {
  if (!currentTable.value || !currentPk.value) return
  const pkVal = row[currentPk.value]
  const ok = await confirm({
    title: '确认删除',
    content: `确定要删除 ${currentTable.value} 中 ${currentPk.value}=${pkVal} 的行吗？此操作不可撤销！`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await dataCenterApi.deleteDbRow({
      table: currentTable.value,
      pk_col: currentPk.value,
      pk_val: pkVal,
    })
    success('行已删除')
    const idx = queryResult.value.findIndex((r: any) => r[currentPk.value] === pkVal)
    if (idx >= 0) queryResult.value.splice(idx, 1)
  } catch (e) { showError('删除失败') }
}

// ===== 清空表 =====
async function truncateTable(tableName: string) {
  const ok = await confirm({
    title: '⚠️ 危险操作',
    content: `确定要清空表 ${tableName} 吗？所有数据将被永久删除，此操作不可撤销！`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await dataCenterApi.truncateDbTable(tableName)
    success(`表 ${tableName} 已清空`)
    fetchTables()
    if (currentTable.value === tableName) {
      queryResult.value = []
      columns.value = []
    }
  } catch (e) { showError('清空失败') }
}

// ===== 行详情 =====
function openRowDetail(row: any) {
  dbRowDetailItem.value = row
  showDbRowDetail.value = true
}

// ===== 清空查询结果 =====
function clearQuery() {
  currentSql.value = ''
  queryResult.value = []
  columns.value = []
  currentTable.value = ''
  currentPk.value = 'id'
  searchText.value = ''
  sqlPage.value = 1
}

onMounted(fetchTables)
onActivated(() => { if (tables.value.length === 0) fetchTables() })
</script>

<template>
  <v-alert type="warning" density="compact" variant="tonal" class="mb-4">
    此处直接操作生产数据库。如果您不熟悉 SQL 语法，请谨慎执行修改操作。
  </v-alert>

  <!-- 选择表 + SQL 输入 -->
  <v-card class="glass-card pa-4 mb-4">
    <v-autocomplete
      v-model="currentTable"
      :items="tableOptions"
      label="选择数据表"
      placeholder="🔍 选择数据表进行浏览..."
      density="compact"
      variant="outlined"
      clearable
      hide-details
      :loading="loading"
      class="mb-3"
      @update:model-value="(val: string | null) => { if (val) selectTable(val); else clearQuery() }"
    />

    <v-text-field
      v-model="currentSql"
      placeholder="输入 SQL 查询语句... (Ctrl+Enter 执行)"
      prepend-inner-icon="mdi-database-search"
      variant="outlined"
      density="comfortable"
      hide-details
      clearable
      style="font-family: monospace"
      @keydown.ctrl.enter="handleManualRun"
    >
      <template #append-inner>
        <v-btn color="primary" variant="flat" size="small" :loading="queryLoading" prepend-icon="mdi-play" @click="handleManualRun">
          执行
        </v-btn>
      </template>
    </v-text-field>
  </v-card>

  <!-- 执行结果 -->
  <v-card v-if="columns.length > 0 || queryResult.length > 0 || queryLoading" class="glass-card pa-4">
    <div class="d-flex align-center justify-space-between mb-3 flex-wrap ga-2">
      <div class="text-subtitle-2 font-weight-bold">执行结果</div>
      <div class="d-flex ga-2 align-center">
        <v-text-field
          v-model="searchText"
          density="compact"
          variant="outlined"
          placeholder="在结果中搜索..."
          prepend-inner-icon="mdi-magnify"
          clearable
          hide-details
          style="max-width: 250px"
        />
      </div>
    </div>

    <!-- 数据表格（支持拖拽滚动） -->
    <div class="dc-db-data-container">
      <v-skeleton-loader v-if="queryLoading" type="table@5" />
      <div v-else-if="paginatedData.length > 0" ref="tableWrapperRef" class="dc-db-table-wrapper" @mousedown="onDragMouseDown">
        <table class="dc-db-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col" class="text-left">{{ col }}</th>
              <th v-if="currentTable && currentPk" class="text-center" style="width:80px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in paginatedData" :key="ri">
              <td
                v-for="col in columns" :key="col"
                class="text-truncate dc-db-cell"
                :class="{ 'dc-db-cell--pk': col === currentPk }"
                style="max-width:250px"
                :title="row[col] === null ? '(NULL)' : (typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col]))"
                @dblclick="startEditCell(row, col)"
              >
                <template v-if="editState && editState.rowPk === row[currentPk] && editState.colKey === col">
                  <input
                    v-model="editInputValue"
                    class="dc-db-edit-input"
                    autofocus
                    @blur="confirmEditCell(row, col)"
                    @keydown.enter="confirmEditCell(row, col)"
                    @keydown.escape="cancelEditCell"
                  />
                </template>
                <template v-else>
                  <span v-if="row[col] === null" class="text-medium-emphasis">(NULL)</span>
                  <span v-else-if="typeof row[col] === 'object'">{{ JSON.stringify(row[col]) }}</span>
                  <span v-else>{{ row[col] }}</span>
                </template>
              </td>
              <td v-if="currentTable && currentPk" class="text-center">
                <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-eye-outline" @click="openRowDetail(row)">查看</v-btn>
                <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteDbRow(row)">删除</v-btn>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="text-center pa-4 text-body-2 text-medium-emphasis">无匹配结果</div>
    </div>

    <!-- 分页 + 统计 -->
    <div class="d-flex justify-space-between align-center mt-3">
      <span class="text-caption text-medium-emphasis">显示 {{ paginatedData.length }} / 共 {{ filteredData.length }} 条记录</span>
      <div class="d-flex ga-2 align-center">
        <v-btn variant="tonal" size="small" prepend-icon="mdi-chevron-left" :disabled="sqlPage <= 1" @click="sqlPage--">上一页</v-btn>
        <span class="text-caption">{{ sqlPage }} / {{ Math.max(1, Math.ceil(sqlTotal / sqlPageSize)) }}</span>
        <v-btn variant="tonal" size="small" append-icon="mdi-chevron-right" :disabled="sqlPage >= Math.ceil(sqlTotal / sqlPageSize)" @click="sqlPage++">下一页</v-btn>
      </div>
    </div>
  </v-card>

  <!-- 空状态 -->
  <div v-else class="text-center pa-8">
    <v-icon size="48" color="primary" class="mb-3">mdi-code-block-braces</v-icon>
    <div class="text-body-2 text-medium-emphasis">选择数据表或输入 SQL 查询</div>
  </div>

  <!-- 行详情弹窗 -->
  <v-dialog v-model="showDbRowDetail" max-width="640" scrollable>
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start color="primary">mdi-table-row</v-icon>行详情
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showDbRowDetail = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4" v-if="dbRowDetailItem">
        <div class="dc-detail-row" v-for="(val, key) in dbRowDetailItem" :key="String(key)">
          <span class="font-weight-medium">{{ key }}</span>
          <span class="text-body-2" style="word-break:break-all;max-width:70%;text-align:right">
            <span v-if="val === null" class="text-medium-emphasis">(NULL)</span>
            <span v-else-if="typeof val === 'object'">{{ JSON.stringify(val, null, 2) }}</span>
            <span v-else>{{ val }}</span>
          </span>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showDbRowDetail = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 数据库表格容器 — 拖拽滚动 */
.dc-db-data-container { overflow-x: auto; cursor: grab; }
.dc-db-data-container:active { cursor: grabbing; }
.dc-db-table-wrapper { overflow-x: auto; }
.dc-db-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dc-db-table th {
  padding: 8px 12px; text-align: left; font-weight: 600;
  border-bottom: 2px solid rgba(var(--v-theme-on-surface),0.12); white-space: nowrap;
  position: sticky; top: 0; background: rgb(var(--v-theme-surface)); z-index: 1;
}
.dc-db-table td {
  padding: 6px 12px; border-bottom: 1px solid rgba(var(--v-theme-on-surface),0.06);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px;
}
.dc-db-cell { cursor: default; }
.dc-db-cell:not(.dc-db-cell--pk) { cursor: text; }
.dc-db-edit-input {
  width: 100%; padding: 2px 4px; font-size: 13px;
  border: 1px solid rgb(var(--v-theme-primary)); border-radius: 4px;
  outline: none; background: rgba(var(--v-theme-surface),1);
}

/* 详情行 */
.dc-detail-row {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 8px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface),0.06);
}
</style>
