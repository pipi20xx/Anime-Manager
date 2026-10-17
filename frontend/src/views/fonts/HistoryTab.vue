<script setup lang="ts">
/**
 * HistoryTab — 字体管家·处理历史
 *
 * 整理任务联动产生的随行字幕子集化记录：成功也记、缺字体也记。
 * 每条都存了「交付路径」，所以补齐字体后可以直接按路径重新子集化；
 * 即使字幕被改名（多了 .assfonts 标记）也能在同目录按主干找到。
 */
import { ref, computed, onMounted, watch } from 'vue'
import { fontManagerApi } from '@/api'
import type { FontSubsetHistoryItem } from '@/api/fontManager'
import { useFontManager, formatFileSize, formatDateTime } from './useFontManager'
import { EmptyState } from '@/components/common'

defineOptions({ name: 'FontManagerHistoryTab' })

const { success, showError, warning, confirm } = useFontManager()

const items = ref<FontSubsetHistoryItem[]>([])
const counts = ref<Record<string, number>>({})
const total = ref(0)
const loading = ref(false)
const busy = ref<Record<number, boolean>>({})
const bulkRunning = ref(false)
const clearing = ref(false)
const statusFilter = ref('')
const search = ref('')

const statusItems = computed(() => [
  { title: `全部 ${counts.value.total || 0}`, value: '' },
  { title: `已内嵌 ${counts.value.success || 0}`, value: 'success' },
  { title: `缺字体 ${counts.value.missing || 0}`, value: 'missing' },
  { title: `失败 ${counts.value.failed || 0}`, value: 'failed' },
  { title: `跳过 ${counts.value.skipped || 0}`, value: 'skipped' },
])

const retryable = computed(() => (counts.value.missing || 0) + (counts.value.failed || 0))

function statusMeta(status: string) {
  switch (status) {
    case 'success':
      return { icon: 'mdi-check-circle', color: 'success', label: '已内嵌' }
    case 'missing':
      return { icon: 'mdi-format-font', color: 'warning', label: '缺字体' }
    case 'failed':
      return { icon: 'mdi-alert-circle', color: 'error', label: '失败' }
    case 'skipped':
      return { icon: 'mdi-skip-next-circle-outline', color: 'info', label: '已跳过' }
    default:
      return { icon: 'mdi-help-circle-outline', color: 'grey', label: status || '未知' }
  }
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await fontManagerApi.listSubsetHistory({
      status: statusFilter.value || undefined,
      q: search.value.trim() || undefined,
      limit: 300,
    })
    items.value = res?.data || []
    counts.value = res?.counts || {}
    total.value = res?.total || 0
  } catch (e: any) {
    showError(e?.message || '读取处理历史失败')
  } finally {
    loading.value = false
  }
}

async function retryOne(item: FontSubsetHistoryItem) {
  busy.value = { ...busy.value, [item.id]: true }
  try {
    const res = await fontManagerApi.retrySubsetHistory(item.id)
    const data = res?.data
    if (data?.status === 'success') {
      success(`已内嵌：${data.target_name || item.source_name}（${formatFileSize(data.file_size)}）`)
    } else if (data?.status === 'missing') {
      warning(`仍缺字体：${(data.missing_fonts || []).join('、') || '未知'}`)
    } else if (data?.status === 'skipped') {
      warning(data.last_error || '该字幕已内嵌字体，无需处理')
    } else {
      showError(data?.last_error || '重新子集化失败')
    }
    await fetchHistory()
  } catch (e: any) {
    showError(e?.message || '重新子集化失败')
  } finally {
    const next = { ...busy.value }
    delete next[item.id]
    busy.value = next
  }
}

