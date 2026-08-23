<script setup lang="ts">
/**
 * JackettSearchView — Jackett 资源搜索
 *
 * 功能: 全网资源聚合搜索与下载
 */
import { ref, onMounted, watch } from 'vue'
import { clientsApi, api } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'JackettSearchView' })

const { success, error: showError, info: showInfo } = useNotification()
const { confirm } = useConfirm()
const navStore = useNavigationStore()

const keyword = ref('')
const loading = ref(false)
const results = ref<any[]>([])
const clients = ref<any[]>([])
const selectedClientId = ref<string | null>(null)
const indexers = ref<any[]>([])
const selectedIndexerId = ref<string>('all')

async function fetchIndexers() {
  try {
    const data = await api.get<any[]>('/api/jackett/indexers')
    indexers.value = [{ id: 'all', name: '所有站点' }, ...(data || [])]
  } catch (e) {
    console.error('Failed to fetch indexers', e)
  }
}

async function fetchClients() {
  try {
    clients.value = await clientsApi.getClients()
    if (clients.value.length > 0) {
      const lastClient = localStorage.getItem('apm_jackett_last_client')
      if (lastClient && clients.value.some((c: any) => c.id === lastClient)) {
        selectedClientId.value = lastClient
      } else {
        selectedClientId.value = clients.value[0].id
      }
    }
  } catch (e) {
    console.error('Failed to fetch clients', e)
  }
}

async function handleSearch() {
  loading.value = true
  try {
    const data = await api.get<any[]>('/api/jackett/search', {
      params: { keyword: keyword.value, indexer: selectedIndexerId.value },
    })
    results.value = Array.isArray(data) ? data : []
    if (results.value.length === 0) {
      showInfo('未找到相关资源')
    }
  } catch (e) {
    showError('搜索失败')
  } finally {
    loading.value = false
  }
}

async function handleDownload(item: any) {
  if (!selectedClientId.value) {
    showError('请先选择下载客户端')
    return
  }
  const ok = await confirm({
    title: '确认下载',
    content: `确定要下载「${item.title}」吗？`,
    confirmColor: 'primary',
  })
  if (!ok) return
  try {
    const data = await clientsApi.manualDownload({
      client_id: selectedClientId.value,
      url: item.link,
      tags: 'JackettSearch',
    })
    if (data.success) {
      success('已添加到下载队列')
    } else {
      showError(data.message || '添加失败')
    }
  } catch (e: any) {
    showError(e?.message || '请求失败')
  }
}

function formatSize(sizeStr: string) {
  const size = parseInt(sizeStr)
  if (isNaN(size) || size === 0) return 'Unknown'
  const i = Math.floor(Math.log(size) / Math.log(1024))
  return (size / Math.pow(1024, i)).toFixed(2) + ' ' + ['B', 'KB', 'MB', 'GB', 'TB'][i]
}

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

onMounted(() => {
  fetchClients()
  fetchIndexers()
  // 优先使用从详情页传递过来的搜索关键词（仅填入，不自动搜索）
  if (navStore.searchKeyword) {
    keyword.value = navStore.searchKeyword
    navStore.searchKeyword = '' // 消费后清空，避免下次进入仍填充
    return
  }
  // 恢复上次搜索关键词（仅填入，不自动搜索）
  const lastKeyword = localStorage.getItem('apm_jackett_last_keyword')
  if (lastKeyword) {
    keyword.value = lastKeyword
  }
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="app-page-header mb-6">
      <h1 class="page-title text-h5 font-weight-bold">Jackett 搜索</h1>
      <div class="page-subtitle text-body-2 text-medium-emphasis mt-1">全网资源聚合搜索与下载</div>
    </div>

    <!-- 搜索栏 -->
    <v-card class="glass-card mb-4">
      <v-card-text class="pa-4">
        <v-text-field
          v-model="keyword"
          placeholder="输入动画名称、电影关键字..."
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="comfortable"
          hide-details
          clearable
          @keyup.enter="handleSearch"
        >
          <template #append-inner>
            <v-btn variant="tonal" color="primary" size="small" :loading="loading" @click="handleSearch">
              搜索
            </v-btn>
          </template>
        </v-text-field>
        <v-row class="mt-2" align="center">
          <v-col cols="6" md="6">
            <v-select
              v-model="selectedIndexerId"
              :items="indexers.map(i => ({ title: i.name, value: i.id }))"
              label="搜索范围"
              variant="outlined"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="6" md="6">
            <v-select
              v-if="clients.length > 0"
              v-model="selectedClientId"
              :items="clients.map(c => ({ title: c.name + ' (' + c.type + ')', value: c.id }))"
              label="下载客户端"
              variant="outlined"
              density="compact"
              hide-details
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 搜索结果 -->
    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" size="32" />
    </div>

    <template v-else>
      <div v-if="results.length > 0" class="d-flex flex-column ga-3">
        <v-card v-for="item in results" :key="item.guid" class="glass-card hover-lift" variant="flat">
          <v-card-text class="pa-4">
            <div class="d-flex align-start justify-space-between ga-3">
              <div class="flex-grow-1 min-width-0">
                <div class="text-subtitle-1 font-weight-bold text-truncate-2" :title="item.title">{{ item.title }}</div>
                <div v-if="item.description" class="text-body-2 text-medium-emphasis mt-1" style="line-height: 1.5; word-break: break-all">{{ item.description }}</div>
                <div class="d-flex ga-2 mt-2 flex-wrap">
                  <v-chip v-if="item.indexer" size="small" color="info" variant="tonal">{{ item.indexer }}</v-chip>
                  <v-chip size="small" color="info" variant="tonal">{{ formatSize(item.size) }}</v-chip>
                </div>
              </div>
              <v-btn
                color="primary"
                variant="tonal"
                size="small"
                prepend-icon="mdi-download"
                @click="handleDownload(item)"
              >
                下载
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </div>

      <v-card v-else class="glass-card">
        <v-card-text class="pa-8 text-center text-medium-emphasis">
          <v-icon size="48" color="grey">mdi-magnify</v-icon>
          <div class="mt-2">搜索结果将显示在这里</div>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>


