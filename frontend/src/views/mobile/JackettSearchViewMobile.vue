<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { 
  NInput, NButton, NIcon, NSpace, NList, NListItem, 
  NThing, NTag, NEmpty, NSpin, useMessage, NSelect
} from 'naive-ui'
import { SearchOutlined as SearchIcon, CloudDownloadOutlined as DownloadIcon } from '@vicons/material'
import { searchKeyword } from '../../store/navigationStore'

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const keyword = ref('')
const loading = ref(false)
const results = ref<any[]>([])
const clients = ref<any[]>([])
const selectedClientId = ref<string | null>(null)
const indexers = ref<any[]>([])
const selectedIndexerId = ref<string>("all")

onMounted(() => {
  fetchClients()
  fetchIndexers()
  if (searchKeyword.value) {
    keyword.value = searchKeyword.value
    handleSearch()
    searchKeyword.value = ''
  }
})

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
</script>

<template>
  <div class="jackett-search-mobile">
    <div class="m-page-header">
      <h1>Jackett 搜索</h1>
      <div class="m-subtitle">全网资源聚合搜索与下载</div>
    </div>

    <div class="m-search-bar">
      <n-input 
        v-model:value="keyword" 
        placeholder="输入动画名称、电影关键字..." 
        size="large"
        @keyup.enter="handleSearch"
        clearable
      >
        <template #prefix>
          <n-icon><SearchIcon /></n-icon>
        </template>
      </n-input>
      <n-button type="primary" size="large" @click="handleSearch" :loading="loading" block style="margin-top: var(--m-spacing-sm);">
        搜索
      </n-button>
    </div>

    <div class="m-selectors">
      <n-select 
        v-model:value="selectedIndexerId" 
        :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
        placeholder="搜索范围"
        size="small"
        :loading="indexers.length <= 1"
      />
      <n-select 
        v-if="clients.length > 0"
        v-model:value="selectedClientId" 
        :options="clients.map(c => ({ label: c.name + ' (' + c.type + ')', value: c.id }))" 
        placeholder="下载客户端"
        size="small"
      />
    </div>

    <div class="m-results">
      <n-spin :show="loading">
        <n-list hoverable clickable v-if="results.length > 0" bordered>
          <n-list-item v-for="item in results" :key="item.guid">
            <n-thing :title="item.title">
              <template #description>
                <div v-if="item.description" class="result-description">{{ item.description }}</div>
                <n-space size="small" style="margin-top: var(--m-spacing-xs)">
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
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.jackett-search-mobile {
  padding: var(--m-spacing-md);
  padding-bottom: calc(var(--m-spacing-xl) + env(safe-area-inset-bottom));
}

.m-page-header {
  margin-bottom: var(--m-spacing-lg);
}
.m-page-header h1 {
  margin: 0;
  font-size: 22px;
  color: var(--text-primary);
}
.m-subtitle {
  font-size: 11px;
  color: var(--n-primary-color);
  letter-spacing: 1.5px;
  font-weight: bold;
  margin-top: 4px;
}

.m-search-bar {
  margin-bottom: var(--m-spacing-md);
}

.m-selectors {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
  margin-bottom: var(--m-spacing-lg);
}

.m-results {
  min-height: 300px;
}

.empty-state {
  padding: 60px 0;
}

.result-description {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
  line-height: 1.4;
  word-break: break-all;
}
</style>