async function retryBulk() {
  if (!retryable.value) {
    warning('没有缺字体或失败的记录')
    return
  }
  bulkRunning.value = true
  try {
    const res = await fontManagerApi.retrySubsetHistoryBulk('missing', 50)
    const s = res?.summary || {}
    const msg = `批量重试完成：成功 ${s.success || 0} / 仍缺字体 ${s.missing || 0} / 失败 ${s.failed || 0}`
    if ((s.success || 0) > 0) success(msg)
    else warning(msg)
    await fetchHistory()
  } catch (e: any) {
    showError(e?.message || '批量重试失败')
  } finally {
    bulkRunning.value = false
  }
}

async function removeOne(item: FontSubsetHistoryItem) {
  const ok = await confirm({
    title: '删除记录',
    content: `确定删除「${item.source_name}」这条处理历史吗？（只删记录，不动文件）`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await fontManagerApi.deleteSubsetHistory(item.id)
    await fetchHistory()
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

async function clearHistory(keepUnresolved: boolean) {
  const ok = await confirm({
    title: keepUnresolved ? '清理已完成记录' : '清空全部记录',
    content: keepUnresolved
      ? '将删除「已内嵌 / 已跳过」的记录，缺字体与失败的记录会保留，方便补完字体后重试。'
      : '将删除全部处理历史（不可恢复，只删记录不动文件）。',
    confirmColor: 'error',
  })
  if (!ok) return
  clearing.value = true
  try {
    const res = await fontManagerApi.clearSubsetHistory(keepUnresolved)
    success(`已清理 ${res?.removed ?? 0} 条记录`)
    await fetchHistory()
  } catch (e: any) {
    showError(e?.message || '清理失败')
  } finally {
    clearing.value = false
  }
}

async function copyPath(path: string) {
  if (!path) return
  try {
    await navigator.clipboard.writeText(path)
    success('已复制路径')
  } catch {
    showError('复制失败，请手动选择文本')
  }
}

function episodeLabel(item: FontSubsetHistoryItem): string {
  if (item.season == null && !item.episode) return ''
  const s = item.season != null ? `S${item.season}` : ''
  const e = item.episode ? `E${item.episode}` : ''
  return `${s}${e}`
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => fetchHistory(), 400)
})
watch(statusFilter, () => fetchHistory())

onMounted(fetchHistory)
</script>

<template>
  <div>
    <!-- ══ 工具条 ══ -->
    <div class="list-toolbar">
      <div class="list-toolbar__filters">
        <v-text-field
          v-model="search"
          placeholder="搜索字幕名 / 目标路径 / 番剧名…"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          style="max-width: 320px"
        />
        <v-select
          v-model="statusFilter"
          :items="statusItems"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 170px"
        />
        <span class="list-toolbar__total text-caption text-medium-emphasis">共 {{ total }} 条</span>
      </div>
      <div class="list-toolbar__actions">
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-auto-fix"
          :loading="bulkRunning"
          :disabled="!retryable"
          title="把所有「缺字体」的记录按交付路径重新子集化一次"
          @click="retryBulk"
        >
          批量重试缺字体
        </v-btn>
        <v-menu location="bottom end">
          <template #activator="{ props: menuProps }">
            <v-btn
              v-bind="menuProps"
              size="small"
              variant="tonal"
              color="warning"
              prepend-icon="mdi-broom"
              :loading="clearing"
            >
              清理
              <v-icon end size="16">mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact" nav>
            <v-list-item
              prepend-icon="mdi-check-circle-outline"
              title="清理已完成"
              subtitle="只删已内嵌 / 已跳过，保留缺字体与失败"
              @click="clearHistory(true)"
            />
            <v-list-item
              prepend-icon="mdi-delete-sweep-outline"
              title="清空全部"
              subtitle="删除全部处理历史（不可恢复，不动文件）"
              base-color="error"
              @click="clearHistory(false)"
            />
          </v-list>
        </v-menu>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="fetchHistory">
          刷新
        </v-btn>
      </div>
    </div>

    <!-- ══ 列表 ══ -->
    <div v-if="loading && !items.length" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" />
    </div>

    <EmptyState
      v-else-if="!items.length"
      icon="mdi-history"
      title="还没有处理历史"
      description="在「整理任务 → 高级选项」里开启「随行字幕子集化」后，每次整理都会在这里留下记录；成功和缺字体都会记，缺字体可以直接重试。"
    />

    <template v-else>
      <v-card v-for="item in items" :key="item.id" class="glass-card mb-3" variant="flat">
        <v-card-text class="pa-4">
          <div class="d-flex align-center flex-wrap ga-2">
            <v-icon :color="statusMeta(item.status).color" size="20">{{ statusMeta(item.status).icon }}</v-icon>
            <span class="text-body-1 font-weight-medium text-truncate" style="max-width: 46%" :title="item.source_name">
              {{ item.source_name }}
            </span>
            <v-chip size="x-small" variant="flat" :color="statusMeta(item.status).color">
              {{ statusMeta(item.status).label }}
            </v-chip>
            <v-chip v-if="item.video_title" size="small" variant="tonal">
              {{ item.video_title }}<span v-if="episodeLabel(item)" class="ml-1">{{ episodeLabel(item) }}</span>
            </v-chip>
            <v-chip v-if="item.target_via === 'cd2'" size="x-small" variant="tonal" color="info" prepend-icon="mdi-cloud-outline">
              CD2
            </v-chip>
            <v-chip v-else-if="item.exists === false" size="x-small" variant="tonal" color="error" prepend-icon="mdi-link-off">
              文件已不在
            </v-chip>
            <v-chip v-if="item.attempts" size="x-small" variant="tonal" color="grey">
              重试 {{ item.attempts }} 次
            </v-chip>

            <v-spacer />

            <span v-if="item.file_size" class="text-caption text-medium-emphasis">
              {{ formatFileSize(item.file_size) }}
            </span>
            <span class="text-caption text-medium-emphasis">{{ formatDateTime(item.updated_at || item.created_at) }}</span>
          </div>

          <!-- 交付路径（可点击复制） -->
          <div class="history-path" :title="item.target_path" @click="copyPath(item.target_path)">
            <v-icon size="13" class="mr-1">mdi-file-move-outline</v-icon>{{ item.target_path }}
          </div>

          <!-- 缺字体 / 引用字体 -->
          <div v-if="item.missing_fonts?.length" class="d-flex flex-wrap ga-1 mt-2">
            <v-chip
              v-for="f in item.missing_fonts"
              :key="`miss-${f}`"
              size="x-small"
              variant="flat"
              color="warning"
              prepend-icon="mdi-format-font"
            >
              {{ f }}
            </v-chip>
          </div>
          <div v-else-if="item.referenced_fonts?.length" class="d-flex flex-wrap ga-1 mt-2">
            <v-chip v-for="f in item.referenced_fonts.slice(0, 6)" :key="`ref-${f}`" size="x-small" variant="tonal" :title="f">
              {{ f }}
            </v-chip>
            <v-chip v-if="item.referenced_fonts.length > 6" size="x-small" variant="flat" color="grey">
              +{{ item.referenced_fonts.length - 6 }}
            </v-chip>
          </div>

          <div v-if="item.last_error" class="text-caption text-error mt-2">
            {{ item.last_error }}
          </div>

          <div class="d-flex align-center flex-wrap ga-2 mt-3">
            <v-btn
              v-if="item.status !== 'success'"
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-auto-fix"
              :loading="!!busy[item.id]"
              @click="retryOne(item)"
            >
              重新子集化
            </v-btn>
            <v-btn size="small" variant="tonal" prepend-icon="mdi-content-copy" @click="copyPath(item.target_path)">
              复制路径
            </v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="removeOne(item)">
              删除
            </v-btn>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </div>
</template>

<style scoped>
.history-path {
  margin-top: 8px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  overflow-wrap: anywhere;
  cursor: pointer;
  opacity: 0.85;
}
.history-path:hover {
  color: rgb(var(--v-theme-primary));
  opacity: 1;
}
</style>
