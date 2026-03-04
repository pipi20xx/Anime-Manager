import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'

export function useStrmGeneratorView() {
  const message = useMessage()
  const dialog = useDialog()
  const tasks = ref<any[]>([])
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // --- Modal State ---
  const showModal = ref(false)
  const editingTask = ref<any>(null)
  const editingIndex = ref(-1)

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/strm/tasks`)
      tasks.value = await res.json()
    } catch (e) { message.error('获取任务失败') }
  }

  const duplicateTask = async (index: number) => {
    try {
      const configRes = await fetch(`${API_BASE}/api/config`)
      const config = await configRes.json()
      const newTasks = [...(config.strm_tasks || [])]
      
      if (index >= 0 && index < newTasks.length) {
        const taskToCopy = { ...newTasks[index] }
        taskToCopy.id = 'strm_' + Date.now()
        taskToCopy.name = taskToCopy.name + ' (副本)'
        
        newTasks.splice(index + 1, 0, taskToCopy)
        
        await fetch(`${API_BASE}/api/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...config, strm_tasks: newTasks })
        })
        
        message.success('任务已复制')
        fetchTasks()
      }
    } catch (e) { message.error('复制失败') }
  }

  const openEdit = (index: number = -1) => {
    editingIndex.value = index
    if (index === -1) {
      editingTask.value = {
        id: 'strm_' + Date.now(), name: '新 STRM 任务', source_path: '', target_path: '',
        content_prefix: '', content_suffix: '', url_encode: false, copy_meta: true,
        clean_target: false, clean_empty_dirs: true, overwrite_strm: true,
        overwrite_meta: false, 
        target_extensions: ['.mp4', '.mkv', '.ts', '.iso', '.rmvb', '.avi', '.mov', '.mpeg', '.mpg', '.wmv', '.3gp', '.asf', '.m4v', '.flv', '.m2ts', '.tp', '.f4v'],
        meta_extensions: ['.nfo', '.jpg', '.jpeg', '.png', '.svg', '.ass', '.srt', '.sup', '.mp3', '.flac', '.wav', '.aac', '.webp', '.ssa', '.sub'],
        cd2_mapping_path: '', 
        incremental_enabled: false, incremental_mode: 'realtime',
        scheduler_enabled: false, scheduler_interval: 3600,
        monitor_interval: 10, process_interval: 0,
        webhook_enabled: true
      }
    } else {
      editingTask.value = { ...tasks.value[index] }
    }
    showModal.value = true
  }

  const handleSaveTask = async (formData: any) => {
    try {
      const configRes = await fetch(`${API_BASE}/api/config`)
      const config = await configRes.json()
      let strmTasks = config.strm_tasks || []
      
      // 统一字段名映射 (后端使用的是 source_dir 和 target_dir)
      const payload = { ...formData, source_dir: formData.source_path, target_dir: formData.target_path }
      
      if (editingIndex.value === -1) strmTasks.push(payload)
      else {
        const idx = strmTasks.findIndex((t: any) => t.id === formData.id)
        if (idx !== -1) strmTasks[idx] = payload
      }
      
      await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, strm_tasks: strmTasks })
      })
      
      message.success('保存成功')
      showModal.value = false
      fetchTasks()
    } catch (e) { message.error('保存失败') }
  }

  const runTask = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/strm/run/${taskId}`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('任务已启动，请观察控制台日志')
      } else {
        message.error('启动失败: ' + data.message)
      }
    } catch (e) { message.error('请求失败') }
  }

  const deleteTask = (index: number) => {
    dialog.warning({
      title: '删除任务',
      content: '确定要删除此 STRM 任务吗？',
      positiveText: '确定',
      onPositiveClick: async () => {
        const configRes = await fetch(`${API_BASE}/api/config`)
        const config = await configRes.json()
        config.strm_tasks.splice(index, 1)
        await fetch(`${API_BASE}/api/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        })
        fetchTasks()
      }
    })
  }

  const toggleTaskMonitor = async (task: any, type: 'incremental' | 'scheduler') => {
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

    // 保存全局配置
    try {
      const configRes = await fetch(`${API_BASE}/api/config`)
      const config = await configRes.json()
      const idx = config.strm_tasks.findIndex((t: any) => t.id === task.id)
      if (idx !== -1) {
        config.strm_tasks[idx] = { ...task }
        await fetch(`${API_BASE}/api/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        })
        fetchTasks()
      }
    } catch (e) { message.error('快速保存失败') }
  }

  return {
    API_BASE,
    tasks,
    showModal,
    editingTask,
    editingIndex,
    fetchTasks,
    duplicateTask,
    openEdit,
    handleSaveTask,
    runTask,
    deleteTask,
    toggleTaskMonitor
  }
}
