<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { 
  NModal, NCard, NInput, NButton, NIcon, NSpace, NList, NListItem, 
  NThing, NTag, NEmpty, NSpin, useMessage, NSelect, NPopover, NScrollbar
} from 'naive-ui'
import { SearchOutlined as SearchIcon, CloudDownloadOutlined as DownloadIcon, CloseOutlined as CloseIcon, StorageOutlined as ClientIcon } from '@vicons/material'
import { searchKeyword } from '../store/navigationStore'

const props = defineProps<{

  show: boolean
}>()

const emit = defineEmits(['update:show'])

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const keyword = ref('')
const loading = ref(false)
const results = ref<any[]>([])
const clients = ref<any[]>([])
const selectedClientId = ref<string | null>(null)
const indexers = ref<any[]>([])
const selectedIndexerId = ref<string>("all")

const fetchIndexers = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/jackett/indexers`)
    const data = await res.json()
    indexers.value = [{ id: 'all', name: '所有站点' }, ...data]
  } catch (e) {
    console.error('Failed to fetch indexers', e)
  }
}

const fetchClients = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/clients`)
    clients.value = await res.json()
    if (clients.value.length > 0) {
      selectedClientId.value = clients.value[0].id
    }
  } catch (e) {
    console.error('Failed to fetch clients', e)
  }
}

const handleSearch = async () => {
  loading.value = true
  try {
    const url = `${API_BASE}/api/jackett/search?keyword=${encodeURIComponent(keyword.value || '')}&indexer=${selectedIndexerId.value}`
    const res = await fetch(url)
    results.value = await res.json()
    if (results.value.length === 0) {
      message.info('未找到相关资源')
    }
  } catch (e) {
    message.error('搜索失败')
  } finally {
    loading.value = false
  }
}

const handleDownload = async (item: any) => {
  if (!selectedClientId.value) {
    message.warning('请先选择下载客户端')
    return
  }
  
  try {
    const res = await fetch(`${API_BASE}/api/clients/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: selectedClientId.value,
        url: item.link,
        tags: 'JackettSearch'
      })
    })
    const data = await res.json()
    if (data.success) {
      message.success('已添加到下载队列')
    } else {
      message.error(data.message || '添加失败')
    }
  } catch (e) {
    message.error('请求失败')
  }
}

const formatSize = (sizeStr: string) => {
  const size = parseInt(sizeStr)
  if (isNaN(size) || size === 0) return 'Unknown'
  const i = Math.floor(Math.log(size) / Math.log(1024))
  return (size / Math.pow(1024, i)).toFixed(2) + ' ' + ['B', 'KB', 'MB', 'GB', 'TB'][i]
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    if (clients.value.length === 0) fetchClients()
    if (indexers.value.length <= 1) fetchIndexers()
    if (searchKeyword.value) {
      keyword.value = searchKeyword.value
      handleSearch()
      searchKeyword.value = '' // Clear after use
    }
  }
})

const close = () => {
  emit('update:show', false)
}
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)"
    preset="card"
    style="width: 900px; max-width: 95vw; height: 96vh; border-radius: 12px;"
    class="jackett-search-modal"
    content-style="display: flex; flex-direction: column; overflow: hidden;"
  >
    <template #header>
      <div class="search-header">
        <n-icon size="24" color="#63e2b7"><SearchIcon /></n-icon>
        <span style="font-weight: bold; font-size: 18px">全网资源搜索 (Jackett)</span>
      </div>
    </template>

    <div class="search-body">
      <div class="input-section">
        <div class="input-row">
          <n-input 
            v-model:value="keyword" 
            placeholder="输入动画名称、电影关键字..." 
            size="large"
            @keyup.enter="handleSearch"
            clearable
            round
          >
            <template #prefix>
              <n-icon><SearchIcon /></n-icon>
            </template>
          </n-input>
          <n-button type="primary" size="large" @click="handleSearch" :loading="loading" round style="padding: 0 32px">
            搜索
          </n-button>
        </div>

        <div class="client-selector">
           <n-space align="center" size="large">
              <n-space align="center">
                <span class="label">搜索范围:</span>
                <n-select 
                  v-model:value="selectedIndexerId" 
                  :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
                  size="small"
                  style="width: 180px"
                  :loading="indexers.length <= 1"
                />
              </n-space>

              <n-space align="center" v-if="clients.length > 0">
                <span class="label">下载到:</span>
                <n-select 
                  v-model:value="selectedClientId" 
                  :options="clients.map(c => ({ label: c.name + ' (' + c.type + ')', value: c.id }))" 
                  size="small"
                  style="width: 200px"
                />
              </n-space>
           </n-space>
        </div>
      </div>

      <div class="results-area">
        <n-scrollbar>
          <n-spin :show="loading">
            <div class="results-container">
              <n-list hoverable clickable v-if="results.length > 0">
                <n-list-item v-for="item in results" :key="item.guid">
                  <n-thing :title="item.title">
                    <template #description>
                      <div v-if="item.description" class="result-description">{{ item.description }}</div>
                      <n-space size="small" style="margin-top: 4px">
                        <n-tag v-if="item.indexer" size="small" type="warning" round :bordered="false">
                          {{ item.indexer }}
                        </n-tag>
                        <n-tag size="small" type="info" quaternary>{{ formatSize(item.size) }}</n-tag>
                      </n-space>
                    </template>
                  </n-thing>
                  <template #suffix>
                     <n-button 
                      type="primary" 
                      ghost 
                      size="small" 
                      @click="handleDownload(item)"
                    >
                      <template #icon><n-icon><DownloadIcon /></n-icon></template>
                      下载
                    </n-button>
                  </template>
                </n-list-item>
              </n-list>
              <n-empty v-else-if="!loading" description="搜索结果将显示在这里" class="empty-state" />
            </div>
          </n-spin>
        </n-scrollbar>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.search-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
}
.input-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}
.input-row {
  display: flex;
  gap: 12px;
}
.results-area {
  flex: 1;
  min-height: 0;
  position: relative;
}
.results-container {
  /* Let content grow naturally */
  min-height: 200px;
  padding-right: 12px;
}
.empty-state {
  padding: 40px 0;
}
.client-selector {
  padding: 8px 12px;
  background: var(--app-surface-subtle);
  border-radius: var(--button-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.label {
  font-size: 13px;
  color: var(--n-text-color-3);
  font-weight: bold;
}
.result-description {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-top: 2px;
  line-height: 1.4;
  word-break: break-all;
}
</style>