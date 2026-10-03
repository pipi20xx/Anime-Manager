<script setup lang="ts">
/**
 * WebhookEventsView — 联动记录中心（Webhook 事件台账）
 *
 * - 事件列表（卡片式） + 无限滚动加载
 * - 按状态 / 来源筛选，按路径搜索
 * - 统计信息（状态分布 + 今日总数/今日失败）
 * - 事件详情弹窗：原始 payload、错误信息、目录展开的子事件、跳转任务中心
 * - 手动重放（成功/失败的事件均可原样重新执行）、删除 / 批量清理
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { webhookEventsApi, taskHistoryApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import type { WebhookEvent, WebhookEventStats } from '@/api/webhookEvents'

defineOptions({ name: 'WebhookEventsView' })

const router = useRouter()
const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

// --- 数据 ---
const events = ref<WebhookEvent[]>([])
const stats = ref<WebhookEventStats | null>(null)
const loading = ref(false)
const statusFilter = ref<string>('all')
const sourceFilter = ref<string>('all')
const searchQuery = ref('')
const startDate = ref<string>('')
const endDate = ref<string>('')
const page = ref(0)
const pageSize = ref(20)
const hasMore = ref(true)
const totalCount = ref(0)
const replayingAll = ref(false)

const statusOptions = [
  { title: '全部状态', value: 'all' },
  { title: '成功', value: 'success' },
  { title: '失败', value: 'failed' },
  { title: '未命中任务', value: 'unmatched' },
  { title: '处理中', value: 'processing' },
  { title: '待处理', value: 'pending' },
]

// 来源与后端 process_cd2_notification 的 source 取值一一对应:
// HTTP 端点按来源 IP 区分「原生 Webhook / 内部监控」;gRPC 监控与整理/秒传联动为内部直调
const sourceOptions = [
  { title: '全部来源', value: 'all' },
  { title: '原生 Webhook', value: '原生 Webhook' },
  { title: '内部监控', value: '内部监控' },
  { title: 'CD2监控', value: 'CD2监控' },
  { title: '整理联动', value: '整理联动' },
  { title: '手动重放', value: '手动重放' },
]

// --- 状态展示映射 ---
const STATUS_META: Record<string, { label: string; color: string; icon: string }> = {
  success: { label: '成功', color: 'success', icon: 'mdi-check-circle-outline' },
  failed: { label: '失败', color: 'error', icon: 'mdi-alert-circle-outline' },
  unmatched: { label: '未命中', color: 'grey', icon: 'mdi-crosshairs-off' },
  processing: { label: '处理中', color: 'info', icon: 'mdi-progress-clock' },
  pending: { label: '待处理', color: 'warning', icon: 'mdi-clock-outline' },
}

function statusMeta(status: string) {
  return STATUS_META[status] || { label: status, color: 'grey', icon: 'mdi-help-circle-outline' }
}

const statChips = computed(() => {
  const s = stats.value
  if (!s) return []
  const by = s.by_status || {}
  return [
    { label: '累计事件', value: s.total, color: 'primary', icon: 'mdi-format-list-numbered' },
    { label: '今日新增', value: s.today_total, color: 'info', icon: 'mdi-calendar-today' },
    { label: '今日失败', value: s.today_failed, color: by.failed ? 'error' : 'grey', icon: 'mdi-alert-outline' },
    { label: '成功', value: by.success || 0, color: 'success', icon: 'mdi-check-circle-outline' },
    { label: '失败', value: by.failed || 0, color: 'error', icon: 'mdi-alert-circle-outline' },
    { label: '未命中', value: by.unmatched || 0, color: 'grey', icon: 'mdi-crosshairs-off' },
  ]
})

// --- 搜索防抖 ---
let searchDebounce: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => fetchEvents(), 400)
})

watch([statusFilter, sourceFilter, startDate, endDate], () => fetchEvents())

// --- 批量重放当前筛选结果 ---
function buildFilterParams(): Record<string, any> {
  const params: Record<string, any> = {}
  if (statusFilter.value !== 'all') params.status = statusFilter.value
  if (sourceFilter.value !== 'all') params.source = sourceFilter.value
  if (searchQuery.value) params.search = searchQuery.value
  if (startDate.value) params.start_time = `${startDate.value}T00:00:00`
  if (endDate.value) params.end_time = `${endDate.value}T23:59:59`
  return params
}

async function replayFiltered() {
  if (totalCount.value === 0) {
    showError('当前筛选结果为空，没有可重放的记录')
    return
  }
  const ok = await confirm({
    title: '批量重放',
    content: `将按时间从新到旧，顺序重放当前筛选结果中的 ${totalCount.value} 条记录（每个事件的原始 payload 原样重新执行，串行执行避免触发风控）。确定继续吗？`,
    confirmColor: 'primary',
  })
  if (!ok) return
  replayingAll.value = true
  try {
    const res = await webhookEventsApi.replayAll(buildFilterParams())
    success(res?.message || '批量重放完成')
    fetchEvents()
  } catch (e) {
    showError('批量重放失败')
  } finally {
    replayingAll.value = false
  }
}

// --- 列表加载 ---
async function fetchStats() {
  try {
    stats.value = await webhookEventsApi.stats()
  } catch {
    /* 统计失败不打断列表 */
  }
}

