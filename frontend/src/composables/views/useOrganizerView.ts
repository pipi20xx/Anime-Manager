import { ref, watch, onMounted, onUnmounted, h } from 'vue'
import { useMessage, useDialog, NButton, NIcon } from 'naive-ui'
import { DeleteOutlined, PreviewOutlined, PlayArrowOutlined, CloseOutlined } from '@vicons/material'

export function useOrganizerView() {
  const message = useMessage()
  const dialog = useDialog()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const rules = ref<any[]>([])
  const tasks = ref<any[]>([])
  const loading = ref(false)

  const showRuleModal = ref(false)
  const editingRule = ref<any>(null)
  const editingRuleIndex = ref(-1)

  const showTaskModal = ref(false)
  const editingTask = ref<any>(null)
  const editingTaskIndex = ref(-1)

  const showExecModal = ref(false)
  const isRunning = ref(false)
  const isDryRun = ref(true)
  const execLogs = ref<any[]>([])
  const scanningStatus = ref('')
  const abortController = ref<AbortController | null>(null)
  const isSwitchingBackground = ref(false)

  const backgroundTasks = ref<any[]>([])
  let bgTaskPollTimer: ReturnType<typeof setInterval> | null = null

  const fetchBackgroundTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/background_tasks`)
      backgroundTasks.value = await res.json()
    } catch (e) {}
  }

  const stopBackgroundTask = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/stop?task_id=${taskId}`)
      const data = await res.json()
      if (data.status === 'success') {
        message.success('已发送停止指令')
        await fetchBackgroundTasks()
      }
    } catch (e) { message.error('停止失败') }
  }

  const deleteBackgroundTask = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/background_tasks/${taskId}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('任务记录已删除')
        await fetchBackgroundTasks()
      }
    } catch (e) { message.error('删除失败') }
  }

  const startBgTaskPolling = () => {
    if (bgTaskPollTimer) return
    fetchBackgroundTasks()
    bgTaskPollTimer = setInterval(fetchBackgroundTasks, 3000)
  }

  const stopBgTaskPolling = () => {
    if (bgTaskPollTimer) {
      clearInterval(bgTaskPollTimer)
      bgTaskPollTimer = null
    }
  }

  // --- Data Actions ---
  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const data = await res.json()
      rules.value = data.rename_rules || []
      tasks.value = data.organize_tasks || []
    } catch (e) { message.error('加载配置失败') }
  }

  const saveConfig = async () => {
    loading.value = true
    try {
      await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rename_rules: rules.value, organize_tasks: tasks.value })
      })
      message.success('配置已成功同步')
    } catch (e) { message.error('保存失败') }
    finally { loading.value = false }
  }

  // --- Rule Logic ---
  const openEditRule = (index: number = -1) => {
    editingRuleIndex.value = index
    editingRule.value = index === -1 ? { id: 'rule_' + Date.now(), name: '新重命名规则', movie_pattern: '', tv_pattern: '' } : { ...rules.value[index] }
    showRuleModal.value = true
  }

  const handleSaveRule = (data: any) => {
    if (editingRuleIndex.value === -1) rules.value.push(data)
    else rules.value[editingRuleIndex.value] = data
    showRuleModal.value = false
    saveConfig()
  }

  const deleteRule = (index: number) => {
    dialog.warning({
      title: '确认删除规则', 
      content: '确定要删除这条规则吗？',
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, {
          onClick: () => dialog.destroyAll()
        }, { icon: () => h(NIcon, null, { default: () => h(CloseOutlined) }), default: () => '取消' }),
        h(NButton, {
          type: 'warning',
          onClick: () => { rules.value.splice(index, 1); saveConfig(); dialog.destroyAll() }
        }, { icon: () => h(NIcon, null, { default: () => h(DeleteOutlined) }), default: () => '确认' })
      ])
    })
  }

  const duplicateRule = (index: number) => {
    const newRule = { ...rules.value[index] }
    newRule.id = 'rule_' + Date.now()
    newRule.name = newRule.name + ' (副本)'
    rules.value.splice(index + 1, 0, newRule)
    saveConfig()
    message.success('规则已复制')
  }

  // --- Task Logic ---
  const openEditTask = (index: number = -1) => {
    editingTaskIndex.value = index
    editingTask.value = index === -1 ? {
      id: 'task_' + Date.now(), name: '新整理任务', rule_id: rules.value[0]?.id || '',
      source_dir: '', target_dir: '', action_type: 'move', overwrite_mode: false,
      anime_priority: true, 
      incremental_enabled: false, incremental_mode: 'realtime', 
      scheduler_enabled: false, scheduler_interval: 3600,
      monitor_interval: 10, process_interval: 0,
      ignore_file_regex: [], ignore_dir_regex: [], trigger_strm: false
    } : { ...tasks.value[index] }
    showTaskModal.value = true
  }

  const handleSaveTask = (data: any) => {
    if (editingTaskIndex.value === -1) tasks.value.push(data)
    else tasks.value[editingTaskIndex.value] = data
    showTaskModal.value = false
    saveConfig()
  }

  const deleteTask = (index: number) => {
    dialog.warning({
      title: '确认删除任务', 
      content: `确定要删除任务 "${tasks.value[index].name}" 吗？`,
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, {
          onClick: () => dialog.destroyAll()
        }, { icon: () => h(NIcon, null, { default: () => h(CloseOutlined) }), default: () => '取消' }),
        h(NButton, {
          type: 'warning',
          onClick: () => { tasks.value.splice(index, 1); saveConfig(); dialog.destroyAll() }
        }, { icon: () => h(NIcon, null, { default: () => h(DeleteOutlined) }), default: () => '确认' })
      ])
    })
  }

  const duplicateTask = (index: number) => {
    const newTask = { ...tasks.value[index] }
    newTask.id = 'task_' + Date.now()
    newTask.name = newTask.name + ' (副本)'
    tasks.value.splice(index + 1, 0, newTask)
    saveConfig()
    message.success('任务已复制')
  }

  // --- 快速切换监控状态 ---
  const toggleTaskMonitor = (task: any, type: 'incremental' | 'scheduler') => {
    // 数据格式标准化 (兼容旧数据)
    if (task.monitor_mode) {
      if (task.monitor_mode === 'realtime' || task.monitor_mode === 'polling') {
        task.incremental_enabled = true
        task.incremental_mode = task.monitor_mode
      } else if (task.monitor_mode === 'scheduled') {
        task.scheduler_enabled = true
      }
      delete task.monitor_mode
    }

    if (type === 'incremental') {
      task.incremental_enabled = !task.incremental_enabled
      if (task.incremental_enabled && !task.incremental_mode) task.incremental_mode = 'realtime'
      message.info(`${task.name} 实时监控已${task.incremental_enabled ? '开启' : '关闭'}`)
    } else {
      task.scheduler_enabled = !task.scheduler_enabled
      if (task.scheduler_enabled && !task.scheduler_interval) task.scheduler_interval = 3600
      message.info(`${task.name} 定时扫描已${task.scheduler_enabled ? '开启' : '关闭'}`)
    }
    saveConfig()
  }

  // --- Execution Actions ---
  const runTask = async (task: any, dryRun = true) => {
    if (abortController.value) abortController.value.abort()
    abortController.value = new AbortController()
    
    editingTask.value = task; isDryRun.value = dryRun; execLogs.value = []; scanningStatus.value = '';
    showExecModal.value = true; isRunning.value = true
    
    try {
      const response = await fetch(`${API_BASE}/api/organize/stream?task_id=${task.id}&dry_run=${dryRun}`, {
        signal: abortController.value.signal
      })
      const reader = response.body!.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const msg = JSON.parse(line)
            if (msg.type === 'scan') scanningStatus.value = msg.path
            else if (['item', 'skip', 'error', 'start'].includes(msg.type)) execLogs.value.push(msg)
            else if (msg.type === 'finish') { scanningStatus.value = ''; message.success(`完成: 处理 ${msg.count} 项`) }
          } catch (e) {}
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        if (!isSwitchingBackground.value) {
          execLogs.value.push({ type: 'error', message: '用户已终止任务' })
        }
      } else {
        message.error('执行出错: ' + e.message)
      }
    } finally { isRunning.value = false; abortController.value = null; isSwitchingBackground.value = false }
  }

  // Watch for modal close to abort
  watch(showExecModal, (val) => {
    if (!val && isRunning.value && abortController.value) {
      abortController.value.abort()
      message.warning('任务已在后台终止')
    }
  })

  const commitBatch = async () => {
    const items = execLogs.value.filter(l => l.type === 'item' && l.status === 'success')
    if (items.length === 0) return
    isDryRun.value = false; isRunning.value = true; execLogs.value = []
    try {
      const res = await fetch(`${API_BASE}/api/organize/execute`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items, conflict_mode: editingTask.value?.overwrite_mode ? 'overwrite' : 'skip' })
      })
      const reader = res.body!.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const msg = JSON.parse(line)
            if (['item', 'error', 'start', 'finish'].includes(msg.type)) execLogs.value.push(msg)
          } catch (e) {}
        }
      }
      message.success('执行完毕'); fetchConfig()
    } finally { isRunning.value = false }
  }

  const requestRunTask = (task: any) => {
    dialog.info({
      title: '启动整理任务',
      content: `您希望如何运行任务 "${task.name}"？`,
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, {
          onClick: () => { runTask(task, true); dialog.destroyAll() }
        }, { icon: () => h(NIcon, null, { default: () => h(PreviewOutlined) }), default: () => '预览并手动执行' }),
        h(NButton, {
          type: 'primary',
          onClick: async () => {
            try {
              const res = await fetch(`${API_BASE}/api/organize/start_background?dry_run=false`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(task)
              })
              const data = await res.json()
              if (data.status === 'success') message.success('任务已在后台启动')
              else message.error('启动失败: ' + data.message)
            } catch (e) { message.error('网络错误') }
            dialog.destroyAll()
          }
        }, { icon: () => h(NIcon, null, { default: () => h(PlayArrowOutlined) }), default: () => '后台静默执行' })
      ])
    })
  }

  const requestCommitBatch = () => {
    commitBatch()
  }

  return {
    API_BASE,
    rules,
    tasks,
    loading,
    showRuleModal,
    editingRule,
    editingRuleIndex,
    showTaskModal,
    editingTask,
    editingTaskIndex,
    showExecModal,
    isRunning,
    isDryRun,
    execLogs,
    scanningStatus,
    backgroundTasks,
    fetchBackgroundTasks,
    stopBackgroundTask,
    deleteBackgroundTask,
    startBgTaskPolling,
    stopBgTaskPolling,
    fetchConfig,
    saveConfig,
    openEditRule,
    handleSaveRule,
    deleteRule,
    duplicateRule,
    openEditTask,
    handleSaveTask,
    deleteTask,
    duplicateTask,
    toggleTaskMonitor,
    runTask,
    requestRunTask,
    requestCommitBatch
  }
}
