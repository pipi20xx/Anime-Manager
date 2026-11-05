<script setup lang="ts">
/**
 * JackettSearchView — Jackett 资源搜索
 *
 * 功能: 全网资源聚合搜索与下载
 */
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clientsApi, api } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { useNavigationStore } from '@/stores'
import { MetaTag } from '@/components/common'

defineOptions({ name: 'JackettSearchView' })

const { success, error: showError, info: showInfo } = useNotification()
const { confirm } = useConfirm()
const navStore = useNavigationStore()
const router = useRouter()

const keyword = ref('')
const loading = ref(false)
const results = ref<any[]>([])
const clients = ref<any[]>([])
const selectedClientId = ref<string | null>(null)
const indexers = ref<any[]>([])
const selectedIndexerId = ref<string>('all')

// Jackett 配置状态：资源搜索 / 订阅补全 共用同一套配置，没配就搜不到东西
const jackettConfigured = ref(true)
const jackettUrl = ref('')

async function fetchJackettStatus() {
  try {
    const data = await api.get<any>('/api/jackett/status')
    jackettConfigured.value = !!data?.configured
    jackettUrl.value = data?.url || ''
  } catch { /* 状态查询失败不阻塞页面 */ }
}

function goJackettSettings() {
  router.push('/settings')
}

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
  // clearable 清空后 keyword 为 null,axios 会直接丢弃 null 参数导致后端 422,归一化为空字符串
  const kw = (keyword.value ?? '').trim()
  loading.value = true
  recognizedMap.value = {}
  recognizingKey.value = null
  try {
    const data = await api.get<any[]>('/api/jackett/search', {
      params: { keyword: kw, indexer: selectedIndexerId.value },
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

// ---------- 单条识别（与订阅补全共用同一套识别实现） ----------
const recognizingKey = ref<string | null>(null)
const recognizedMap = ref<Record<string, any>>({})

function itemKey(item: any): string {
  return item.guid || item.link || item.title
}

function recognizedOf(item: any) {
  return recognizedMap.value[itemKey(item)]
}

function isRecognizing(item: any): boolean {
  return recognizingKey.value === itemKey(item)
}

function tmdbUrl(result: any): string {
  const type = result?.media_type === 'movie' ? 'movie' : 'tv'
  return `https://www.themoviedb.org/${type}/${result?.tmdb_id}`
}

async function handleRecognize(item: any) {
  const key = itemKey(item)
  recognizingKey.value = key
  try {
    const data = await api.post<any>('/api/jackett/recognize', {
      title: item.title,
      description: item.description || null,
    })
    if (data?.success && data.result) {
      recognizedMap.value = { ...recognizedMap.value, [key]: data.result }
    } else {
      recognizedMap.value = { ...recognizedMap.value, [key]: { failed: true } }
      showInfo(data?.message || '未识别到匹配的番剧')
    }
  } catch (e: any) {
    showError('识别失败: ' + (e?.message || '未知错误'))
  } finally {
    recognizingKey.value = null
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
  fetchJackettStatus()
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
    <!-- Jackett 未配置提示（资源搜索 / 订阅补全共用同一套 Jackett 配置） -->
    <v-alert
      v-if="!jackettConfigured"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-4"
      icon="mdi-magnify-scan"
    >
      <div class="font-weight-medium">Jackett 未配置 —— 资源搜索、订阅补全都依赖它</div>
      <div class="text-caption mt-1">
        请到「系统设置 → 基础配置 → Jackett 设置」填写 Jackett URL 与 API Key；未配置时搜索只会返回空结果（不会报错）。
      </div>
      <template #append>
        <v-btn size="small" variant="tonal" color="warning" prepend-icon="mdi-cog-outline" @click="goJackettSettings">去设置</v-btn>
      </template>
    </v-alert>

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
                <div class="meta-tags mt-2">
                  <MetaTag v-if="item.indexer" label="索引站" class="meta-tag meta-tag--feed">{{ item.indexer }}</MetaTag>
                  <MetaTag label="文件大小" class="meta-tag meta-tag--size">{{ formatSize(item.size) }}</MetaTag>
                </div>

                <!-- 识别结果（版式对齐「订阅源详情」：🎯标题行 + meta-tags 标签行） -->
                <div v-if="recognizedOf(item)" class="mt-2">
                  <template v-if="recognizedOf(item).failed">
                    <div class="meta-tags">
                      <MetaTag label="识别状态" variant="tonal" class="meta-tag meta-tag--miss">未识别</MetaTag>
                    </div>
                  </template>
                  <template v-else>
                    <div class="text-caption font-weight-bold text-truncate">
                      🎯 {{ recognizedOf(item).title || '-' }}<span v-if="recognizedOf(item).year" class="text-medium-emphasis">（{{ recognizedOf(item).year }}）</span>
                    </div>
                    <div class="meta-tags mt-1">
                      <MetaTag v-if="recognizedOf(item).tmdb_id" label="TMDB ID" :href="tmdbUrl(recognizedOf(item))" target="_blank" class="meta-tag meta-tag--tmdb">
                        ID: {{ recognizedOf(item).tmdb_id }}
                      </MetaTag>
                      <MetaTag label="媒体类型" class="meta-tag meta-tag--type">
                        {{ recognizedOf(item).media_type === 'movie' ? '电影' : '剧集' }}
                      </MetaTag>
                      <MetaTag v-if="recognizedOf(item).media_type !== 'movie'" label="季集" class="meta-tag meta-tag--season">
                        S{{ recognizedOf(item).season || 1 }} E{{ recognizedOf(item).episode || '-' }}
                      </MetaTag>
                      <MetaTag v-if="recognizedOf(item).team" label="制作组" class="meta-tag meta-tag--team">{{ recognizedOf(item).team }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).source" label="介质来源" class="meta-tag meta-tag--source">{{ recognizedOf(item).source }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).platform" label="发布平台" class="meta-tag meta-tag--source">{{ recognizedOf(item).platform }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).resolution" label="分辨率" class="meta-tag meta-tag--resolution">{{ recognizedOf(item).resolution }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).video_effect" label="视频特效" class="meta-tag meta-tag--encode">{{ recognizedOf(item).video_effect }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).video_encode" label="视频编码" class="meta-tag meta-tag--encode">{{ recognizedOf(item).video_encode }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).audio_encode" label="音频编码" class="meta-tag meta-tag--encode">{{ recognizedOf(item).audio_encode }}</MetaTag>
                      <MetaTag v-if="recognizedOf(item).subtitle" label="字幕语言" class="meta-tag meta-tag--encode">{{ recognizedOf(item).subtitle }}</MetaTag>
                    </div>
                  </template>
                </div>
              </div>

              <div class="d-flex flex-column ga-2 flex-shrink-0">
                <v-btn
                  color="success"
                  variant="tonal"
                  size="small"
                  prepend-icon="mdi-tag-search"
                  :loading="isRecognizing(item)"
                  @click="handleRecognize(item)"
                >
                  识别
                </v-btn>
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