async function fetchEvents(isRefresh = true) {
  if (loading.value) return
  loading.value = true
  try {
    if (isRefresh) {
      page.value = 0
      hasMore.value = true
    }
    const params: any = { limit: pageSize.value, offset: page.value * pageSize.value, ...buildFilterParams() }

    const data = await webhookEventsApi.list(params)
    const items: WebhookEvent[] = data?.items || data?.data || []
    totalCount.value = data?.total ?? items.length
    if (isRefresh) {
      events.value = items
    } else {
      events.value.push(...items)
    }
    hasMore.value = items.length >= pageSize.value
    if (hasMore.value) page.value++
    fetchStats()
  } catch (e) {
    showError('获取联动记录失败')
  } finally {
    loading.value = false
  }
}

function loadMore() {
  if (!hasMore.value) return
  fetchEvents(false)
}

// --- 详情弹窗 ---
const showDetailModal = ref(false)
const selectedEvent = ref<WebhookEvent | null>(null)
const childEvents = ref<WebhookEvent[]>([])
const loadingChildren = ref(false)
// 全链路执行日志（webhook 接收任务 + 队列处理/目录展开任务）
const eventLogs = ref<Array<{
  task_id: string
  module: string
  name: string
  status: string
  started_at: string | null
  logs: Array<{ time: string; level: string; message: string }>
}>>([])
const loadingLogs = ref(false)

const payloadText = computed(() => {
  try {
    return JSON.stringify(selectedEvent.value?.payload ?? {}, null, 2)
  } catch {
    return String(selectedEvent.value?.payload ?? '')
  }
})

async function openDetail(event: WebhookEvent) {
  selectedEvent.value = event
  showDetailModal.value = true
  childEvents.value = []
  eventLogs.value = []
  fetchEventLogs(event.id)
  if (event.is_dir) {
    loadingChildren.value = true
    try {
      const data = await webhookEventsApi.list({ limit: 200, parent_id: event.id })
      childEvents.value = data?.items || []
    } catch {
      /* 子事件加载失败不阻塞详情 */
    } finally {
      loadingChildren.value = false
    }
  }
}

async function fetchEventLogs(eventId: number) {
  loadingLogs.value = true
  try {
    const data = await webhookEventsApi.getLogs(eventId)
    eventLogs.value = data?.tasks || []
  } catch {
    eventLogs.value = []
  } finally {
    loadingLogs.value = false
  }
}

function goTaskCenter() {
  const taskId = selectedEvent.value?.task_id
  if (taskId) router.push({ path: '/task-history', query: { search: taskId } })
}

// --- 操作 ---
async function replayEvent(event: WebhookEvent) {
  const ok = await confirm({
    title: '确认重放',
    content: `将把该事件的原始 payload 原样重新执行一遍（第 ${(event.attempts || 1) + 1} 次）。确定继续吗？`,
    confirmColor: 'primary',
  })
  if (!ok) return
  try {
    await webhookEventsApi.replay(event.id)
    success('重放已触发，状态将随执行结果更新')
    setTimeout(() => fetchEvents(), 1500)
  } catch (e) {
    showError('重放失败')
  }
}

