import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon,
  VideoFileOutlined as VideoIcon,
  DescriptionOutlined as FileIcon,
  SubtitlesOutlined as SubIcon
} from '@vicons/material'

// Types
export interface FileItem { name: string; path: string; is_dir: boolean; size: number; mtime: number; extension: string; }

export function useFileBrowserView() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // State
  const currentPath = ref('/')
  const parentPath = ref<string | null>(null)
  const items = ref<FileItem[]>([])
  const loading = ref(false)
  const recognizingPath = ref<string | null>(null)
  const availableRules = ref<any[]>([])
  const defaultTask = ref<any>(null)

  // --- Modals Visibility ---
  const showManualModal = ref(false)
  const showResultModal = ref(false)
  const showExecModal = ref(false)

  // --- Shared Data for Modals ---
  const selectedFile = ref<FileItem | null>(null)
  const recognitionData = ref<any>(null)
  const previewPath = ref('')
  const isRecogLoading = ref(false)
  const isRenaming = ref(false)

  const execLogs = ref<any[]>([])
  const scanningStatus = ref('')
  const isRunning = ref(false)
  const isDryRun = ref(true)
  const currentManualTask = ref<any>(null)

  // --- Clipboard & Extra Ops ---
  const clipboard = ref<{ path: string; name: string; type: 'copy' | 'move' } | null>(null)
  const showInfoModal = ref(false)
  const fileInfo = ref<any>(null)

  const breadcrumbParts = computed(() => {
    const pathStr = String(currentPath.value || '/')
    const parts = pathStr.split('/').filter(x => x)
    return parts.map((part, index) => {
      return {
        name: part,
        path: '/' + parts.slice(0, index + 1).join('/')
      }
    })
  })

  // --- Core Browser Functions ---
  const fetchFiles = async (path: string) => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/files/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      const data = await res.json()
      if (data.status === 'success') {
        currentPath.value = data.data.current_path
        parentPath.value = data.data.parent_path
        items.value = data.data.items
      }
    } catch (e) { message.error('加载失败') }
    finally { loading.value = false }
  }

  const deleteItem = async (path: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/files/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('已删除')
        fetchFiles(currentPath.value)
      } else {
        message.error('删除失败: ' + data.detail)
      }
    } catch (e) { message.error('删除失败') }
  }

  const copyToClipboard = (item: FileItem, type: 'copy' | 'move' = 'copy') => {
    clipboard.value = { path: item.path, name: item.name, type }
    message.info(`已${type === 'copy' ? '复制' : '剪切'}: ${item.name}`)
  }

  const pasteItem = async () => {
    if (!clipboard.value) return
    
    const src = clipboard.value.path
    const dst = (currentPath.value.endsWith('/') ? currentPath.value : currentPath.value + '/') + clipboard.value.name
    
    if (src === dst) {
      message.warning('源路径与目标路径相同')
      return
    }

    try {
      const endpoint = clipboard.value.type === 'copy' ? '/api/files/copy' : '/api/files/move'
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ src, dst })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('粘贴成功')
        if (clipboard.value.type === 'move') clipboard.value = null
        fetchFiles(currentPath.value)
      } else {
        message.error('粘贴失败: ' + data.detail)
      }
    } catch (e) { message.error('粘贴失败') }
  }

  const getFileInfo = async (path: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/files/info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      const data = await res.json()
      if (data.status === 'success') {
        fileInfo.value = data.data
        showInfoModal.value = true
      }
    } catch (e) { message.error('获取详情失败') }
  }

  const copyPath = (path: string) => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(path)
        .then(() => {
          message.success('路径已复制到剪贴板')
        })
        .catch(err => {
          console.error('Clipboard API failed, using fallback:', err)
          fallbackCopyText(path)
        })
    } else {
      fallbackCopyText(path)
    }
  }

  const fallbackCopyText = (text: string) => {
    const textArea = document.createElement("textarea")
    textArea.value = text
    textArea.style.position = "fixed"
    textArea.style.left = "-9999px"
    textArea.style.top = "0"
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    try {
      document.execCommand('copy')
      message.success('路径已复制到剪贴板 (兼容模式)')
    } catch (err) {
      console.error('Fallback copy failed:', err)
      message.error('复制失败，请手动复制')
    }
    document.body.removeChild(textArea)
  }

  const loadConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const cfg = await res.json()
      availableRules.value = cfg.rename_rules || []
      if (cfg.organize_tasks?.length > 0) {
        defaultTask.value = cfg.organize_tasks[0]
      }
    } catch (e) {}
  }

  // --- Recognition Actions ---
  const recognizeFile = async (item: FileItem, forcedParams: any = null) => {
    selectedFile.value = item
    previewPath.value = ''
    
    if (!forcedParams) {
      recognizingPath.value = item.path
      showResultModal.value = true
    }
    
    isRecogLoading.value = true
    try {
      const payload = { 
        filename: item.path, 
        forced_tmdb_id: forcedParams?.tmdb_id || undefined, 
        forced_type: forcedParams?.type || undefined, 
        forced_season: forcedParams?.season || undefined, 
        forced_episode: forcedParams?.episode || undefined,
        anime_priority: forcedParams?.anime_priority,
        offline_priority: forcedParams?.offline_priority,
        bangumi_priority: forcedParams?.bangumi_priority,
        bangumi_failover: forcedParams?.bangumi_failover,
        series_fingerprint: forcedParams?.series_fingerprint,
        batch_enhancement: forcedParams?.batch_enhancement,
        force_filename: forcedParams?.force_filename
      }
      const res = await fetch(`${API_BASE}/api/recognize`, {  
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify(payload) 
      })
      recognitionData.value = await res.json()
      
      // Preview
      if (availableRules.value.length > 0) {
        const resP = await fetch(`${API_BASE}/api/rename/preview`, { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ rule_id: availableRules.value[0].id, result_data: recognitionData.value })
        })
        const dataP = await resP.json()
        if (dataP.status === 'success') previewPath.value = dataP.new_path
        else previewPath.value = '预览失败: ' + (dataP.message || '规则不匹配')
      } else {
        previewPath.value = '未配置规则'
      }
    } catch (e) { message.error('识别出错') }
    finally { recognizingPath.value = null; isRecogLoading.value = false }
  }

  const handleRename = async () => {
    if (!selectedFile.value || !previewPath.value || previewPath.value.startsWith('预览失败')) {
      message.warning('无效的预览路径')
      return
    }
    
    // 1. 初始化执行状态
    execLogs.value = []
    scanningStatus.value = '正在准备执行重命名...'
    showResultModal.value = false
    showExecModal.value = true
    isDryRun.value = false
    isRunning.value = true

    try {
      const fullPath = selectedFile.value.path
      const currentDir = fullPath.substring(0, fullPath.lastIndexOf('/'))
      const targetAbs = (currentDir || '.').replace(/\/+$/, '') + '/' + previewPath.value
      
      const res = await fetch(`${API_BASE}/api/organize/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          items: [{ source: selectedFile.value.path, target: targetAbs, action: 'move' }], 
          conflict_mode: 'skip'
        })
      })
      
      if (res.ok) {
        await readStream(res)
        message.success('重命名完成')
        setTimeout(() => fetchFiles(currentPath.value), 1000)
      } else {
        message.error('执行失败')
      }
    } catch (e) {
      message.error('重命名过程出错')
    } finally {
      isRunning.value = false
      scanningStatus.value = ''
    }
  }

  // --- Shared Stream Reader ---
  const readStream = async (response: Response) => {
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const msg = JSON.parse(line)
          if (msg.type === 'scan') {
            scanningStatus.value = msg.path
          } else if (['item', 'skip', 'error', 'start'].includes(msg.type)) {
            // 补全 start 类型，确保“开始任务”日志能显示出来
            execLogs.value.push(msg)
          } else if (msg.type === 'finish') {
            scanningStatus.value = ''
            message.success(`任务完成: 处理了 ${msg.count} 个文件`)
          }
        } catch (e) {}
      }
    }
  }

  // --- Organize Actions ---
  const runManualOrganize = async (task: any) => {
    currentManualTask.value = task
    showManualModal.value = false
    showExecModal.value = true
    isDryRun.value = true
    isRunning.value = true
    execLogs.value = []
    
    try {
      const response = await fetch(`${API_BASE}/api/organize/stream_adhoc?dry_run=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...task, source_dir: currentPath.value })
      })
      await readStream(response)
    } catch (e) { message.error('任务中断') }
    finally { isRunning.value = false }
  }

  const runManualOrganizeBackground = async (task: any) => {
    try {
      const res = await fetch(`${API_BASE}/api/organize/start_background?dry_run=false`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...task, source_dir: currentPath.value })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('后台整理任务已启动')
        showManualModal.value = false
      } else {
        message.error('启动失败: ' + data.message)
      }
    } catch (e) { message.error('网络错误') }
  }

  const commitBatch = async () => {
    const items = execLogs.value.filter(l => l.type === 'item' && l.status === 'success')
    if (items.length === 0) {
      message.warning('没有可执行的项目')
      return
    }
    
    isDryRun.value = false
    isRunning.value = true
    execLogs.value = [] // 清空预览日志，准备显示执行日志
    
    try {
      const response = await fetch(`${API_BASE}/api/organize/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          items,
          conflict_mode: currentManualTask.value?.overwrite_mode ? 'overwrite' : 'skip' 
        })
      })
      
      if (response.ok) {
        await readStream(response)
        message.success('整理任务执行完毕')
        setTimeout(() => fetchFiles(currentPath.value), 500)
      } else {
        message.error('执行请求失败')
      }
    } catch (e) {
      message.error('执行过程出错')
    } finally {
      isRunning.value = false
    }
  }

  const getFileIcon = (item: FileItem) => {
    if (item.is_dir) return FolderIcon
    const ext = item.extension.toLowerCase()
    if (['.mp4', '.mkv', '.avi', '.mov', '.ts'].includes(ext)) return VideoIcon
    if (['.srt', '.ass', '.ssa'].includes(ext)) return SubIcon
    return FileIcon
  }

  return {
    API_BASE,
    currentPath,
    parentPath,
    items,
    loading,
    recognizingPath,
    availableRules,
    defaultTask,
    breadcrumbParts,
    showManualModal,
    showResultModal,
    showExecModal,
    selectedFile,
    recognitionData,
    previewPath,
    isRecogLoading,
    isRenaming,
    execLogs,
    scanningStatus,
    isRunning,
    isDryRun,
    currentManualTask,
    clipboard,
    showInfoModal,
    fileInfo,
    fetchFiles,
    deleteItem,
    copyToClipboard,
    pasteItem,
    getFileInfo,
    copyPath,
    loadConfig,
    recognizeFile,
    handleRename,
    runManualOrganize,
    runManualOrganizeBackground,
    commitBatch,
    getFileIcon
  }
}
