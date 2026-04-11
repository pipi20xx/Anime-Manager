import { ref, onMounted, computed, h } from 'vue'
import { useMessage, NInput, NPopover } from 'naive-ui'

export function useDatabase() {
  const message = useMessage()
  const activeTab = ref('metadata')
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // --- SQL Lab Logic ---
  const tables = ref<any[]>([])
  const loading = ref(false)
  const queryLoading = ref(false)
  const currentSql = ref('')
  const queryResult = ref<any[]>([])
  const columns = ref<any[]>([])
  const searchText = ref('')

  const currentTable = ref('')
  const currentPk = ref('')
  const editState = ref<{ rowPk: any, colKey: string | null }>({ rowPk: null, colKey: null })

  const scrollX = computed(() => {
    return columns.value.length * 200 + (currentPk.value ? 100 : 0)
  })

  const filteredData = computed(() => {
    if (!searchText.value) return queryResult.value
    const lowerSearch = searchText.value.toLowerCase()
    return queryResult.value.filter(row => {
      return Object.values(row).some(val => 
        String(val).toLowerCase().includes(lowerSearch)
      )
    })
  })

  const fetchTables = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/system/db/tables`)
      const data = await res.json()
      if (data.status === 'success') {
        tables.value = data.tables
      }
    } catch (e) { message.error('获取表结构失败') }
    finally { loading.value = false }
  }

  const tableOptions = computed(() => {
    return tables.value.map(t => ({
      label: `${t.name} (${t.count}行)`,
      value: t.name
    }))
  })

  const handleUpdate = async (row: any, colKey: string, val: string) => {
      editState.value = { rowPk: null, colKey: null }
      if (val === String(row[colKey])) return

      try {
          const res = await fetch(`${API_BASE}/api/system/db/update_cell`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  table: currentTable.value,
                  pk_col: currentPk.value,
                  pk_val: row[currentPk.value],
                  col: colKey,
                  val: val
              })
          })
          const data = await res.json()
          if (data.status === 'success') {
              message.success('更新成功')
              row[colKey] = val 
          } else {
              message.error('更新失败: ' + data.message)
              runQuery()
          }
      } catch (e) { message.error('请求失败') }
  }

  const deleteRow = async (row: any) => {
      if (!currentTable.value || !currentPk.value) return
      try {
          const res = await fetch(`${API_BASE}/api/system/db/delete_row`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  table: currentTable.value,
                  pk_col: currentPk.value,
                  pk_val: row[currentPk.value]
              })
          })
          const data = await res.json()
          if (data.status === 'success') {
              message.success('删除成功')
              runQuery()
          } else {
              message.error('删除失败: ' + data.message)
          }
      } catch (e) { message.error('请求失败') }
  }

  const runQuery = async (sql?: string) => {
    const sqlToRun = sql || currentSql.value
    if (!sqlToRun) return
    
    currentSql.value = sqlToRun
    queryLoading.value = true
    queryResult.value = []
    columns.value = []
    
    try {
      const res = await fetch(`${API_BASE}/api/system/db/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: sqlToRun })
      })
      const data = await res.json()
      
      if (data.status === 'success') {
        queryResult.value = data.data
        
        const formatVal = (val: any) => {
            if (val === null) return '(NULL)'
            if (typeof val === 'object') return JSON.stringify(val)
            return String(val)
        }

        if (data.columns && data.columns.length > 0) {
          // Columns logic is mainly for DataTable rendering which is in the component
          // But we can prep the raw column names here
          columns.value = data.columns 
        }
        message.success(`查询成功: ${data.data.length} 行`)
      } else { message.error('查询错误: ' + data.message) }
    } catch (e) { message.error('请求失败') }
    finally { queryLoading.value = false }
  }

  const selectTable = async (tableName: string) => {
    currentTable.value = tableName
    currentPk.value = ''
    try {
        const res = await fetch(`${API_BASE}/api/system/db/table_info/${tableName}`)
        const data = await res.json()
        if (data.status === 'success' && data.pk) { currentPk.value = data.pk }
    } catch (e) {}
    runQuery(`SELECT * FROM ${tableName} ORDER BY 1 DESC LIMIT 10000`)
  }

  const handleManualRun = () => {
      if (currentTable.value && !currentSql.value.toLowerCase().includes(currentTable.value.toLowerCase())) {
          currentTable.value = ''; currentPk.value = ''
      }
      runQuery()
  }

  onMounted(fetchTables)

  return {
    activeTab,
    tables,
    loading,
    queryLoading,
    currentSql,
    queryResult,
    columns,
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
    runQuery,
    selectTable,
    handleManualRun
  }
}
