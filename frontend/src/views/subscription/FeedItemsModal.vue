<script setup lang="ts">
/**
 * FeedItemsModal — 订阅源详情弹窗
 *
 * 对齐旧前端 AggregatedFeedItemsModalDesktop:
 * - 分页加载所有源的条目
 * - 搜索 + 站点筛选
 * - 手动下载 / 切换已下载 / 重试识别 / 清空识别缓存 / 清除下载记录
 * - 元数据 Tags（季集、类型、分辨率、编码、字幕组、来源等）
 * - 识别状态标签（已订阅、订阅已下载、未命中、TMDB链接）
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { api } from '@/api/client'
import { subscriptionApi, clientsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{
  show: boolean
  feeds: any[]
}>()

const emit = defineEmits<{ (e: 'update:show', v: boolean): void }>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const offset = ref(0)
const hasMore = ref(true)
const LIMIT = 50

const selectedFeedIds = ref<number[]>([])
const keyword = ref('')
const clients = ref<any[]>([])
const downloading = ref<Record<string, boolean>>({})

const clientOptions = computed(() =>
  (clients.value || []).map((c: any) => ({ title: c.name, value: c.id }))
)

const feedOptions = computed(() =>
  (props.feeds || []).map((f: any) => ({ title: f.title || f.url, value: f.id }))
)

// IntersectionObserver
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function setupObserver() {
  cleanupObserver()
  nextTick(() => {
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading.value && hasMore.value) {
          fetchItems(true)
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
  })
}

function cleanupObserver() {
  if (observer) { observer.disconnect(); observer = null }
}

watch(() => props.show, (val) => {
  if (val) {
    fetchClients()
    fetchItems(false).then(() => setupObserver())
  } else { cleanupObserver() }
})

watch(() => items.value.length, () => {
  if (props.show && hasMore.value) setupObserver()
})

onBeforeUnmount(cleanupObserver)

async function fetchClients() {
  try { clients.value = (await clientsApi.getClients()) || [] } catch { /* */ }
}

function buildQuery() {
  const params = new URLSearchParams()
  params.set('limit', String(LIMIT))
  params.set('offset', String(offset.value))
  if (selectedFeedIds.value.length > 0) params.set('feed_ids', selectedFeedIds.value.join(','))
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  return params.toString()
}

async function fetchItems(append = false) {
  if (!append) { offset.value = 0; items.value = []; hasMore.value = true }
  if (!hasMore.value) return
  loading.value = true
  try {
    const data = await api.get<any>(`/api/feeds/items/all?${buildQuery()}`)
    const newItems = data?.items || []
    total.value = data?.total || 0
    if (newItems.length < LIMIT) hasMore.value = false
    if (append) items.value.push(...newItems)
    else items.value = newItems
    offset.value += newItems.length
  } catch { /* */ }
  finally { loading.value = false }
}

function applyFilter() { fetchItems(false) }

function cleanDescription(desc: string | null | undefined): string | null {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  return clean || null
}

function formatPubDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return dateStr }
}

function getTmdbUrl(item: any): string {
  if (!item.tmdb_id) return ''
  const type = item.media_type === 'movie' ? 'movie' : 'tv'
  return `https://www.themoviedb.org/${type}/${item.tmdb_id}`
}

function getMediaTypeLabel(type: string | null | undefined): string {
  if (type === 'movie') return '🎬 电影'
  if (type === 'tv') return '📺 剧集'
  return type || ''
}

async function handleDownload(item: any, clientId: string) {
  downloading.value[item.guid] = true
  try {
    const data: any = await api.post('/api/clients/download', { client_id: clientId, url: item.link, title: item.title })
    if (data?.success) success(data.message || '下载已推送')
    else showError(data?.message || '推送失败')
  } catch { showError('请求失败') }
  finally { downloading.value[item.guid] = false }
}

async function handleToggleHistory(item: any, isAdd: boolean) {
  try {
    if (isAdd) {
      await subscriptionApi.saveDownloadHistory({ guid: item.guid, title: item.title, feed_id: item.feed_id })
    } else {
      await subscriptionApi.deleteDownloadHistory(item.guid)
    }
    item.is_downloaded = isAdd
  } catch { /* */ }
}

