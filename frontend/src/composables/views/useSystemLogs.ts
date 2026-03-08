import { ref, reactive, watch, onMounted, h } from 'vue'
import { useMessage, useDialog, NButton, NIcon } from 'naive-ui'
import { DeleteSweepOutlined, CloseOutlined } from '@vicons/material'
import { getButtonStyle } from '../useButtonStyles'

export function useSystemLogs() {
  const message = useMessage()
  const dialog = useDialog()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const showConsole = ref(false)
  const data = ref([])

  const filters = reactive({
    module: null,
    level: null,
    keyword: ''
  })

  const pagination = reactive({
    page: 1,
    pageSize: 20,
    showSizePicker: true,
    pageSizes: [20, 50, 100, 200],
    itemCount: 0,
    prefix ({ itemCount }: any) { return `共 ${itemCount} 条` }
  })

  const fetchLogs = async () => {
    loading.value = true
    try {
      const params = new URLSearchParams({
        page: pagination.page.toString(),
        page_size: pagination.pageSize.toString(),
        ...(filters.module && { module: filters.module }),
        ...(filters.level && { level: filters.level }),
        ...(filters.keyword && { keyword: filters.keyword })
      })
      const res = await fetch(`${API_BASE}/api/system/logs?${params.toString()}`)
      const json = await res.json()
      data.value = json.items || []
      pagination.itemCount = json.total || 0
    } catch (e) {
      message.error('加载审计日志失败')
    } finally {
      loading.value = false
    }
  }

  const clearLogs = () => {
    dialog.warning({
      title: '清空审计日志',
      content: '这将彻底清空数据库中存储的所有历史操作记录，确定吗？',
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
        h(NButton, { ...getButtonStyle('dialogDanger'), onClick: async () => {
          await fetch(`${API_BASE}/api/system/logs`, { method: 'DELETE' })
          message.success('审计历史已清空')
          fetchLogs()
          dialog.destroyAll()
        } }, { default: () => '确认清空' })
      ])
    })
  }

  const exportLogs = () => {
    window.open(`${API_BASE}/api/system/logs/export`)
  }

  watch([() => filters.module, () => filters.level], () => {
    pagination.page = 1
    fetchLogs()
  })

  onMounted(fetchLogs)

  return {
    loading,
    showConsole,
    data,
    filters,
    pagination,
    fetchLogs,
    clearLogs,
    exportLogs
  }
}
