<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { 
  NCard, NButton, NIcon, NSpace, NTag, NEmpty, NSpin, useMessage
} from 'naive-ui'
import AppSelectField from '../../components/AppSelectField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import {
  MagnifyingGlassIcon as SearchIcon,
  CloudArrowDownIcon as DownloadIcon
} from '@heroicons/vue/24/outline'
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
  } else {
    // 恢复上次搜索状态
    const lastKeyword = localStorage.getItem('apm_jackett_last_keyword')
    const lastIndexer = localStorage.getItem('apm_jackett_last_indexer')
    const lastClient = localStorage.getItem('apm_jackett_last_client')
    if (lastIndexer) selectedIndexerId.value = lastIndexer
    // client 需要等 fetchClients 完成后才能恢复（确保 id 有效）
    if (lastKeyword) {
      keyword.value = lastKeyword
      // 延迟搜索，等 indexers/clients 加载完成
      setTimeout(() => handleSearch(), 300)
    }
  }
})

// 记忆搜索状态
watch(keyword, (v) => {
  if (v) localStorage.setItem('apm_jackett_last_keyword', v)
  else localStorage.removeItem('apm_jackett_last_keyword')
})
watch(selectedIndexerId, (v) => {
  if (v) localStorage.setItem('apm_jackett_last_indexer', v)
})
watch(selectedClientId, (v) => {
  if (v) localStorage.setItem('apm_jackett_last_client', v)
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
      // 恢复上次选择的客户端（确保 id 仍有效）
      const lastClient = localStorage.getItem('apm_jackett_last_client')
      if (lastClient && clients.value.some(c => c.id === lastClient)) {
        selectedClientId.value = lastClient
      } else {
        selectedClientId.value = clients.value[0].id
      }
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
  <div class="jackett-search-view">
    <div class="page-header">
      <div>
        <h1>Jackett 搜索</h1>
        <div class="subtitle">全网资源聚合搜索与下载</div>
      </div>
      
      <n-space align="center">
        <AppSelectField 
          v-model:value="selectedIndexerId" 
          label="搜索范围"
          :options="indexers.map(i => ({ label: i.name, value: i.id }))" 
          placeholder="搜索范围"
          style="width: 240px"
          :loading="indexers.length <= 1"
        />
        <AppSelectField 
          v-if="clients.length > 0"
          v-model:value="selectedClientId" 
          label="下载客户端"
          :options="clients.map(c => ({ label: c.name + ' (' + c.type + ')', value: c.id }))" 
          placeholder="下载客户端"
          style="width: 320px"
        />
      </n-space>
    </div>

    <div class="search-bar">
      <AppSearchField
        v-model:value="keyword"
        placeholder="输入动画名称、电影关键字..."
        :loading="loading"
        @search="handleSearch"
      />
    </div>

    <div class="results-section">
      <n-spin :show="loading">
        <div v-if="results.length > 0" class="result-cards">
          <n-card
            v-for="item in results"
            :key="item.guid"
            class="result-card"
            hoverable
          >
            <div class="result-card-header">
              <div class="result-card-title" :title="item.title">{{ item.title }}</div>
              <n-button
                v-bind="getButtonStyle('primary')"
                size="small"
                @click="handleDownload(item)"
              >
                <template #icon><n-icon><DownloadIcon /></n-icon></template>
                下载
              </n-button>
            </div>
            <div v-if="item.description" class="result-description">{{ item.description }}</div>
            <n-space size="small" style="margin-top: 8px">
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
</template>

<style scoped>
.jackett-search-view { width: 100%; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: var(--text-primary);
}
.subtitle {
  font-size: 11px;
  color: var(--n-primary-color);
  letter-spacing: 2px;
  font-weight: bold;
  margin-top: 4px;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.search-bar .n-input {
  flex: 1;
}

.results-section {
  min-height: 300px;
}
.empty-state {
  padding: 80px 0;
}

.result-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  transition: all var(--transition-normal);
}

.result-card:hover {
  border-color: var(--app-border-hover) !important;
  box-shadow: var(--shadow-md) !important;
}

.result-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.result-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
  flex: 1;
  min-width: 0;
}

.result-description {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 8px;
  line-height: 1.5;
  word-break: break-all;
}
</style>