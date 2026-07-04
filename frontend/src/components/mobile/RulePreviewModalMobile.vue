<script setup lang="ts">
import { ref, watch } from 'vue'
import { 
  NModal, NButton, NSpace, NIcon, NTag, NSpin, NEmpty, NDrawer, NDrawerContent
} from 'naive-ui'
import { 
  DownloadOutlined as DownloadIcon, 
  HistoryOutlined as HistoryIcon,
  CloseOutlined as CloseIcon
} from '@vicons/material'
import { useRulePreview } from '../../composables/modals/useRulePreview'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  ruleData: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  clientOptions,
  fetchPreview,
  handleDownload,
  handleToggleHistory
} = useRulePreview(props)

const showClientDrawer = ref(false)
const currentItem = ref<any>(null)

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

watch(() => props.show, (newVal) => {
  if (newVal) fetchPreview()
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)"
    :mask-closable="true"
    transform-origin="center"
  >
    <div class="mobile-preview-modal">
      <div class="mobile-header">
        <div class="header-title">
          <span>匹配结果预览</span>
        </div>
        <n-button 
          v-bind="getButtonStyle('icon')" 
          size="small" 
          @click="emit('update:show', false)"
        >
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
      </div>

      <div class="mobile-content">
        <n-spin :show="loading" style="height: 100%;">
          <div v-if="items.length > 0" class="items-list">
            <div v-for="item in items" :key="item.guid" class="preview-item">
              <div class="item-header">
                <div class="status-dot" :class="{ downloaded: item.is_downloaded }"></div>
                <div class="item-title">{{ item.title }}</div>
              </div>
              
              <n-tag size="small" :bordered="false" style="margin-top: 8px;">
                {{ item.feed_name }}
              </n-tag>

              <div class="item-actions">
                <n-button 
                  v-bind="getButtonStyle('primary')" 
                  size="small"
                  @click="openDownloadDrawer(item)"
                  :disabled="clientOptions.length === 0"
                >
                  <template #icon><n-icon><DownloadIcon/></n-icon></template>
                  {{ clientOptions.length === 0 ? '无下载器' : '下载' }}
                </n-button>
                <n-button 
                  v-bind="getButtonStyle('secondary')"
                  size="small"
                  @click="handleToggleHistory(item)"
                >
                  <template #icon><n-icon><HistoryIcon/></n-icon></template>
                  {{ item.is_downloaded ? '清除' : '标记' }}
                </n-button>
              </div>
            </div>
          </div>

          <n-empty v-else-if="!loading" description="未匹配到条目" style="margin-top: 80px" />
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
.mobile-preview-modal {
  width: 100vw;
  height: 100vh;
  background: var(--app-surface-card-mixed);
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

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-spacing-md);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.preview-item {
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

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
  flex-shrink: 0;
  margin-top: 6px;
}

.status-dot.downloaded {
  background: var(--n-success-color);
  box-shadow: 0 0 6px var(--n-success-color);
}

.item-title {
  font-size: var(--m-text-sm);
  font-weight: bold;
  line-height: 1.4;
  word-break: break-all;
  color: var(--text-primary);
  flex: 1;
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
