<script setup lang="ts">
/**
 * NotificationCenterView — 通知中心
 *
 * 展示发送到通知渠道（Telegram 等）的消息记录：
 * - 列表（无限滚动加载）+ 事件类型 / 发送状态筛选
 * - 查看完整渲染内容（与 TG 实际收到的一致）
 * - 单条删除 / 清空全部（保留条数由后端控制在 1000 条）
 */
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { notificationsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'NotificationCenterView' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

// --- 数据 ---
const records = ref<any[]>([])
const loading = ref(false)
const eventFilter = ref<string>('all')
const statusFilter = ref<string>('all')
const page = ref(0)
const pageSize = ref(30)
const hasMore = ref(true)
const total = ref(0)

// --- 详情弹窗 ---
const showDetail = ref(false)
const selectedRecord = ref<any>(null)

// --- 事件类型选项 ---
const eventTypeOptions = [
  { title: '全部类型', value: 'all' },
  { title: '整理入库', value: 'organize_complete' },
  { title: '整理失败', value: 'organize_failed' },
  { title: 'STRM 任务完成', value: 'strm_task_finished' },
  { title: '实时联动', value: 'strm_webhook' },
  { title: '联动生成 STRM', value: 'strm_link_created' },
  { title: '新增订阅', value: 'sub_added' },
  { title: '删除订阅', value: 'sub_deleted' },
  { title: '订阅完结', value: 'sub_completed' },
  { title: '订阅命中推送', value: 'sub_matched' },
  { title: '新集播出', value: 'episode_aired' },
  { title: '规则命中下载', value: 'rule_matched' },
  { title: 'RSS 更新', value: 'rss_updated' },
  { title: '新入库', value: 'library_new' },
  { title: '深度删除', value: 'library_deleted' },
  { title: 'CD2 联动删除', value: 'deep_delete_cd2' },
  { title: '客户端异常', value: 'client_error' },
  { title: '推送失败', value: 'client_push_failed' },
  { title: '每日播出概览', value: 'calendar_daily' },
  { title: '放送表推送', value: 'bgm_schedule_daily' },
  { title: '系统启动', value: 'system_startup' },
  { title: '系统健康', value: 'system_health' },
  { title: '系统警告', value: 'system_warning' },
  { title: '测试通知', value: 'test' },
  { title: '其他', value: 'other' },
]

// 事件类型 -> 中文标签
const eventTypeLabelMap: Record<string, string> = Object.fromEntries(
  eventTypeOptions.filter(o => o.value !== 'all').map(o => [o.value, o.title])
)

// 事件类型 -> 图标
const eventTypeIconMap: Record<string, string> = {
  organize_complete: 'mdi-movie-open-check-outline',
  organize_failed: 'mdi-alert-circle-outline',
  strm_task_finished: 'mdi-movie-filter-outline',
  strm_webhook: 'mdi-link-variant',
  strm_link_created: 'mdi-link-plus',
  sub_added: 'mdi-plus-circle-outline',
  sub_deleted: 'mdi-minus-circle-outline',
  sub_completed: 'mdi-check-circle-outline',
  sub_matched: 'mdi-magnet-outline',
  episode_aired: 'mdi-television-classic',
  rule_matched: 'mdi-filter-check-outline',
  rss_updated: 'mdi-rss',
  library_new: 'mdi-emoticon-excited-outline',
  library_deleted: 'mdi-delete-sweep-outline',
  deep_delete_cd2: 'mdi-cloud-remove-outline',
  client_error: 'mdi-download-alert-outline',
  client_push_failed: 'mdi-upload-off-outline',
  calendar_daily: 'mdi-calendar-today',
  bgm_schedule_daily: 'mdi-calendar-clock-outline',
  system_startup: 'mdi-rocket-launch-outline',
  system_health: 'mdi-heart-pulse',
  system_warning: 'mdi-alert-outline',
  test: 'mdi-flask-outline',
  download_complete: 'mdi-download-circle-outline',
  download_failed: 'mdi-download-off-outline',
}

function eventTypeLabel(t: string): string {
  return eventTypeLabelMap[t] || t || '未知'
}

function eventTypeIcon(t: string): string {
  return eventTypeIconMap[t] || 'mdi-bell-ring-outline'
}

const statusOptions = [
  { title: '全部状态', value: 'all' },
  { title: '成功', value: 'success' },
  { title: '失败', value: 'failed' },
]

const hasAnyFilter = computed(() => eventFilter.value !== 'all' || statusFilter.value !== 'all')

// --- 加载 ---
async function fetchData(isRefresh = false) {
  if (loading.value) return
  if (isRefresh) {
    page.value = 0
    hasMore.value = true
  }
  if (!hasMore.value) return

  loading.value = true
  try {
    const params: any = { limit: pageSize.value, offset: page.value * pageSize.value }
    if (eventFilter.value !== 'all') params.event_type = eventFilter.value
    if (statusFilter.value !== 'all') params.status = statusFilter.value

    const data = await notificationsApi.list(params)
    const items = data?.items || data?.data || []
    total.value = data?.total ?? total.value

    if (isRefresh) {
      records.value = items
    } else {
      records.value.push(...items)
    }

    if (items.length < pageSize.value) {
      hasMore.value = false
    } else {
      page.value++
    }
  } catch (e) {
    showError('获取通知记录失败')
  } finally {
    loading.value = false
  }
}

watch([eventFilter, statusFilter], () => fetchData(true))

// --- 无限滚动 ---
const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function setupObserver(el: HTMLElement) {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      fetchData(false)
    }
  }, { threshold: 0, rootMargin: '200px' })
  observer.observe(el)
}

