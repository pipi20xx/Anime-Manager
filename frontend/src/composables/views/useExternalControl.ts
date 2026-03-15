import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useExternalControl() {
  const message = useMessage()
  const loading = ref(false)
  const logLoading = ref(false)
  
  // Environment
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
  const fullApiBase = computed(() => API_BASE.replace(/\/$/, '') + '/api')
  const webhookUrl = computed(() => `${window.location.origin}/api/webhook/cd2/file_notify`)
  const embyWebhookUrl = computed(() => `${window.location.origin}/api/webhook/emby`)

  // State
  const config = ref<any>({
    external_token: '',
    enable_api: true,
    api_logging: true
  })

  const logs = ref<any[]>([])
  const pagination = ref({
    page: 1,
    pageSize: 15,
    itemCount: 0
  })

  // Actions
  const fetchConfig = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const data = await res.json()
      config.value = {
        external_token: data.external_token || '',
        enable_api: data.enable_api !== undefined ? data.enable_api : true,
        api_logging: data.api_logging !== undefined ? data.api_logging : true
      }
      if (config.value.external_token) {
        localStorage.setItem('apm_external_token', config.value.external_token)
      }
    } catch (e) {
      message.error('加载配置失败')
    } finally {
      loading.value = false
    }
  }

  const fetchLogs = async () => {
    logLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/system/logs?module=API&limit=${pagination.value.pageSize}&offset=${(pagination.value.page - 1) * pagination.value.pageSize}`)
      const data = await res.json()
      logs.value = data
      // Simple logic for total count estimation or update if backend provides it
      // Currently mimicking original logic: if data length < pageSize, we are at end, else assume more
      pagination.value.itemCount = data.length < pagination.value.pageSize ? logs.value.length + ((pagination.value.page - 1) * pagination.value.pageSize) : 1000 
    } catch (e) {
      console.error('获取 API 日志失败', e)
    } finally {
      logLoading.value = false
    }
  }

  const saveConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const fullConfig = await res.json()
      Object.assign(fullConfig, config.value)
      
      await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fullConfig)
      })
      message.success('配置已更新')
    } catch (e) {
      message.error('保存失败')
    }
  }

  const generateToken = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let token = 'ak-'
    for (let i = 0; i < 28; i++) {
      token += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    config.value.external_token = token
    localStorage.setItem('apm_external_token', token)
    saveConfig()
  }

  const fallbackCopy = (text: string) => {
    const textArea = document.createElement("textarea")
    textArea.value = text
    textArea.style.position = "fixed"
    textArea.style.left = "-9999px"
    textArea.style.top = "0"
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    try {
      const successful = document.execCommand('copy')
      if (successful) {
        message.success('已复制到剪贴板 (兼容模式)')
      } else {
        message.error('复制失败，请手动选择复制')
      }
    } catch (err) {
      message.error('浏览器不支持自动复制')
    }
    document.body.removeChild(textArea)
  }

  const copyToClipboard = (text: string) => {
    if (!text) return
    
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        message.success('已复制到剪贴板')
      }).catch(() => {
        fallbackCopy(text)
      })
    } else {
      fallbackCopy(text)
    }
  }

  return {
    API_BASE,
    fullApiBase,
    webhookUrl,
    embyWebhookUrl,
    config,
    logs,
    pagination,
    loading,
    logLoading,
    fetchConfig,
    fetchLogs,
    saveConfig,
    generateToken,
    copyToClipboard
  }
}
