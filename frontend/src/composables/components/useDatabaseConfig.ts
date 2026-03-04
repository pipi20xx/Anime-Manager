import { ref, onMounted, reactive } from 'vue'
import { useMessage } from 'naive-ui'

export function useDatabaseConfig() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const testing = ref(false)

  const dbConfig = reactive({
    type: 'sqlite',
    host: 'localhost',
    port: 5432,
    user: 'postgres',
    password: '',
    database: 'anime_pro_matcher'
  })

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const data = await res.json()
      if (data.database) {
        Object.assign(dbConfig, data.database)
      }
    } catch (e) {
      message.error('获取配置失败')
    }
  }

  const testConnection = async () => {
    testing.value = true
    try {
      const res = await fetch(`${API_BASE}/api/system/db/test_connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dbConfig)
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success(data.message)
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('测试连接失败')
    } finally {
      testing.value = false
    }
  }

  const saveConfig = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/system/db/save_connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dbConfig)
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success(data.message)
        setTimeout(() => window.location.reload(), 1500)
      } else {
        message.error(data.message)
      }
    } catch (e) {
      message.error('保存失败')
    } finally {
      loading.value = false
    }
  }

  onMounted(fetchConfig)

  return {
    loading,
    testing,
    dbConfig,
    testConnection,
    saveConfig
  }
}