watch(scrollTarget, (el) => {
  if (el) setupObserver(el)
})

watch(loading, async (isLoading) => {
  if (!isLoading && hasMore.value && scrollTarget.value) {
    await nextTick()
    const rect = scrollTarget.value.getBoundingClientRect()
    if (rect.top < window.innerHeight + 200) {
      fetchData(false)
    }
  }
})

// --- 操作 ---
function openDetail(record: any) {
  selectedRecord.value = record
  showDetail.value = true
}

async function deleteRecord(record: any) {
  const ok = await confirm({
    title: '确认删除',
    content: '确定要删除这条通知记录吗？',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await notificationsApi.remove(record.id)
    success('通知记录已删除')
    fetchData(true)
  } catch (e) {
    showError('删除失败')
  }
}

async function clearAll() {
  const ok = await confirm({
    title: '清空通知记录',
    content: '确定要清空全部通知记录吗？该操作不可恢复。',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await notificationsApi.clear()
    success('通知记录已清空')
    fetchData(true)
  } catch (e) {
    showError('清空失败')
  }
}

// --- 格式化 ---
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

/** 把渲染的 HTML 转回纯文本预览（与 TG 收到的文本一致，去掉标签） */
function toPlainText(html: string): string {
  return (html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
}

/** 正文预览：第一行是摘要标题，取其后内容 */
function previewText(record: any): string {
  return toPlainText(record.content).split('\n').slice(1).join(' ').trim().slice(0, 120)
}

onMounted(() => fetchData(true))

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 搜索与筛选 -->
    <div class="d-flex ga-3 mb-4 flex-wrap align-center">
      <v-select
        v-model="eventFilter"
        :items="eventTypeOptions"
        density="compact"
        variant="outlined"
        hide-details
        item-title="title"
        item-value="value"
        class="notification-filter-select"
      />
      <v-select
        v-model="statusFilter"
        :items="statusOptions"
        density="compact"
        variant="outlined"
        hide-details
        item-title="title"
        item-value="value"
        class="notification-filter-select"
      />
      <v-spacer />
      <div class="page-subtitle text-body-2 text-medium-emphasis">共 {{ total }} 条记录</div>
      <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-delete-sweep-outline" @click="clearAll">
        清空记录
      </v-btn>
    </div>

    <!-- 记录列表 -->
    <v-skeleton-loader v-if="loading && records.length === 0" type="card@4" />

    <template v-else-if="records.length > 0">
      <div v-for="record in records" :key="record.id" class="mb-3">
        <v-card class="glass-card hover-lift nc-record-card" @click="openDetail(record)">
          <v-card-text class="pb-0">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="d-flex align-center ga-2 flex-grow-1" style="min-width: 0">
                <v-chip
                  size="small"
                  :color="record.status === 'success' ? 'success' : 'error'"
                  variant="tonal"
                  :prepend-icon="record.status === 'success' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'"
                >
                  {{ record.status === 'success' ? '已发送' : '发送失败' }}
                </v-chip>
                <span class="text-subtitle-2 font-weight-bold text-truncate">{{ record.title }}</span>
                <v-chip size="small" variant="tonal" color="primary" class="flex-shrink-0">
                  {{ eventTypeLabel(record.event_type) }}
                </v-chip>
              </div>
              <span class="text-caption text-medium-emphasis flex-shrink-0">{{ formatTime(record.created_at) }}</span>
            </div>
          </v-card-text>

          <v-card-text class="pt-0 pb-2">
            <div class="d-flex ga-4 text-caption text-medium-emphasis flex-wrap">
              <span>
                <v-icon size="12" class="mr-1">{{ eventTypeIcon(record.event_type) }}</v-icon>
                {{ eventTypeLabel(record.event_type) }}
              </span>
              <span v-if="previewText(record)">
                <v-icon size="12" class="mr-1">mdi-text-box-outline</v-icon>
                {{ previewText(record) }}
              </span>
              <span v-if="record.error" class="text-error">
                <v-icon size="12" class="mr-1">mdi-alert-circle-outline</v-icon>
                {{ record.error }}
              </span>
            </div>
          </v-card-text>

          <v-divider />
          <v-card-actions class="pa-2">
            <v-spacer />
            <v-btn variant="tonal" size="small" color="info" prepend-icon="mdi-text-box-outline" @click.stop="openDetail(record)">内容</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteRecord(record)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </div>

      <!-- 无限滚动触发器 -->
      <div ref="scrollTarget" class="text-center pa-4">
        <v-progress-circular v-if="loading" indeterminate size="24" />
        <div v-else-if="!hasMore" class="text-caption text-medium-emphasis">
          <v-divider class="mb-3" />
          到底了，共 {{ records.length }} 条记录
        </div>
        <div v-else class="text-caption text-medium-emphasis d-flex align-center justify-center ga-2">
          <v-icon size="16">mdi-chevron-double-down</v-icon>
          向下滚动加载更多
        </div>
      </div>
    </template>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-bell-ring-outline</v-icon>
      <div class="text-h6 font-weight-medium">{{ hasAnyFilter ? '没有符合筛选条件的通知记录' : '暂无通知记录' }}</div>
      <div class="text-body-2 text-medium-emphasis mt-2">系统发送通知后会自动留档在这里</div>
    </div>

    <!-- 完整内容弹窗 -->
    <v-dialog v-model="showDetail" max-width="640" scrollable>
      <v-card v-if="selectedRecord" class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">{{ eventTypeIcon(selectedRecord.event_type) }}</v-icon>
          通知内容
          <v-spacer />
          <v-chip
            size="small"
            :color="selectedRecord.status === 'success' ? 'success' : 'error'"
            variant="tonal"
          >
            {{ selectedRecord.status === 'success' ? '已发送' : '发送失败' }}
          </v-chip>
          <v-btn icon="mdi-close" variant="text" size="small" @click="showDetail = false" class="ml-2" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4" style="max-height: 70vh; overflow-y: auto">
          <div class="d-flex ga-4 text-caption text-medium-emphasis flex-wrap mb-3">
            <span>
              <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>
              {{ formatTime(selectedRecord.created_at) }}
            </span>
            <span>
              <v-icon size="12" class="mr-1">mdi-send-outline</v-icon>
              渠道：{{ selectedRecord.channel }}
            </span>
            <span>
              <v-icon size="12" class="mr-1">{{ eventTypeIcon(selectedRecord.event_type) }}</v-icon>
              {{ eventTypeLabel(selectedRecord.event_type) }}
            </span>
          </div>
          <v-alert
            v-if="selectedRecord.error"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ selectedRecord.error }}
          </v-alert>
          <pre class="nc-detail-content">{{ toPlainText(selectedRecord.content) }}</pre>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.nc-record-card {
  transition: all 0.2s ease;
}
.notification-filter-select {
  min-width: 140px;
  max-width: 180px;
}
/* 选中文字居中 */
.notification-filter-select :deep(.v-field__input),
.notification-filter-select :deep(.v-select__selection),
.notification-filter-select :deep(.v-select__selection-text) {
  width: 100% !important;
  text-align: center !important;
  justify-content: center !important;
}
/* 下拉菜单选项也居中 */
.notification-filter-select :deep(.v-list-item-title) {
  text-align: center !important;
}
.nc-detail-content {
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.35);
}
</style>
