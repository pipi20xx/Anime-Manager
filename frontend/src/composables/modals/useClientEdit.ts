import { reactive, watch, ref, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useClientEdit(props: any, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const form = reactive({
    id: '',
    name: '',
    type: 'qbittorrent',
    url: '',
    username: '',
    password: '',
    api_token: '',
    default_save_path: '',
    mount_path: '',
    monitor_enabled: false,
    monitor_interval: 5,
    is_default: false
  })

  const testLoading = ref(false)
  const testResult = ref<{success: boolean, message: string} | null>(null)

  const typeOptions = computed(() => {
    const hasCd2 = (props.allClients || []).some((c: any) => c.type === 'cd2' && c.id !== form.id)
    return [
      { label: 'qBittorrent', value: 'qbittorrent' },
      { 
        label: 'CloudDrive2' + (hasCd2 ? ' (已存在，限配一个)' : ''), 
        value: 'cd2',
        disabled: hasCd2
      }
    ]
  })

  watch(() => props.show, (newVal) => {
    if (newVal) {
      testResult.value = null
      if (props.isNew) {
        form.id = ''
        form.name = '新客户端'
        form.type = 'qbittorrent'
        form.url = 'http://127.0.0.1:8080'
        form.username = 'admin'
        form.password = 'adminadmin'
        form.api_token = ''
        form.default_save_path = ''
        form.mount_path = ''
        form.monitor_enabled = true
        form.monitor_interval = 5
        form.is_default = false
      } else {
        Object.assign(form, JSON.parse(JSON.stringify(props.clientData)))
      }
    }
  })

  const handleTest = async () => {
    testLoading.value = true
    testResult.value = null
    try {
      const res = await fetch(`${API_BASE}/api/clients/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      })
      const data = await res.json()
      testResult.value = data
      if (data.success) {
        message.success('连接测试成功')
      } else {
        message.error('连接测试失败')
      }
    } catch (e) {
      testResult.value = { success: false, message: '请求失败，请检查后端' }
      message.error('请求失败')
    } finally {
      testLoading.value = false
    }
  }

  const handleSave = () => {
    emit('save', { ...form })
    emit('update:show', false)
  }

  return {
    form,
    testLoading,
    testResult,
    typeOptions,
    handleTest,
    handleSave
  }
}
