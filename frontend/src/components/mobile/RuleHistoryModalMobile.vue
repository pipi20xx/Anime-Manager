<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { 
  NModal, NButton, NSpace, NTag, NSpin, NEmpty, NIcon, NDrawer, NDrawerContent, useMessage
} from 'naive-ui'
import { 
  DownloadOutlined as DownloadIcon,
  DeleteOutlined as DeleteIcon,
  CheckCircleOutlined as SuccessIcon,
  ErrorOutlined as FailIcon,
  CloseOutlined as CloseIcon
} from '@vicons/material'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  rule: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const message = useMessage()

const loading = ref(false)
const items = ref<any[]>([])
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const showClientDrawer = ref(false)
const currentItem = ref<any>(null)

const clientOptions = computed(() => {
  return (props.clients || []).map(c => ({ label: c.name, value: c.id }))
})

const handleDownload = async (item: any, clientId: string) => {
  try {
    const res = await fetch(`${API_BASE}/api/clients/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: clientId,
        url: item.link,
        title: item.title
      })
    })
    const data = await res.json()
    if (data.success) {
      message.success(data.message)
    } else {
      message.error(data.message)
    }
  } catch (e) {
    message.error('请求失败')
  }
}

const openDownloadDrawer = (item: any) => {
  if (clientOptions.value.length === 0) return
  
  if (clientOptions.value.length === 1) {
    handleDownload(item, clientOptions.value[0].value)
  } else {
    currentItem.value = item
    showClientDrawer.value = true
  }
}

const selectClient = (clientId: string) => {
  if (currentItem.value) {
    handleDownload(currentItem.value, clientId)
  }
  showClientDrawer.value = false
  currentItem.value = null
}

const handleDelete = async (guid: string) => {
  try {
    await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(guid)}`, { method: 'DELETE' })
    message.success('已清除下载记录')
    fetchHistory()
  } catch (e) {
    message.error('清除失败')
    console.error(e)
  }
}

const fetchHistory = async () => {
  if (!props.rule?.id) return
  loading.value = true
  items.value = []
  try {
    const res = await fetch(`${API_BASE}/api/rules/${props.rule.id}/history`)
    items.value = await res.json()
  } catch (e) {
    console.error('获取历史失败', e)
  } finally {
    loading.value = false
  }
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  try {
    const date = new Date(timeStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return timeStr
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) fetchHistory()
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)"
    :mask-closable="true"
    transform-origin="center"
  >
    <div class="mobile-history-modal">
      <div class="mobile-header">
        <div class="header-title">
          <n-icon size="20"><SuccessIcon /></n-icon>
          <span>执行记录</span>
        </div>
        <n-button 
          v-bind="getButtonStyle('icon')" 
          size="small" 
          @click="emit('update:show', false)"
        >
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
      </div>

      <div class="mobile-subtitle" v-if="rule?.name">{{ rule.name }}</div>

      <div class="mobile-content">
        <n-spin :show="loading">
          <div class="history-list" v-if="items.length > 0">
            <div v-for="item in items" :key="item.guid" class="history-item">
              <div class="item-header">
                <n-icon 
                  size="20" 
                  :color="item.state === 'Success' ? 'var(--n-success-color)' : 'var(--n-error-color)'"
                >
                  <SuccessIcon v-if="item.state === 'Success'" />
                  <FailIcon v-else />
                </n-icon>
                <div class="item-title">{{ item.title }}</div>
              </div>
              
              <div class="item-desc" v-if="item.description">{{ item.description }}</div>
              
              <div class="item-meta">
                <span class="item-time">{{ formatTime(item.created_at) }}</span>
                <n-tag 
                  size="tiny" 
                  round 
                  :bordered="false"
                  :style="item.state === 'Success' 
                    ? { color: '#fff', backgroundColor: '#2e7d32' } 
                    : { color: '#fff', backgroundColor: '#c62828' }"
                >
                  {{ item.state === 'Success' ? '成功' : '失败' }}
                </n-tag>
              </div>

              <div class="item-actions">
                <n-button 
                  v-bind="getButtonStyle('secondary')" 
                  size="small"
                  @click="handleDelete(item.guid)"
                >
                  <template #icon><n-icon><DeleteIcon /></n-icon></template>
                  清除
                </n-button>
                <n-button 
                  v-if="item.link"
                  v-bind="getButtonStyle('primary')" 
                  size="small"
                  @click="openDownloadDrawer(item)"
                  :disabled="clientOptions.length === 0"
                >
                  <template #icon><n-icon><DownloadIcon /></n-icon></template>
                  {{ clientOptions.length === 0 ? '无下载器' : '再下载' }}
                </n-button>
              </div>
            </div>
          </div>
          
          <div v-else-if="!loading" class="empty-state">
            <n-empty description="该规则暂无推送记录" />
          </div>
        </n-spin>
      </div>
    </div>
  </n-modal>

  <n-drawer 
    v-model:show="showClientDrawer" 
    placement="bottom" 
    :height="clientOptions.length * 60 + 100"
    style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;"
  >
    <n-drawer-content title="选择下载客户端" closable :native-scrollbar="false">
      <div class="client-list">
        <div 
          v-for="client in clientOptions" 
          :key="client.value"
          class="client-item"
          @click="selectClient(client.value)"
        >
          <div class="client-icon">
            <n-icon size="20"><DownloadIcon /></n-icon>
          </div>
          <span class="client-name">{{ client.label }}</span>
        </div>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.mobile-history-modal {
  width: 100vw;
  height: 100vh;
  background: var(--app-surface-card);
  display: flex;
  flex-direction: column;
}

.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-spacing-md);
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface-inner);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-lg);
  font-weight: bold;
  color: var(--text-primary);
}

.mobile-subtitle {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  background: var(--app-surface-inner);
  border-bottom: 1px solid var(--app-border-light);
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-spacing-md);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.history-item {
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.item-header {
  display: flex;
  align-items: flex-start;
  gap: var(--m-spacing-sm);
}

.item-title {
  font-size: var(--m-text-sm);
  font-weight: bold;
  line-height: 1.4;
  word-break: break-all;
  color: var(--text-primary);
  flex: 1;
}

.item-desc {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.item-time {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  font-family: monospace;
}

.item-actions {
  display: flex;
  gap: var(--m-spacing-sm);
  margin-top: var(--m-spacing-sm);
  padding-top: var(--m-spacing-sm);
  border-top: 1px solid var(--app-border-light);
}

.item-actions .n-button {
  flex: 1;
}

.empty-state {
  padding: 80px var(--m-spacing-lg);
  text-align: center;
}

.empty-state :deep(.n-empty__icon) {
  font-size: 64px;
}

.empty-state :deep(.n-empty__description) {
  font-size: var(--m-text-md);
  color: var(--text-secondary);
}

.client-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}

.client-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
  background: var(--app-surface-inner);
}

.client-item:active {
  background: var(--bg-surface-hover);
}

.client-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--n-primary-color);
  border-radius: var(--m-radius-md);
  color: #fff;
}

.client-name {
  font-size: var(--m-text-md);
  font-weight: 500;
  color: var(--text-primary);
}
</style>
