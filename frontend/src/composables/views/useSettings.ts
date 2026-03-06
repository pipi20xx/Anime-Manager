import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'

export function useSettings() {
  const message = useMessage()
  const loading = ref(false)
  const syncLoading = ref(false)
  const testTgLoading = ref(false)
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const config = ref<any>({
    tmdb_api_key: '',
    bangumi_token: '',
    bangumi_priority: false,
    bangumi_failover: true,
    http_proxy: '',
    proxy_services: { tmdb: false, bangumi: false, remote_rules: false },
    telegram: { bot_token: '', chat_id: '', enabled: false, notify_on_download: true, notify_on_organize: true },
    anime_priority: true,
    offline_priority: true,
    ai_config: {
      openai_base_url: 'http://localhost:11434/v1',
      openai_api_key: 'sk-xxx',
      openai_model: 'qwen2.5:1.5b'
    },
    batch_enhancement: false,
    custom_noise_words: [],
    remote_noise_urls: [],
    custom_release_groups: [],
    remote_group_urls: [],
    custom_render_words: [],
    remote_render_urls: [],
    custom_privileged_rules: [],
    remote_privileged_urls: [],
    rss_auto_refresh: true,
    rss_refresh_interval: 15,
    auto_clear_recognition: false,
    auto_clear_interval: 24,
    sub_auto_fill: false,
    sub_fill_interval: 12,
    rule_auto_update: false,
    rule_update_interval: 24,
    stalled_timeout_minutes: 0,
    stalled_monitor_interval: 30,
    health_check_enabled: true,
    health_check_interval: 30,
    emby_enabled: false,
    emby_url: '',
    emby_api_key: '',
    emby_username: '',
    emby_password: '',
    emby_user_id: ''
  })

  const clients = ref<any[]>([])
  const showClientModal = ref(false)
  const currentClient = ref<any>(null)
  const isNewClient = ref(false)

  const fetchAll = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const data = await res.json()
      config.value = data
      
      if (!config.value.telegram) {
        config.value.telegram = { 
          bot_token: '', chat_id: '', enabled: false, 
          notify_on_sub_add: true, notify_on_sub_del: true, notify_on_sub_push: true, 
          notify_on_rule_push: true, notify_on_organize: true, 
          notify_on_strm_finish: true, notify_on_sub_complete: true
        }
      } else {
        const tg = config.value.telegram
        if (tg.notify_on_sub_add === undefined) tg.notify_on_sub_add = true
        if (tg.notify_on_sub_push === undefined) tg.notify_on_sub_push = true
        if (tg.notify_on_rule_push === undefined) tg.notify_on_rule_push = true
        if (tg.notify_on_organize === undefined) tg.notify_on_organize = true
        if (tg.notify_on_strm_finish === undefined) tg.notify_on_strm_finish = true
        if (tg.notify_on_strm_link === undefined) tg.notify_on_strm_link = true
        if (tg.notify_on_sub_del === undefined) tg.notify_on_sub_del = true
        if (tg.notify_on_sub_complete === undefined) tg.notify_on_sub_complete = true
      }

      if (!config.value.emby_enabled) {
        config.value.emby_enabled = false
      }
      if (!config.value.emby_url) {
        config.value.emby_url = ''
      }
      if (!config.value.emby_api_key) {
        config.value.emby_api_key = ''
      }
      if (!config.value.emby_username) {
        config.value.emby_username = ''
      }
      if (!config.value.emby_password) {
        config.value.emby_password = ''
      }
      if (!config.value.emby_user_id) {
        config.value.emby_user_id = ''
      }
      
      const clientRes = await fetch(`${API_BASE}/api/clients`)
      clients.value = await clientRes.json()
    } catch (e) {
      message.error('加载配置失败')
    } finally {
      loading.value = false
    }
  }

  const testTelegram = async () => {
    if (!config.value.telegram?.enabled) {
      message.warning('请先开启 Telegram 通知开关并保存')
      return
    }
    testTgLoading.value = true
    try {
      await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config.value)
      })
      
      const res = await fetch(`${API_BASE}/api/system/telegram/test`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        message.success('测试消息已发送，请检查 Telegram')
      } else {
        message.error(data.detail || '发送失败')
      }
    } catch (e) {
      message.error('请求失败')
    } finally {
      testTgLoading.value = false
    }
  }

  const saveClientsList = async () => {
    try {
      await fetch(`${API_BASE}/api/clients`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(clients.value)
      })
      message.success('客户端列表已更新')
      fetchAll()
    } catch (e) {
      message.error('保存客户端失败')
    }
  }

  const openAddClient = () => {
    currentClient.value = null
    isNewClient.value = true
    showClientModal.value = true
  }

  const openEditClient = (client: any) => {
    currentClient.value = client
    isNewClient.value = false
    showClientModal.value = true
  }

  const handleClientSave = (clientData: any) => {
    if (clientData.type === 'cd2') {
      const existingCd2 = clients.value.find(c => c.type === 'cd2' && c.id !== clientData.id)
      if (existingCd2) {
        message.error(`系统中已存在 CD2 客户端 "${existingCd2.name}"，目前仅支持配置一个 CD2 实例。`)
        return
      }
    }

    if (isNewClient.value) {
      clients.value.push(clientData)
    } else {
      const idx = clients.value.findIndex(c => c.id === clientData.id)
      if (idx !== -1) clients.value[idx] = clientData
    }
    saveClientsList()
  }

  const handleDeleteClient = (id: string) => {
    clients.value = clients.value.filter(c => c.id !== id)
    saveClientsList()
  }

  const saveAll = async () => {
    loading.value = true
    try {
      await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config.value)
      })

      message.success('配置已保存')
    } catch (e) {
      message.error('保存失败')
    } finally {
      loading.value = false
    }
  }

  const refreshRemoteRules = async () => {
    syncLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/refresh_remote_rules`, { method: 'POST' })
      const data = await res.json()
      message.success(data.message || '同步完成')
    } catch (e) {
      message.error('同步失败')
    } finally {
      syncLoading.value = false
    }
  }

  onMounted(fetchAll)

  return {
    loading,
    syncLoading,
    testTgLoading,
    config,
    clients,
    showClientModal,
    currentClient,
    isNewClient,
    fetchAll,
    testTelegram,
    saveClientsList,
    openAddClient,
    openEditClient,
    handleClientSave,
    handleDeleteClient,
    saveAll,
    refreshRemoteRules
  }
}
