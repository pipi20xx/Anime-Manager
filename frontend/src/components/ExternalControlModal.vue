<script setup lang="ts">
import { ref, onMounted, computed, h, watch } from 'vue'
import { dataTableThemeOverrides } from '../store/appearanceStore'
import AppGlassModal from './AppGlassModal.vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NForm, NFormItem, 
  NDivider, NGrid, NGi, useMessage, NAlert, NSpin, NTag,
  NDataTable, NSwitch, NTabs, NTabPane, NList, NListItem, NThing
} from 'naive-ui'
import AppTextField from './AppTextField.vue'
import {
  ApiOutlined as ApiIcon,
  ContentCopyOutlined as CopyIcon,
  RefreshOutlined as RefreshIcon,
  LinkOutlined as WebhookIcon,
  HistoryOutlined as LogIcon,
  SettingsOutlined as SettingIcon,
  DescriptionOutlined as DocIcon,
  VpnKeyOutlined as KeyIcon,
  CloseOutlined as CloseIcon
} from '@vicons/material'
import { getButtonStyle } from '../composables/useButtonStyles'
import { docsTheme } from '../store/themeStore'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const message = useMessage()
const loading = ref(false)
const logLoading = ref(false)
const activeTab = ref('keys')
const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)
const fullApiBase = computed(() => API_BASE.replace(/\/$/, '') + '/api')

const config = ref<any>({
  external_token: '',
  enable_api: true,
  api_logging: true
})

const logs = ref<any[]>([])
const pagination = ref({
  page: 1,
  pageSize: 10,
  itemCount: 0
})

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
    message.success('配置已保存')
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
  saveConfig()
}

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    message.success('已复制到剪贴板')
  })
}

const showLogDetail = ref(false)
const currentLogDetail = ref('')

const logColumns = [
  { title: '时间', key: 'timestamp', width: 160, render: (row: any) => row.timestamp.replace('T', ' ').split('.')[0] },
  { title: '方法', key: 'action', width: 80, render: (row: any) => h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => row.action }) },
  { title: '接口', key: 'message', render: (row: any) => h('span', { style: 'font-family: monospace; font-size: 11px' }, row.message) },
  { 
    title: '详情', 
    key: 'details',
    width: 60,
    render: (row: any) => {
      if (!row.details) return '-'
      return h(NButton, {
        size: 'tiny', quaternary: true, circle: true, type: 'primary',
        onClick: () => {
          try {
            const parsed = JSON.parse(row.details)
            currentLogDetail.value = JSON.stringify(parsed, null, 2)
          } catch {
            currentLogDetail.value = row.details
          }
          showLogDetail.value = true
        }
      }, { default: () => h(NIcon, null, { default: () => h(DocIcon) }) })
    }
  }
]

watch(() => props.show, (val) => {
  if (val) {
    fetchConfig()
    fetchLogs()
  }
})

const webhookUrl = computed(() => `${window.location.origin}/api/webhook/cd2/file_notify`)
const embyWebhookUrl = computed(() => `${window.location.origin}/api/webhook/emby`)
</script>

<template>
  <AppGlassModal
    appearance-key="external-control-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    title="API 外部控制中心"
    style="width: 1000px;"
    class="external-modal"
  >
    <template #header-extra>
      <n-button v-bind="getButtonStyle('iconPrimary')" @click="emit('update:show', false)">
        <template #icon><n-icon><CloseIcon /></n-icon></template>
      </n-button>
    </template>

    <n-spin :show="loading">
      <n-tabs type="line" animated size="large" v-model:value="activeTab">
        <!-- API 密钥 -->
        <n-tab-pane name="keys" tab="API 密钥">
          <div class="modal-tab-content">
            <n-form-item>
              <AppTextField v-model:value="config.external_token" label="访问令牌 (Bearer Token)" type="password" readonly placeholder="尚未生成密钥">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" @click="copyToClipboard(config.external_token)"><template #icon><n-icon><CopyIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>
            <n-button type="primary" @click="generateToken" style="width: 100%; margin-top: 12px">重新生成</n-button>
            <n-divider title-placement="left">Webhook</n-divider>
            <n-form-item>
              <AppTextField :value="webhookUrl" label="CloudDrive2 通知地址" readonly>
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" @click="copyToClipboard(webhookUrl)">复制</n-button>
                </template>
              </AppTextField>
            </n-form-item>

            <n-divider title-placement="left">Emby Webhook</n-divider>
            <n-alert title="Emby 配置指引" type="info" style="margin-bottom: 12px">
              在 Emby 设置的 <b>控制面板 -> Webhook</b> 中添加该地址，并确保以下设置：
              <ul style="margin: 8px 0 0 16px; padding: 0;">
                <li>发送格式：<b>JSON</b></li>
                <li>勾选事件：<b>媒体库 - 已添加新媒体</b></li>
                <li>勾选行为：<b>按剧集和专辑对通知进行分组</b></li>
              </ul>
            </n-alert>
            <n-form-item>
              <AppTextField :value="embyWebhookUrl" label="Emby 通知地址" readonly>
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" @click="copyToClipboard(embyWebhookUrl)">复制</n-button>
                </template>
              </AppTextField>
            </n-form-item>
          </div>
        </n-tab-pane>

        <!-- 设置 -->
        <n-tab-pane name="settings" tab="设置">
          <div class="modal-tab-content small">
            <n-list bordered>
              <n-list-item>
                <n-thing title="开放 API 访问" description="允许第三方客户端连接。关闭后所有外部接口失效。" />
                <template #suffix><n-switch v-model:value="config.enable_api" @update:value="saveConfig" /></template>
              </n-list-item>
              <n-list-item>
                <n-thing title="访问审计日志" description="记录每一次外部 API 的请求详细信息。" />
                <template #suffix><n-switch v-model:value="config.api_logging" @update:value="saveConfig" /></template>
              </n-list-item>
            </n-list>
          </div>
        </n-tab-pane>

        <!-- 日志 -->
        <n-tab-pane name="logs" tab="访问日志">
          <div class="modal-tab-content full">
            <div style="margin-bottom: 12px; display: flex; justify-content: flex-end">
              <n-button size="small" secondary @click="fetchLogs" :loading="logLoading">刷新日志</n-button>
            </div>
            <n-data-table :theme-overrides="dataTableThemeOverrides" :columns="logColumns" :data="logs" size="small" :max-height="400" />
          </div>
        </n-tab-pane>

        <!-- 文档 -->
        <n-tab-pane name="docs" tab="API 文档">
          <div class="modal-tab-content docs">
            <iframe 
              :key="config.external_token"
              :src="`${API_BASE}/api/system/docs?theme=${docsTheme}&token=${config.external_token}`" 
              class="docs-iframe"
            ></iframe>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-spin>

    <n-modal v-model:show="showLogDetail" preset="card" title="请求详情" style="width: 500px">
      <div class="detail-box"><pre>{{ currentLogDetail }}</pre></div>
    </n-modal>
  </AppGlassModal>
</template>

<style scoped>
.modal-tab-content { padding: 12px 0; }
.modal-tab-content.small { max-width: 500px; margin: 0 auto; }
.modal-tab-content.docs { height: 60vh; padding: 0; overflow: hidden; }
.docs-iframe { width: 100%; height: 100%; border: none; background: white; }
.detail-box { background: var(--bg-surface); padding: 12px; border-radius: 8px; max-height: 400px; overflow-y: auto; }
.detail-box pre { margin: 0; white-space: pre-wrap; font-size: 12px; font-family: monospace; }
</style>
