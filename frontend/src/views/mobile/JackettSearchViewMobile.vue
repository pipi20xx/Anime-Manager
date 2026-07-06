<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { 
  NCard, NButton, NIcon, NSpace, NTag, NEmpty, NSpin, useMessage
} from 'naive-ui'
import AppSelectField from '../../components/AppSelectField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import { SearchOutlined as SearchIcon, CloudDownloadOutlined as DownloadIcon } from '@vicons/material'
import { searchKeyword } from '../../store/navigationStore'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
  <div class="m-page m-page-safe-bottom">
    <div class="m-header">
      <div>
        <h1 class="m-header-title">Jackett 搜索</h1>
        <div class="m-subtitle">全网资源聚合搜索与下载</div>
      </div>
    </div>

    <div class="m-page-scrollable">
    <div class="m-search-bar">
      <AppSearchField
        v-model:value="keyword"
        placeholder="输入动画名称、电影关键字..."
        :loading="loading"
        @search="handleSearch"
      />
    </div>

    <div class="m-selectors">
      <AppSelectField 
        v-model:value="selectedIndexerId" 
        label="搜索范围"
        :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
        placeholder="搜索范围"
        :loading="indexers.length <= 1"
      />
      <AppSelectField 
        v-if="clients.length > 0"
        v-model:value="selectedClientId" 
        label="下载客户端"
        :options="clients.map(c => ({ label: c.name + ' (' + c.type + ')', value: c.id }))" 
        placeholder="下载客户端"
      />
    </div>

    <div class="m-results">
      <n-spin :show="loading">
        <div v-if="results.length > 0" class="m-result-cards">
          <n-card
            v-for="item in results"
            :key="item.guid"
            class="m-result-card"
            hoverable
          >
            <div class="m-result-card-header">
              <div class="m-result-card-title" :title="item.title">{{ item.title }}</div>
              <n-button
                v-bind="getButtonStyle('primary')"
                size="small"
                @click="handleDownload(item)"
              >
                下载
              </n-button>
            </div>
            <div v-if="item.description" class="result-description">{{ item.description }}</div>
            <n-space size="small" style="margin-top: var(--m-spacing-xs)">
              <n-tag v-if="item.indexer" size="small" type="warning" round :bordered="false">
                {{ item.indexer }}
              </n-tag>
              <n-tag size="small" type="info" quaternary>{{ formatSize(item.size) }}</n-tag>
            </n-space>
          </n-card>
        </div>
        <n-empty v-else-if="!loading" description="搜索结果将显示在这里" class="empty-state" />
      </n-spin>
    </div>
    </div>
  </div>
</template>

<style scoped>
.m-page-scrollable {
  padding: var(--m-spacing-lg);
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

.m-result-cards {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.m-result-card {
  transition: all var(--transition-normal);
}

.m-result-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--m-spacing-sm);
}

.m-result-card-title {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-all;
  flex: 1;
  min-width: 0;
}

.empty-state {
  padding: 60px 0;
}

.result-description {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--m-spacing-xs);
  line-height: 1.4;
  word-break: break-all;
}
</style>