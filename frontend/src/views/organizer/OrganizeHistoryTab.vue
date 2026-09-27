<script setup lang="ts">
/**
 * OrganizeHistoryTab — 整理历史
 *
 * 功能对齐全旧前端:
 * - 元数据 Tags (季集/类型/分辨率/编码/字幕组)
 * - 路径容器 (源→目标 竖向布局)
 * - 底部详情 (转移方式/文件大小/时间/TMDB链接/失败原因)
 * - 识别日志查看弹框 (task_id 关联)
 * - 删除确认带物理删除选项
 * - 跳过/失败消息行
 */
import { ref, onMounted } from 'vue'
import { organizerApi, taskHistoryApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import ExecutionLogModal from './ExecutionLogModal.vue'

defineOptions({ name: 'OrganizeHistoryTab' })

const { success, error: showError, warning, info } = useNotification()
const { confirm } = useConfirm()

const historyList = ref<any[]>([])
const historyLoading = ref(false)
const historyOffset = ref(0)
const historyHasMore = ref(true)
const historyStatusFilter = ref<string>('all')
const historySearch = ref('')
// 筛选模式: all=全部时间 / top=最近N条 / days=最近N天 / range=自定义日期范围
const historyFilterMode = ref<string>('all')
const historyTopCount = ref<number>(100)
const historyDaysCount = ref<number>(30)
const historyStartDate = ref('')
const historyEndDate = ref('')

// --- 日志查看弹框 ---
const showLogModal = ref(false)
const logTaskId = ref('')

/** 组装当前筛选对应的查询参数（列表查询与批量联动共用） */
function buildFilterParams(): Record<string, any> {
  const p: Record<string, any> = {}
  if (historyStatusFilter.value !== 'all') p.status = historyStatusFilter.value
  if (historySearch.value) p.search = historySearch.value
  if (historyFilterMode.value === 'top') {
    if (historyTopCount.value > 0) p.top = historyTopCount.value
  } else if (historyFilterMode.value === 'days') {
    if (historyDaysCount.value > 0) p.days = historyDaysCount.value
  } else if (historyFilterMode.value === 'range') {
    if (historyStartDate.value) p.start_date = historyStartDate.value
    if (historyEndDate.value) p.end_date = historyEndDate.value
  }
  return p
}

async function fetchHistory(isRefresh = false) {
  if (historyLoading.value) return
  if (isRefresh) {
    historyOffset.value = 0
    historyHasMore.value = true
  }
  if (!historyHasMore.value && !isRefresh) return

  historyLoading.value = true
  try {
    const filters = buildFilterParams()
    // "最近 N 条"模式下一次拉全，无分页
    const isTopMode = historyFilterMode.value === 'top' && filters.top
    const data = await organizerApi.getHistory({
      limit: isTopMode ? filters.top : 20,
      offset: isTopMode ? 0 : historyOffset.value,
      ...filters,
    })
    const items = Array.isArray(data) ? data : (data?.items || data?.data || [])
    if (isRefresh) {
      historyList.value = items
    } else {
      historyList.value = [...historyList.value, ...items]
    }
    historyHasMore.value = isTopMode ? false : items.length >= 20
    historyOffset.value += items.length
  } catch (e) {
    // 静默
  } finally {
    historyLoading.value = false
  }
}

function filterHistory(status?: string) {
  historyStatusFilter.value = status || 'all'
  fetchHistory(true)
}

function searchHistory() {
  fetchHistory(true)
}

async function retryHistoryItem(historyId: number) {
  const ok = await confirm({
    title: '确认重试',
    content: '将根据源路径重新执行识别与整理流程（绕过历史去重）。进度可在「任务历史」中查看。',
    confirmText: '确定重试',
  })
  if (!ok) return
  try {
    const data = await organizerApi.retryHistory(historyId)
    if (data?.success) {
      success(data.message || '重试已启动')
    } else {
      showError(data?.message || '重试失败')
    }
  } catch (e: any) {
    showError('重试失败: ' + e.message)
  }
}

async function deleteHistoryItem(item: any) {
  let deleteFile = false
  const ok = await confirm({
    title: '确认删除',
    content: '确定要删除这条整理记录吗？',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await organizerApi.deleteHistory(item.id, deleteFile)
    success('已删除')
    historyList.value = historyList.value.filter((h: any) => h.id !== item.id)
  } catch (e) {
    showError('删除失败')
  }
}

async function clearAllHistory() {
  const ok = await confirm({ title: '确认清空', content: '确定要清空所有整理历史记录吗？此操作不可逆，不会影响磁盘上的文件。', confirmColor: 'error' })
  if (!ok) return
  try {
    await organizerApi.clearHistory()
    success('历史记录已清空')
    historyList.value = []
    historyOffset.value = 0
    historyHasMore.value = false
  } catch (e) {
    showError('清空失败')
  }
}

// --- 日志查看 ---
function viewTaskLog(item: any) {
  if (!item.task_id) {
    warning('该记录未关联识别日志（旧数据不支持查看日志）')
    return
  }
  logTaskId.value = item.task_id
  showLogModal.value = true
}

// --- STRM 联动（单条独立生成 / 按筛选批量生成，避免全库遍历） ---
const strmLinkLoadingId = ref<number | null>(null)
const strmLinkBatchLoading = ref(false)

function currentStrmFilters() {
  return { select_all: true, ...buildFilterParams() }
}

async function strmLinkItem(item: any) {
  const ok = await confirm({
    title: '确认生成 STRM',
    content: '将对该记录的目标文件执行 STRM 联动：匹配 STRM 任务后生成 STRM，并同步源目录中已存在的元数据/字幕（不会向 TMDB 拉取新元数据）。进度可在「任务历史」中查看。',
    confirmText: '开始执行',
  })
  if (!ok) return
  strmLinkLoadingId.value = item.id
  try {
    const data = await organizerApi.strmLinkHistory({ history_ids: [item.id] })
    if (data?.success) {
      success('已提交后台执行，进度可在「任务历史」中查看')
    } else {
      showError(data?.message || '提交失败')
    }
  } catch (e: any) {
    showError('提交失败: ' + e.message)
  } finally {
    strmLinkLoadingId.value = null
  }
}

/** 按当前筛选条件批量执行 STRM 联动（服务端按条件全量处理，不依赖已加载条数） */
async function strmLinkFiltered() {
  strmLinkBatchLoading.value = true
  let matched = 0
  try {
    const data = await organizerApi.strmLinkHistory({ ...currentStrmFilters(), count_only: true })
    matched = data?.matched ?? 0
  } catch (e: any) {
    showError('查询命中数量失败: ' + e.message)
    strmLinkBatchLoading.value = false
    return
  }
  strmLinkBatchLoading.value = false

  if (!matched) {
    warning('当前筛选条件下没有可处理的记录（需为成功/跳过状态且有目标路径）')
    return
  }
  const ok = await confirm({
    title: '按筛选条件批量生成 STRM',
    content: `当前筛选条件下共命中 ${matched} 条记录（成功/跳过），将逐条匹配 STRM 任务并生成 STRM + 同步源目录已存在的元数据/字幕。进度可在「任务历史」中查看。`,
    confirmText: `开始执行 (${matched})`,
  })
  if (!ok) return
  strmLinkBatchLoading.value = true
  try {
    const data = await organizerApi.strmLinkHistory(currentStrmFilters())
    if (data?.success) {
      success(`已提交后台执行，共 ${data.matched} 条，进度可在「任务历史」中查看`)
    } else {
      showError(data?.message || '提交失败')
    }
  } catch (e: any) {
    showError('提交失败: ' + e.message)
  } finally {
    strmLinkBatchLoading.value = false
  }
}

// --- 辅助函数 ---
function historyStatusColor(status: string): string {
  if (status === 'success') return 'success'
  if (status === 'failed' || status === 'error') return 'error'
  if (status === 'skipped') return 'warning'
  return 'default'
}

function historyStatusLabel(status: string): string {
  if (status === 'success') return '成功'
  if (status === 'failed' || status === 'error') return '失败'
  if (status === 'skipped') return '跳过'
  return status || '-'
}

function getActionLabel(type: string): string {
  const map: Record<string, string> = {
    move: '移动',
    copy: '复制',
    link: '硬链',
    symlink: '符号链接',
    hardlink: '硬链接',
    cd2_move: 'CD2移动',
    cd2_copy: 'CD2复制',
  }
  return map[type] || type || '-'
}

function formatTime(timeStr: string): string {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').split('.')[0]
}

function getTmdbUrl(item: any): string {
  if (!item.tmdb_id) return ''
  const type = item.media_type === '电影' ? 'movie' : 'tv'
  return `https://www.themoviedb.org/${type}/${item.tmdb_id}`
}

// 首次挂载时自动加载数据
onMounted(() => {
  if (historyList.value.length === 0) {
    fetchHistory()
  }
})

// 暴露 fetchHistory 给父组件
defineExpose({ fetchHistory })
</script>

<template>
  <div>
    <!-- 筛选栏 -->
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="historySearch"
        label="搜索标题或文件名"
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        class="org-search-field"
        @keyup.enter="searchHistory"
        @click:clear="historySearch = ''; searchHistory()"
      />
      <v-chip :color="historyStatusFilter === 'all' ? 'primary' : undefined" :variant="historyStatusFilter === 'all' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterHistory()">全部</v-chip>
      <v-chip :color="historyStatusFilter === 'success' ? 'primary' : undefined" :variant="historyStatusFilter === 'success' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterHistory('success')">成功</v-chip>
      <v-chip :color="historyStatusFilter === 'failed' ? 'primary' : undefined" :variant="historyStatusFilter === 'failed' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterHistory('failed')">失败</v-chip>
      <v-chip :color="historyStatusFilter === 'skipped' ? 'primary' : undefined" :variant="historyStatusFilter === 'skipped' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterHistory('skipped')">跳过</v-chip>
      <v-spacer />
      <v-btn
        variant="tonal" color="info" size="small"
        prepend-icon="mdi-link-variant"
        :loading="strmLinkBatchLoading"
        @click="strmLinkFiltered"
      >按筛选生成 STRM</v-btn>
      <v-select
        v-model="historyFilterMode"
        :items="[
          { title: '全部时间', value: 'all' },
          { title: '最近 N 条', value: 'top' },
          { title: '最近 N 天', value: 'days' },
          { title: '日期范围', value: 'range' },
        ]"
        label="时间"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 130px"
        @update:model-value="fetchHistory(true)"
      />
      <v-text-field
        v-if="historyFilterMode === 'top'"
        v-model.number="historyTopCount"
        label="条数"
        type="number"
        min="1"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 100px"
        @keyup.enter="fetchHistory(true)"
        @blur="fetchHistory(true)"
      />
      <v-text-field
        v-if="historyFilterMode === 'days'"
        v-model.number="historyDaysCount"
        label="天数"
        type="number"
        min="1"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 100px"
        @keyup.enter="fetchHistory(true)"
        @blur="fetchHistory(true)"
      />
      <template v-if="historyFilterMode === 'range'">
        <v-text-field
          v-model="historyStartDate"
          label="开始日期"
          type="date"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 150px"
          @change="fetchHistory(true)"
        />
        <v-text-field
          v-model="historyEndDate"
          label="结束日期"
          type="date"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 150px"
          @change="fetchHistory(true)"
        />
      </template>
      <v-btn variant="tonal" color="error" size="small" prepend-icon="mdi-delete-sweep-outline" @click="clearAllHistory">清空历史</v-btn>
    </div>

    <v-skeleton-loader v-if="historyLoading && historyList.length === 0" type="list-item@5" />

    <div v-else-if="historyList.length > 0">
      <v-card
        v-for="item in historyList"
        :key="item.id"
        class="org-history-item glass-card mb-3 pa-4"
      >
        <!-- 1. Header: Title + Meta Tags + Status -->
        <div class="d-flex align-center justify-space-between ga-2">
          <div class="d-flex align-center ga-2 flex-wrap flex-grow-1 min-width-0">
            <span class="text-subtitle-1 font-weight-bold text-truncate">{{ item.title || item.filename || '-' }}</span>
            <span v-if="item.year" class="text-caption text-medium-emphasis">({{ item.year }})</span>
            <!-- 元数据 Tags -->
            <v-chip v-if="item.season || item.episode" size="x-small" variant="flat" class="meta-tag meta-tag--season">
              S{{ String(item.season || 0).padStart(2, '0') }}E{{ item.episode || '?' }}
            </v-chip>
            <v-chip v-if="item.media_type" size="x-small" variant="flat" class="meta-tag meta-tag--type">
              {{ item.media_type }}
            </v-chip>
            <v-chip v-if="item.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">
              {{ item.resolution }}
            </v-chip>
            <v-chip v-if="item.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">
              {{ item.video_encode }}
            </v-chip>
            <v-chip v-if="item.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">
              {{ item.team }}
            </v-chip>
          </div>
          <v-chip size="small" :color="historyStatusColor(item.status)" variant="tonal" class="flex-shrink-0">
            {{ historyStatusLabel(item.status) }}
          </v-chip>
        </div>

        <!-- 跳过消息 -->
        <v-alert v-if="item.status === 'skipped' && item.message" type="warning" density="compact" variant="tonal" class="mt-2" :text="item.message" />

        <!-- 失败消息 -->
        <v-alert v-if="(item.status === 'failed' || item.status === 'error') && item.message" type="error" density="compact" variant="tonal" class="mt-2" :text="item.message" />

        <!-- 2. Paths (Vertical Stacked) -->
        <div v-if="item.source_path" class="org-path-container mt-3">
          <div class="org-path-item">
            <v-chip
              v-if="item.source_via"
              size="x-small"
              variant="flat"
              class="meta-tag flex-shrink-0"
              :class="item.source_via === 'cd2' ? 'meta-tag--via-cd2' : 'meta-tag--via-local'"
            >
              {{ item.source_via === 'cd2' ? 'CD2' : '本地' }}
            </v-chip>
            <span class="org-path-text" :title="item.source_path">{{ item.source_path }}</span>
          </div>
          <div class="org-path-divider">
            <v-icon size="14">mdi-arrow-down</v-icon>
          </div>
          <div v-if="item.target_path" class="org-path-item">
            <v-chip
              v-if="item.target_via"
              size="x-small"
              variant="flat"
              class="meta-tag flex-shrink-0"
              :class="item.target_via === 'cd2' ? 'meta-tag--via-cd2' : 'meta-tag--via-local'"
            >
              {{ item.target_via === 'cd2' ? 'CD2' : '本地' }}
            </v-chip>
            <span class="org-path-text org-path-target" :title="item.target_path">{{ item.target_path }}</span>
          </div>
        </div>

        <!-- 随行文件（字幕/音轨）去向 -->
        <div v-if="item.related_files?.length" class="mt-2 related-files-box">
          <div class="related-files-title">
            <v-icon size="13" class="mr-1">mdi-paperclip</v-icon>随行文件 ({{ item.related_files.length }})
          </div>
          <div v-for="(rf, i) in item.related_files" :key="i" class="related-file-item">
            <div class="related-file-head">
              <v-icon size="13" :color="rf.status === 'success' ? 'success' : (rf.status === 'skipped' ? 'warning' : 'error')">
                {{ rf.status === 'success' ? 'mdi-check-circle' : (rf.status === 'skipped' ? 'mdi-skip-next' : 'mdi-alert-circle') }}
              </v-icon>
              <span class="related-file-name">{{ rf.filename }}</span>
            </div>
            <div v-if="rf.target_path" class="related-file-target" :title="rf.target_path">→ {{ rf.target_path }}</div>
          </div>
        </div>

        <!-- 3. Footer: Details + Actions -->
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mt-3">
          <div class="d-flex align-center ga-2 flex-wrap min-width-0">
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--action" v-if="item.action_type">
              {{ getActionLabel(item.action_type) }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--size" v-if="item.file_size">
              {{ item.file_size }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--time" v-if="item.processed_at">
              {{ formatTime(item.processed_at) }}
            </v-chip>
            <v-chip
              v-if="item.tmdb_id"
              :href="getTmdbUrl(item)"
              target="_blank"
              size="x-small"
              variant="flat"
              class="meta-tag meta-tag--tmdb"
            >
              TMDB: {{ item.tmdb_id }}
            </v-chip>
          </div>
          <div class="d-flex align-center ga-1 flex-shrink-0">
            <v-btn
              v-if="item.target_path && item.status !== 'failed'"
              size="small" variant="tonal" color="success"
              prepend-icon="mdi-link-variant"
              :loading="strmLinkLoadingId === item.id"
              @click="strmLinkItem(item)"
            >STRM</v-btn>
            <v-btn v-if="item.task_id" size="small" variant="tonal" color="info" prepend-icon="mdi-file-document-outline" @click="viewTaskLog(item)">日志</v-btn>
            <v-btn size="small" variant="tonal" color="warning" prepend-icon="mdi-refresh" @click="retryHistoryItem(item.id)">重试</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteHistoryItem(item)">删除</v-btn>
          </div>
        </div>
      </v-card>

      <div class="text-center pa-4">
        <v-btn v-if="historyHasMore" variant="tonal" prepend-icon="mdi-chevron-down" :loading="historyLoading" @click="fetchHistory()">加载更多</v-btn>
        <div v-else class="text-caption text-medium-emphasis">到底了，共 {{ historyList.length }} 条记录</div>
      </div>
    </div>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-history</v-icon>
      <div class="text-h6 font-weight-medium">暂无整理历史</div>
      <div class="text-body-2 text-medium-emphasis mt-2">执行整理任务后，历史记录会显示在这里</div>
    </div>

    <!-- 识别日志查看弹框 -->
    <ExecutionLogModal v-model="showLogModal" :task-id="logTaskId" />
  </div>
</template>

<style scoped>
.history-filter-chip {
  height: 40px !important;
}

/* 随行文件（字幕/音轨）去向：文件名一行、目标路径一行 */
.related-files-box {
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.related-files-title {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
  margin-bottom: 4px;
}

.related-file-item {
  padding: 1px 0 1px 6px;
}

.related-file-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.related-file-name {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
}

.related-file-target {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
  padding-left: 21px;
}
</style>