async function handleRetryRecognition() {
  loading.value = true
  try {
    const data = await subscriptionApi.retryRecognition()
    if (data?.success) success(data.message || '已触发')
    else showError(data?.message || '重试失败')
  } catch { showError('重试请求失败') }
  finally { loading.value = false }
}

async function handleClearCache() {
  const ok = await confirm({ title: '确认清空', content: '此操作将清空所有 RSS 源的条目记录，包括识别结果、下载状态等全部数据。下次刷新时将重新抓取并识别所有条目，确定要继续吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    const data = await subscriptionApi.clearRecognitionCache()
    if (data?.success) { success(data.message || '已清空'); fetchItems(false) }
    else showError(data?.message || '清空失败')
  } catch { showError('清空请求失败') }
}

async function handleClearHistory() {
  const tip = selectedFeedIds.value.length > 0
    ? `确认清除当前筛选的 ${selectedFeedIds.value.length} 个站点的下载记录吗？`
    : '未筛选站点，将清除全部下载记录，确认吗？'
  const ok = await confirm({ title: '确认清除', content: tip, confirmColor: 'error' })
  if (!ok) return
  try {
    const qs = selectedFeedIds.value.length > 0 ? `?feed_ids=${selectedFeedIds.value.join(',')}` : ''
    const data: any = await api.post(`/api/feeds/reset-history${qs}`)
    if (data?.success) { success(data.message || '已清除'); fetchItems(false) }
    else showError(data?.message || '清除失败')
  } catch { showError('清除请求失败') }
}
</script>

<template>
  <v-dialog :model-value="show" max-width="1400" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-format-list-bulleted</v-icon>
        订阅源详情
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="$emit('update:show', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 工具栏 -->
        <div class="list-toolbar">
          <div class="list-toolbar__filters">
            <v-text-field
              v-model="keyword"
              placeholder="搜索资源标题或识别名..."
              prepend-inner-icon="mdi-magnify"
              density="compact" hide-details variant="outlined"
              class="flex-grow-1"
              style="max-width: 320px"
              @keyup.enter="applyFilter"
            />
            <v-select
              v-model="selectedFeedIds"
              :items="feedOptions"
              multiple chips clearable
              density="compact" hide-details variant="outlined"
              placeholder="筛选站点"
              class="flex-grow-1"
              style="max-width: 320px"
              @update:model-value="applyFilter"
            />
          </div>
          <div class="list-toolbar__actions">
            <span class="list-toolbar__total">共 {{ total }} 条</span>
            <v-spacer />
            <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-delete-sweep-outline" @click="handleClearHistory">清除下载记录</v-btn>
            <v-btn variant="tonal" size="small" color="primary" prepend-icon="mdi-refresh" @click="handleRetryRecognition" :loading="loading">重试识别失败项</v-btn>
            <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-database-remove-outline" @click="handleClearCache">清空识别缓存</v-btn>
          </div>
        </div>

        <v-skeleton-loader v-if="loading && items.length === 0" type="list-item@8" />

        <!-- 条目列表 -->
        <div v-else-if="items.length > 0" class="d-flex flex-column ga-2">
          <v-card v-for="(item, index) in items" :key="item.guid" class="glass-card hover-lift pa-3" variant="flat">
            <!-- 第一行：标签 + 序号 -->
            <div class="d-flex align-center justify-space-between ga-2 flex-wrap">
              <div class="d-flex align-center ga-1 flex-wrap" style="min-width: 0; flex: 1;">
                <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--feed">{{ item.feed_name || '-' }}</v-chip>
                <v-chip size="x-small" variant="flat" :class="['meta-tag', item.is_downloaded ? 'meta-tag--downloaded' : 'meta-tag--not-downloaded']">
                  {{ item.is_downloaded ? '已下载' : '未下载' }}
                </v-chip>
                <span v-if="item.tmdb_title" class="text-caption font-weight-bold" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0;">🎯 {{ item.tmdb_title }}</span>
              </div>
              <span class="text-caption text-medium-emphasis flex-shrink-0" style="font-family: monospace;">#{{ index + 1 }}</span>
            </div>

            <!-- 标题 -->
            <div class="text-subtitle-2 font-weight-bold mt-2" style="word-break: break-all;">{{ item.raw_title || item.title }}</div>

            <!-- 描述 -->
            <div v-if="cleanDescription(item.description)" class="text-caption text-medium-emphasis mt-1" style="word-break: break-all; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
              {{ cleanDescription(item.description) }}
            </div>

            <!-- 元数据 Tags -->
            <div class="meta-tags mt-2">
              <!-- 订阅状态标签 -->
              <v-chip v-if="item.in_subscription" size="x-small" variant="flat" class="meta-tag meta-tag--subscribed">已订阅</v-chip>
              <v-chip v-if="item.episode_collected" size="x-small" variant="flat" class="meta-tag meta-tag--collected">订阅已下载</v-chip>

              <!-- 识别结果标签 -->
              <template v-if="item.recognition_done && item.tmdb_id">
                <v-chip :href="getTmdbUrl(item)" target="_blank" size="x-small" variant="flat" class="meta-tag meta-tag--tmdb">ID: {{ item.tmdb_id }}</v-chip>
                <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--type">{{ getMediaTypeLabel(item.media_type) }}</v-chip>
                <v-chip v-if="item.media_type === 'tv'" size="x-small" variant="flat" class="meta-tag meta-tag--season">
                  S{{ item.season || 1 }} E{{ item.episode || '-' }}
                </v-chip>
              </template>
              <v-chip v-else-if="item.recognition_done" size="x-small" variant="tonal" class="meta-tag meta-tag--miss">未命中</v-chip>

              <!-- 字幕组 -->
              <v-chip v-if="item.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">{{ item.team }}</v-chip>

              <!-- 来源/平台 -->
              <v-chip v-if="item.source" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ item.source }}</v-chip>
              <v-chip v-if="item.platform" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ item.platform }}</v-chip>

              <!-- 分辨率 -->
              <v-chip v-if="item.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">{{ item.resolution }}</v-chip>

              <!-- 视频特效/编码 -->
              <v-chip v-if="item.video_effect" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ item.video_effect }}</v-chip>
              <v-chip v-if="item.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ item.video_encode }}</v-chip>

              <!-- 音频编码 -->
              <v-chip v-if="item.audio_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ item.audio_encode }}</v-chip>

              <!-- 字幕 -->
              <v-chip v-if="item.subtitle" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ item.subtitle }}</v-chip>
            </div>

            <!-- 底部：时间 + 操作 -->
            <div class="d-flex align-center justify-space-between flex-wrap ga-2 mt-2">
              <span class="text-caption text-medium-emphasis" style="font-family: monospace;">{{ formatPubDate(item.pub_date) }}</span>
              <div class="d-flex align-center ga-1 flex-shrink-0">
                <v-menu v-if="clientOptions.length > 0">
                  <template #activator="{ props: menuProps }">
                    <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-download" v-bind="menuProps">手动下载</v-btn>
                  </template>
                  <v-list density="compact" min-width="160">
                    <v-list-item v-for="c in clientOptions" :key="c.value" @click="handleDownload(item, c.value)">
                      <v-list-item-title>{{ c.title }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
                <v-btn
                  size="small" variant="tonal"
                  :color="item.is_downloaded ? 'warning' : 'success'"
                  :prepend-icon="item.is_downloaded ? 'mdi-close-circle-outline' : 'mdi-check-circle-outline'"
                  @click="handleToggleHistory(item, !item.is_downloaded)"
                >
                  {{ item.is_downloaded ? '清除下载记录' : '设为已下载' }}
                </v-btn>
              </div>
            </div>
          </v-card>

          <!-- 无限滚动哨兵 -->
          <div ref="sentinelRef" style="height: 1px" />
          <div v-if="loading" class="text-center pa-4"><v-progress-circular indeterminate size="24" /></div>
          <div v-if="!hasMore && items.length > 0" class="text-center text-caption text-medium-emphasis pa-2">已加载全部</div>
        </div>

        <div v-else class="text-center pa-8">
          <v-icon size="64" color="primary" class="mb-4">mdi-inbox-outline</v-icon>
          <div class="text-body-2 text-medium-emphasis">暂无条目</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

</script>