async function deleteEvent(event: WebhookEvent) {
  const ok = await confirm({
    title: '确认删除',
    content: '确定要删除这条联动记录吗？',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await webhookEventsApi.remove(event.id)
    success('联动记录已删除')
    fetchEvents()
  } catch (e) {
    showError('删除失败')
  }
}

async function clearEvents() {
  const ok = await confirm({
    title: '批量清理',
    content: '确定要清空当前筛选条件下的所有联动记录吗？该操作不可恢复。',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    const res = await webhookEventsApi.clear(buildFilterParams())
    success(res?.message || '清理完成')
    fetchEvents()
  } catch (e) {
    showError('清理失败')
  }
}

// --- 无限滚动 ---
const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

watch(scrollTarget, (el) => {
  if (observer) observer.disconnect()
  if (!el) return
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      loadMore()
    }
  }, { threshold: 0, rootMargin: '200px' })
  observer.observe(el)
})

// --- 格式化 ---
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatPath(path: string): string {
  const parts = (path || '').split('/')
  return parts[parts.length - 1] || path
}

function actionIcon(action: string, isDir: boolean): string {
  if (isDir) return 'mdi-folder-move-outline'
  return action === 'rename' ? 'mdi-file-undo-outline' : 'mdi-file-plus-outline'
}

