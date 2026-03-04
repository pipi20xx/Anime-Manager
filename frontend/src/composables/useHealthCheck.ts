import { ref, onMounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { healthApi, type HealthCheckConfig } from '../api/health'
import { useSettings } from './views/useSettings'

export function useHealthCheck() {
  const message = useMessage()
  const { config, saveAll } = useSettings()
  const loading = ref(false)
  const configs = ref<HealthCheckConfig[]>([])
  const showModal = ref(false)
  const editingConfig = ref<HealthCheckConfig>({
    name: '',
    file_path: '',
    file_url: '',
    enabled: true
  })

  const fetchConfigs = async () => {
    loading.value = true
    try {
      const res = await healthApi.getConfigs()
      configs.value = res.data
    } catch (e) {
      message.error('获取配置失败')
    } finally {
      loading.value = false
    }
  }

  const openAdd = () => {
    editingConfig.value = { name: '', file_path: '', file_url: '', enabled: true }
    showModal.value = true
  }

  const openEdit = (config: HealthCheckConfig) => {
    editingConfig.value = { ...config }
    showModal.value = true
  }

  const saveConfig = async () => {
    try {
      if (editingConfig.value.id) {
        await healthApi.updateConfig(editingConfig.value.id, editingConfig.value)
        message.success('更新成功')
      } else {
        await healthApi.createConfig(editingConfig.value)
        message.success('创建成功')
      }
      showModal.value = false
      fetchConfigs()
    } catch (e) {
      message.error('保存失败')
    }
  }

  const deleteConfig = async (id: number) => {
    try {
      await healthApi.deleteConfig(id)
      message.success('已删除')
      fetchConfigs()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const startCheck = async (id: number) => {
    try {
      await healthApi.triggerCheck(id)
      message.info('检测已在后台启动')
      setTimeout(fetchConfigs, 2000)
    } catch (e) {
      message.error('触发检测失败')
    }
  }

  const checkAll = async () => {
    try {
      await healthApi.triggerCheckAll()
      message.info('全局检测已启动')
      setTimeout(fetchConfigs, 3000)
    } catch (e) {
      message.error('触发检测失败')
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '从无'
    const d = new Date(dateStr)
    const pad = (n: number) => n.toString().padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }

  const getStatusInfo = (status: string = 'Unknown') => {
    const isOk = status === 'OK'
    const isFailed = status.includes('Failed')
    
    let displayStatus = status
    if (isOk) displayStatus = '正常'
    else if (isFailed) {
      const match = status.match(/Failed \((.+)\)/)
      displayStatus = match ? match[1] : '检测失败'
    } else if (status === 'Unknown') {
      displayStatus = '待检测'
    }

    return {
      type: isOk ? 'success' : (isFailed ? 'error' : 'default') as any,
      text: displayStatus,
      isOk,
      isFailed
    }
  }

  onMounted(fetchConfigs)

  return {
    config,
    saveAll,
    loading,
    configs,
    showModal,
    editingConfig,
    fetchConfigs,
    openAdd,
    openEdit,
    saveConfig,
    deleteConfig,
    startCheck,
    checkAll,
    formatDate,
    getStatusInfo
  }
}
