<script setup lang="ts">
/**
 * TaskHistoryView — 任务中心
 *
 * 功能对标旧前端 TaskHistoryViewDesktop:
 * - 任务列表（卡片式） + 无限滚动加载
 * - 按模块筛选（整理 / STRM / RSS / 识别 / 规则同步 / 订阅补全 / 死种清理 / Webhook联动）
 * - 搜索任务名称
 * - 任务详情弹窗 + 分组日志展示
 * - WebSocket 实时推送（任务变更 + 运行中任务实时日志）
 * - 模块特定统计信息展示
 * - 删除 / 清理旧记录
 */
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { taskHistoryApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { useWebSocket } from '@/composables'
import { getStatusTag } from '@/utils/taskStatus'

defineOptions({ name: 'TaskHistoryView' })

const { success, error: showError, info } = useNotification()
const { confirm } = useConfirm()

// --- 数据 ---
const tasks = ref<any[]>([])
const loading = ref(false)
const moduleFilter = ref<string>('all')
const searchQuery = ref('')
const page = ref(0)
const pageSize = ref(20)
const hasMore = ref(true)

// --- 任务详情弹窗 ---
const showLogModal = ref(false)
const selectedTask = ref<any>(null)

// --- WebSocket ---
const { on, onReconnect } = useWebSocket()
let unsubTaskRecord: (() => void) | null = null
let unsubTaskLog: (() => void) | null = null
let unsubReconnect: (() => void) | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

// --- 模块选项 ---
const moduleOptions = computed(() => [
  { title: '全部', value: 'all' },
  { title: '整理', value: '整理' },
  { title: 'STRM', value: 'STRM' },
  { title: 'RSS', value: 'RSS' },
  { title: '识别', value: '识别' },
  { title: '规则同步', value: '规则同步' },
  { title: '订阅补全', value: '订阅补全' },
  { title: '死种清理', value: '死种清理' },
  { title: 'Webhook联动', value: 'Webhook联动' },
])

// --- 分组日志 ---
const selectedTaskGroupedLogs = computed(() => {
  const item = selectedTask.value
  if (!item?.logs?.length) return []

  const datePrefix = item.started_at
    ? new Date(item.started_at).toLocaleDateString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
      }).replace(/\//g, '/')
    : null

  const groups = new Map<string, any[]>()
  for (const log of item.logs) {
    const key = log.time?.split('.')?.[0] || log.time || '--:--:--'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(log)
  }

  return Array.from(groups.entries()).map(([groupTime, logs]) => ({
    groupTime,
    displayTime: datePrefix ? `${datePrefix} ${groupTime}` : groupTime,
    logs,
  }))
})

// --- 搜索防抖 ---
let searchDebounce: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    fetchTasks()
  }, 400)
})

// --- 方法 ---
async function fetchData(isRefresh = false) {
  if (loading.value) return
  if (isRefresh) {
    page.value = 0
    hasMore.value = true
  }
  if (!hasMore.value) return

  loading.value = true
  try {
    const offset = page.value * pageSize.value
    const params: any = { limit: pageSize.value, offset }
    if (moduleFilter.value !== 'all') params.module = moduleFilter.value
    if (searchQuery.value) params.search = searchQuery.value

    const data = await taskHistoryApi.getTaskList(params)
    const items = Array.isArray(data) ? data : (data?.items || data?.data || [])

    if (isRefresh) {
      tasks.value = items
    } else {
      tasks.value.push(...items)
    }

    if (items.length < pageSize.value) {
      hasMore.value = false
    } else {
      page.value++
    }
  } catch (e) {
    showError('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

function loadMore() {
  fetchData(false)
}

function fetchTasks() {
  fetchData(true)
}

// 模块变化时重新加载
watch(moduleFilter, () => fetchTasks())

// 无限滚动
const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function setupObserver(el: HTMLElement) {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      loadMore()
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
      loadMore()
    }
  }
})