// --- 生命周期 ---
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchEvents()
  refreshTimer = setInterval(() => {
    if (!loading.value && !showDetailModal.value) fetchEvents()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (observer) observer.disconnect()
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 统计概览 -->
    <div v-if="statChips.length" class="d-flex ga-2 mb-4 flex-wrap">
      <v-chip v-for="chip in statChips" :key="chip.label" variant="tonal" :color="chip.color" size="small">
        <v-icon start size="14">{{ chip.icon }}</v-icon>
        {{ chip.label }} {{ chip.value }}
      </v-chip>
    </div>

    <!-- 搜索与筛选 -->
    <div class="d-flex ga-3 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="searchQuery"
        label="搜索路径..."
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        style="max-width: 240px"
      />
      <v-select
        v-model="statusFilter"
        :items="statusOptions"
        density="compact"
        variant="outlined"
        hide-details
        item-title="title"
        item-value="value"
        style="min-width: 140px; max-width: 180px"
      />
      <v-select
        v-model="sourceFilter"
        :items="sourceOptions"
        density="compact"
        variant="outlined"
        hide-details
        item-title="title"
        item-value="value"
        style="min-width: 140px; max-width: 180px"
      />
      <v-text-field
        v-model="startDate"
        type="date"
        label="开始日期"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 165px"
      />
      <v-text-field
        v-model="endDate"
        type="date"
        label="结束日期"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 165px"
      />
      <v-spacer />
      <v-btn variant="tonal" size="small" color="primary" prepend-icon="mdi-replay"
             :loading="replayingAll" :disabled="replayingAll || totalCount === 0" @click="replayFiltered">重放</v-btn>
      <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-spray-bottle" @click="clearEvents">清理</v-btn>
      <v-btn variant="tonal" size="small" color="primary" prepend-icon="mdi-refresh" @click="fetchEvents()">刷新</v-btn>
    </div>

    <!-- 事件列表 -->
    <v-skeleton-loader v-if="loading && events.length === 0" type="card@4" />

    <template v-else-if="events.length > 0">
      <div v-for="event in events" :key="event.id" class="mb-3">
        <v-card class="glass-card hover-lift" :class="{ 'we-failed-card': event.status === 'failed' }">
          <v-card-text class="pb-0">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="d-flex align-center ga-2 flex-grow-1" style="min-width: 0">
                <v-chip size="small" :color="statusMeta(event.status).color" variant="tonal" class="flex-shrink-0">
                  <v-icon start size="14">{{ statusMeta(event.status).icon }}</v-icon>
                  {{ statusMeta(event.status).label }}
                </v-chip>
                <v-icon size="18" class="flex-shrink-0">{{ actionIcon(event.action, event.is_dir) }}</v-icon>
                <span class="text-subtitle-2 font-weight-bold text-truncate">
                  {{ formatPath(event.file_path) }}
                  <span v-if="event.is_dir" class="text-caption text-medium-emphasis">(目录)</span>
                </span>
              </div>
              <span class="text-caption text-medium-emphasis flex-shrink-0">{{ formatTime(event.first_seen_at) }}</span>
            </div>
          </v-card-text>

          <v-card-text class="pt-0 pb-2">
            <div class="d-flex ga-3 text-caption text-medium-emphasis flex-wrap">
              <span v-for="src in event.sources" :key="src">
                <v-icon size="12" class="mr-1">mdi-source-branch</v-icon>{{ src }}
              </span>
              <span v-if="event.dup_count > 0">
                <v-icon size="12" class="mr-1">mdi-merge</v-icon>合并重复 {{ event.dup_count }} 次
              </span>
              <span v-if="event.attempts > 1">
                <v-icon size="12" class="mr-1">mdi-replay</v-icon>已执行 {{ event.attempts }} 次
              </span>
            </div>
            <div class="text-caption text-medium-emphasis mt-1 we-break-all">
              <v-icon size="12" class="mr-1">mdi-map-marker-path</v-icon>{{ event.file_path }}
            </div>
            <div v-if="event.status === 'failed' && event.error_message" class="text-caption text-error mt-1">
              <v-icon size="12" class="mr-1">mdi-alert-circle-outline</v-icon>{{ event.error_message }}
            </div>
          </v-card-text>

          <v-divider />
          <v-card-actions class="pa-2">
            <v-spacer />
            <v-btn variant="tonal" size="small" color="info" prepend-icon="mdi-text-box-outline" @click="openDetail(event)">详情</v-btn>
            <v-btn variant="tonal" size="small" color="primary" prepend-icon="mdi-replay" @click="replayEvent(event)">重放</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteEvent(event)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </div>

      <!-- 无限滚动触发器 -->
      <div ref="scrollTarget" class="text-center pa-4">
        <v-progress-circular v-if="loading" indeterminate size="24" />
        <div v-else-if="!hasMore" class="text-caption text-medium-emphasis">
          <v-divider class="mb-3" />
          到底了，共 {{ events.length }} 条记录
        </div>
        <div v-else class="text-caption text-medium-emphasis d-flex align-center justify-center ga-2">
          <v-icon size="16">mdi-chevron-double-down</v-icon>
          向下滚动加载更多
        </div>
      </div>
    </template>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-webhook</v-icon>
      <div class="text-h6 font-weight-medium">暂无联动记录</div>
      <div class="text-body-2 text-medium-emphasis mt-2">CD2 Webhook 或内部联动触发后，事件会记录在这里</div>
    </div>

    <!-- 详情弹窗 -->
    <v-dialog v-model="showDetailModal" max-width="860">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-webhook</v-icon>
          联动事件详情
          <v-spacer />
          <v-chip v-if="selectedEvent" size="small" :color="statusMeta(selectedEvent.status).color" variant="tonal">
            {{ statusMeta(selectedEvent.status).label }}
          </v-chip>
          <v-btn icon="mdi-close" variant="text" size="small" @click="showDetailModal = false" class="ml-2" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4" style="max-height: 70vh; overflow-y: auto">
          <template v-if="selectedEvent">
            <div class="text-caption text-medium-emphasis mb-1">路径</div>
            <div class="text-body-2 mb-3 we-break-all">{{ selectedEvent.file_path }}</div>

            <div class="d-flex ga-2 flex-wrap mb-3">
              <v-chip size="small" variant="tonal" color="info">{{ selectedEvent.action }}</v-chip>
              <v-chip v-for="src in selectedEvent.sources" :key="src" size="small" variant="tonal">{{ src }}</v-chip>
              <v-chip v-if="selectedEvent.dup_count > 0" size="small" variant="tonal" color="warning">
                合并重复 {{ selectedEvent.dup_count }} 次
              </v-chip>
              <v-chip size="small" variant="tonal">执行 {{ selectedEvent.attempts }} 次</v-chip>
            </div>

            <div v-if="selectedEvent.error_message" class="mb-3">
              <div class="text-caption text-medium-emphasis mb-1">失败原因</div>
              <v-alert type="error" variant="tonal" density="compact">{{ selectedEvent.error_message }}</v-alert>
            </div>

            <div v-if="selectedEvent.is_dir && (loadingChildren || childEvents.length)" class="mb-3">
              <div class="text-caption text-medium-emphasis mb-1">目录展开的子事件（{{ childEvents.length }}）</div>
              <v-progress-circular v-if="loadingChildren" indeterminate size="20" />
              <div v-else class="we-child-list">
                <div v-for="child in childEvents" :key="child.id" class="d-flex align-center ga-2 we-child-item">
                  <v-icon size="12" :color="statusMeta(child.status).color">{{ statusMeta(child.status).icon }}</v-icon>
                  <v-tooltip location="top" max-width="420">
                    <template #activator="{ props }">
                      <span v-bind="props" class="text-caption text-truncate">{{ child.file_path }}</span>
                    </template>
                    {{ child.file_path }}
                  </v-tooltip>
                  <v-spacer />
                  <v-btn icon="mdi-replay" size="x-small" variant="text" @click="replayEvent(child)" />
                </div>
              </div>
            </div>

            <!-- 全链路执行日志：webhook 接收任务 + 队列处理/目录展开任务 -->
            <div class="mb-3">
              <div class="d-flex align-center mb-1">
                <span class="text-caption text-medium-emphasis">执行日志（全链路 {{ eventLogs.length }} 段）</span>
                <v-spacer />
                <v-btn icon="mdi-refresh" size="x-small" variant="text"
                       :disabled="!selectedEvent" @click="selectedEvent && fetchEventLogs(selectedEvent.id)" />
              </div>
              <v-progress-circular v-if="loadingLogs" indeterminate size="20" />
              <template v-else-if="eventLogs.length">
                <div v-for="t in eventLogs" :key="t.task_id" class="we-task-log mb-2">
                  <div class="d-flex align-center ga-2 we-task-header">
                    <v-icon size="14" class="flex-shrink-0">mdi-text-box-outline</v-icon>
                    <span class="text-caption font-weight-medium text-truncate">{{ t.name || t.module }}</span>
                    <v-chip size="x-small" variant="tonal" class="flex-shrink-0">{{ t.module }}</v-chip>
                  </div>
                  <div class="we-log-lines">
                    <div v-for="(log, i) in t.logs" :key="i" class="we-log-line">
                      <span class="we-log-time">{{ log.time }}</span>
                      <span :class="['we-log-level', (log.level || '').toLowerCase()]">{{ log.level }}</span>
                      <span class="we-log-msg">{{ log.message }}</span>
                    </div>
                  </div>
                </div>
              </template>
              <div v-else class="text-caption text-medium-emphasis">暂无关联任务日志</div>
            </div>

            <div class="text-caption text-medium-emphasis mb-1">原始 payload（重放时使用）</div>
            <pre class="we-payload">{{ payloadText }}</pre>

            <div class="d-flex ga-2 mt-3 text-caption text-medium-emphasis flex-wrap">
              <span>首次到达: {{ formatTime(selectedEvent.first_seen_at) }}</span>
              <span>最近到达: {{ formatTime(selectedEvent.last_event_at) }}</span>
            </div>
          </template>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-btn variant="text" size="small" color="info" prepend-icon="mdi-open-in-new"
                 :disabled="!selectedEvent?.task_id" @click="goTaskCenter">在任务中心打开</v-btn>
          <v-spacer />
          <v-btn variant="tonal" size="small" color="primary" prepend-icon="mdi-replay"
                 @click="selectedEvent && replayEvent(selectedEvent)">重放</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.we-failed-card {
  border-left: 3px solid rgb(var(--v-theme-error));
}

.we-break-all {
  word-break: break-all;
}

.we-child-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 6px;
  padding: 4px 8px;
}

.we-child-item {
  padding: 3px 0;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}

.we-child-item:last-child {
  border-bottom: none;
}

.we-task-log {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 6px;
  overflow: hidden;
}

.we-task-header {
  padding: 6px 10px;
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.we-log-lines {
  font-family: monospace;
  font-size: 12px;
  padding: 8px 10px;
  max-height: 220px;
  overflow-y: auto;
}

.we-log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}

.we-log-time {
  min-width: 75px;
  flex-shrink: 0;
}

.we-log-level {
  min-width: 40px;
  font-weight: bold;
  flex-shrink: 0;
}

.we-log-level.info { color: #52c41a; }
.we-log-level.error { color: #ff4d4f; }
.we-log-level.warning { color: #faad14; }

.we-log-msg {
  flex: 1;
  word-break: break-all;
}

.we-payload {
  font-family: monospace;
  font-size: 12px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 6px;
  padding: 12px;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