// 实时日志自动滚动
watch(selectedTaskGroupedLogs, async () => {
  if (showLogModal.value) {
    await nextTick()
    const scrollArea = document.querySelector('.log-scroll-area')
    if (scrollArea) {
      scrollArea.scrollTop = scrollArea.scrollHeight
    }
  }
})

// 弹窗关闭时取消日志流订阅
watch(showLogModal, (val) => {
  if (!val && unsubTaskLog) {
    unsubTaskLog()
    unsubTaskLog = null
  }
})

async function fetchTaskDetail(taskId: string) {
  loading.value = true
  try {
    const data = await taskHistoryApi.getTaskDetail(taskId)
    selectedTask.value = data
    showLogModal.value = true
    // 任务运行中：订阅实时日志流
    if (selectedTask.value?.status === 'running') {
      subscribeTaskLogs(taskId)
    }
  } catch (e) {
    showError('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

function subscribeTaskLogs(taskId: string) {
  if (unsubTaskLog) unsubTaskLog()
  unsubTaskLog = on('task_log', (data: any) => {
    if (data?.task_id === taskId && selectedTask.value) {
      const logs = [...(selectedTask.value.logs || []), data.log]
      selectedTask.value = { ...selectedTask.value, logs }
    }
  })
}

async function deleteTask(taskId: string) {
  const ok = await confirm({
    title: '确认删除',
    content: '确定要删除这条任务历史记录吗？',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await taskHistoryApi.deleteTask(taskId)
    success('任务记录已删除')
    fetchTasks()
  } catch (e) {
    showError('删除失败')
  }
}

async function cleanupTasks() {
  const ok = await confirm({
    title: '清理旧记录',
    content: '确定要清理超过 30 天的任务记录吗？',
    confirmColor: 'warning',
  })
  if (!ok) return
  try {
    const data = await taskHistoryApi.cleanup()
    if (data?.status === 'success' || data?.success) {
      success(data?.message || '清理完成')
      fetchTasks()
    } else {
      showError(data?.message || '清理失败')
    }
  } catch (e) {
    showError('清理失败')
  }
}

// --- 格式化方法 ---
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '-'
  const s = new Date(start).getTime()
  const e = new Date(end).getTime()
  const sec = Math.floor((e - s) / 1000)
  if (sec < 60) return `${sec}秒`
  if (sec < 3600) return `${Math.floor(sec / 60)}分${sec % 60}秒`
  return `${Math.floor(sec / 3600)}时${Math.floor((sec % 3600) / 60)}分`
}

function getTaskStats(task: any): string | null {
  const stats = task.stats || {}
  const module = task.module

  if (module === 'RSS') {
    const parts = []
    if (stats.total_feeds) parts.push(`${stats.total_feeds}个源`)
    if (stats.total_items) parts.push(`${stats.total_items}项`)
    if (stats.total_matched) parts.push(`${stats.total_matched}项匹配`)
    return parts.join(' | ') || null
  } else if (module === '整理') {
    const parts = []
    if (stats.mode) parts.push(stats.mode)
    if (stats.success) parts.push(`成功${stats.success}`)
    if (stats.skipped) parts.push(`跳过${stats.skipped}`)
    if (stats.errors) parts.push(`失败${stats.errors}`)
    return parts.join(' | ') || null
  } else if (module === '死种清理') {
    if (stats.total_stalled) return `清理${stats.total_stalled}个`
  } else if (module === 'STRM') {
    const parts = []
    if (stats.success) parts.push(`成功${stats.success}`)
    if (stats.skipped) parts.push(`跳过${stats.skipped}`)
    if (stats.errors) parts.push(`失败${stats.errors}`)
    return parts.join(' | ') || null
  } else if (module === '规则同步') {
    const parts = []
    if (stats.total) parts.push(`共${stats.total}条`)
    if (stats.noise) parts.push(`噪声${stats.noise}`)
    if (stats.groups) parts.push(`制作组${stats.groups}`)
    if (stats.render) parts.push(`渲染${stats.render}`)
    if (stats.privileged) parts.push(`特权${stats.privileged}`)
    return parts.join(' | ') || null
  } else if (module === '订阅补全') {
    if (stats.total_pushed) return `推送${stats.total_pushed}项`
  } else if (module === '识别') {
    const parts = []
    if (stats.title) parts.push(stats.title)
    if (stats.tmdb_id) parts.push(`ID:${stats.tmdb_id}`)
    if (stats.category) parts.push(stats.category)
    if (stats.category === '剧集') {
      const season = stats.season != null ? String(stats.season).padStart(2, '0') : null
      const episode = stats.episode != null ? String(stats.episode).padStart(2, '0') : null
      if (season && episode) parts.push(`S${season}E${episode}`)
      else if (season) parts.push(`S${season}`)
      else if (episode) parts.push(`E${episode}`)
    }
    return parts.join(' | ') || null
  }
  return null
}

// --- 生命周期 ---
onMounted(() => {
  fetchTasks()

  // 订阅 WS 事件：任务记录变更时刷新列表
  unsubTaskRecord = on('task_record', () => {
    if (!loading.value && !showLogModal.value) {
      fetchTasks()
    }
  })

  // 重连后重新拉取
  unsubReconnect = onReconnect(() => {
    fetchTasks()
  })

  // 定时刷新（作为 WS 不可用时的 fallback）
  refreshTimer = setInterval(() => {
    if (!loading.value && !showLogModal.value) {
      fetchTasks()
    }
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (unsubTaskRecord) { unsubTaskRecord(); unsubTaskRecord = null }
  if (unsubTaskLog) { unsubTaskLog(); unsubTaskLog = null }
  if (unsubReconnect) { unsubReconnect(); unsubReconnect = null }
  if (observer) observer.disconnect()
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between flex-wrap ga-3">
      <div>
        <h1 class="page-title text-h5 font-weight-bold">任务中心</h1>
        <div class="page-subtitle text-body-2 text-medium-emphasis mt-1">任务执行历史与日志</div>
      </div>
      <div class="d-flex ga-2 align-center">
        <v-btn variant="tonal" color="warning" prepend-icon="mdi-broom" @click="cleanupTasks">清理旧记录</v-btn>
      </div>
    </div>

    <!-- 搜索与筛选 -->
    <div class="d-flex ga-3 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="searchQuery"
        label="搜索任务名称..."
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        class="task-search-field"
        style="max-width: 240px"
      />
      <v-select
        v-model="moduleFilter"
        :items="moduleOptions"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 160px"
        item-title="title"
        item-value="value"
      />
    </div>

    <!-- 任务列表 -->
    <v-skeleton-loader v-if="loading && tasks.length === 0" type="card@4" />

    <template v-else-if="tasks.length > 0">
      <div v-for="task in tasks" :key="task.task_id" class="mb-3">
        <v-card class="glass-card hover-lift th-task-card">
          <v-card-text class="pb-0">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="d-flex align-center ga-2 flex-grow-1" style="min-width: 0">
                <v-chip size="small" :color="getStatusTag(task.status).color" variant="tonal">
                  {{ getStatusTag(task.status).label }}
                </v-chip>
                <span class="text-subtitle-2 font-weight-bold text-truncate">{{ task.name || task.module }}</span>
              </div>
              <span class="text-caption text-medium-emphasis flex-shrink-0">{{ formatTime(task.started_at) }}</span>
            </div>
          </v-card-text>

          <v-card-text class="pt-0 pb-2">
            <div class="d-flex ga-4 text-caption text-medium-emphasis flex-wrap">
              <span v-if="task.status === 'completed'">
                <v-icon size="12" class="mr-1">mdi-timer-outline</v-icon>
                耗时 {{ formatDuration(task.started_at, task.finished_at) }}
              </span>
              <span v-if="getTaskStats(task)">
                <v-icon size="12" class="mr-1">mdi-chart-box-outline</v-icon>
                {{ getTaskStats(task) }}
              </span>
              <span v-else-if="task.processed != null">
                <v-icon size="12" class="mr-1">mdi-file-multiple-outline</v-icon>
                处理 {{ task.processed }} 项
              </span>
            </div>
          </v-card-text>

          <v-divider />
          <v-card-actions class="pa-2">
            <v-spacer />
            <v-btn variant="tonal" size="small" color="info" prepend-icon="mdi-text-box-outline" @click="fetchTaskDetail(task.task_id)">日志</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteTask(task.task_id)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </div>

      <!-- 无限滚动触发器 -->
      <div ref="scrollTarget" class="text-center pa-4">
        <v-progress-circular v-if="loading" indeterminate size="24" />
        <div v-else-if="!hasMore" class="text-caption text-medium-emphasis">
          <v-divider class="mb-3" />
          到底了，共 {{ tasks.length }} 条记录
        </div>
        <div v-else class="text-caption text-medium-emphasis d-flex align-center justify-center ga-2">
          <v-icon size="16">mdi-chevron-double-down</v-icon>
          向下滚动加载更多
        </div>
      </div>
    </template>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-clipboard-list-outline</v-icon>
      <div class="text-h6 font-weight-medium">暂无任务记录</div>
      <div class="text-body-2 text-medium-emphasis mt-2">执行整理或识别任务后记录会出现在这里</div>
    </div>

    <!-- 日志弹窗 -->
    <v-dialog v-model="showLogModal" max-width="960">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-text-box-outline</v-icon>
          任务日志
          <v-spacer />
          <v-chip v-if="selectedTask" size="small" :color="getStatusTag(selectedTask.status).color" variant="tonal">
            {{ getStatusTag(selectedTask.status).label }}
          </v-chip>
          <v-btn icon="mdi-close" variant="text" size="small" @click="showLogModal = false" class="ml-2" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4 log-scroll-area" style="max-height: 70vh; overflow-y: auto">
          <div v-if="selectedTask?.logs?.length" class="th-log-container">
            <div v-for="group in selectedTaskGroupedLogs" :key="group.groupTime" class="log-group">
              <div class="log-group-time">{{ group.displayTime }}</div>
              <div class="log-group-line"></div>
              <div class="log-group-items">
                <div v-for="(log, i) in group.logs" :key="i" class="log-line">
                  <span class="log-time">{{ log.time }}</span>
                  <span :class="['log-level', (log.level || '').toLowerCase()]">{{ log.level }}</span>
                  <span class="log-msg">{{ log.message }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center pa-8">
            <v-icon size="48" color="primary" class="mb-3">mdi-text-box-remove-outline</v-icon>
            <div class="text-body-2 text-medium-emphasis">暂无日志</div>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.th-task-card {
  transition: all 0.2s ease;
}

.th-log-container {
  font-family: monospace;
  font-size: 13px;
}
.log-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.log-group:last-child {
  border-bottom: none;
}
.log-group-time {
  color: rgb(var(--v-theme-primary));
  font-size: 11px;
  min-width: 130px;
  flex-shrink: 0;
  padding-top: 2px;
  font-weight: 700;
}
.log-group-line {
  width: 2px;
  background-color: rgb(var(--v-theme-primary));
  border-radius: 1px;
  flex-shrink: 0;
  align-self: stretch;
  margin: 4px 0;
  opacity: 0.6;
}
.log-group-items {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}
.log-time {
  color: rgba(var(--v-theme-on-surface), 0.5);
  min-width: 75px;
}
.log-level {
  min-width: 40px;
  font-weight: bold;
}
.log-level.info { color: #52c41a; }
.log-level.error { color: #ff4d4f; }
.log-level.warning { color: #faad14; }
.log-msg {
  flex: 1;
  word-break: break-all;
}
</style>
