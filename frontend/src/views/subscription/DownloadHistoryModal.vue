<script setup lang="ts">
/**
 * DownloadHistoryModal — 下载记录弹窗
 *
 * 对齐旧前端: 使用 /api/rules/history/all 富数据接口
 * - 分页加载（无限滚动）
 * - 搜索 + 站点筛选
 * - 每条记录展示: 标题、描述、规则名、状态标签、失败原因、时间、资源链接
 * - 删除单条 / 批量清除
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { subscriptionApi } from '@/api'
import { api } from '@/api/client'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{
  show: boolean
  feeds?: any[]
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

const keyword = ref('')
const selectedFeedIds = ref<number[]>([])

// 无限滚动
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
    fetchItems(false).then(() => setupObserver())
  } else { cleanupObserver() }
})

watch(() => items.value.length, () => {
  if (props.show && hasMore.value) setupObserver()
})

onBeforeUnmount(cleanupObserver)

const feedOptions = computed(() =>
  (props.feeds || []).map((f: any) => ({ title: f.title || f.url, value: f.id }))
)

// 构建 feed_id -> feed_name 映射
const feedNameMap = computed(() => {
  const map: Record<number, string> = {}
  ;(props.feeds || []).forEach((f: any) => { map[f.id] = f.title || f.url || '-' })
  return map
})

async function fetchItems(append = false) {
  if (!append) { offset.value = 0; items.value = []; hasMore.value = true }
  if (!hasMore.value) return
  loading.value = true
  try {
    const data = await subscriptionApi.getAllRuleHistory({
      limit: LIMIT,
      offset: offset.value,
      keyword: keyword.value.trim() || undefined,
    })
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

// --- 状态映射 ---
function getStateInfo(state: string): { label: string; tagClass: string } {
  switch (state) {
    case 'Success': return { label: '成功', tagClass: 'meta-tag--downloaded' }
    case 'Failed': return { label: '失败', tagClass: 'meta-tag--not-downloaded' }
    case 'EmbyExists': return { label: 'Emby已存在', tagClass: 'meta-tag--collected' }
    case 'TmdbBlocked': return { label: 'TMDB屏蔽', tagClass: 'meta-tag--miss' }
    default: return { label: state || '未知', tagClass: 'meta-tag--feed' }
  }
}

function getRuleNameTagClass(ruleName: string): string {
  if (!ruleName) return 'meta-tag--feed'
  if (ruleName === 'Emby库中已存在') return 'meta-tag--collected'
  if (ruleName === 'TMDB屏蔽列表') return 'meta-tag--miss'
  if (ruleName === '手动记录') return 'meta-tag--source'
  return 'meta-tag--feed'
}

function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return dateStr }
}

function cleanDescription(desc: string | null | undefined): string | null {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  return clean || null
}

// --- 操作 ---
async function deleteItem(guid: string) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此下载记录吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.deleteDownloadHistory(guid)
    success('已删除')
    items.value = items.value.filter((i: any) => (i.guid || i.id) !== guid)
    total.value = Math.max(0, total.value - 1)
  } catch { showError('删除失败') }
}

async function handleClearAll() {
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

// 筛选逻辑（前端过滤 feed_id，因为后端 history/all 不支持 feed_ids 筛选）
const filteredItems = computed(() => {
  if (selectedFeedIds.value.length === 0) return items.value
  return items.value.filter((item: any) => item.feed_id && selectedFeedIds.value.includes(item.feed_id))
})
</script>

<template>
  <v-dialog :model-value="show" max-width="1200" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-history-download</v-icon>
        下载记录
        <v-chip size="small" variant="tonal" class="ml-3">{{ total }} 条</v-chip>
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
              placeholder="搜索标题或描述..."
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
            />
          </div>
          <div class="list-toolbar__actions">
            <v-btn variant="tonal" size="small" prepend-icon="mdi-refresh" @click="fetchItems(false)">刷新</v-btn>
            <v-spacer />
            <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-delete-sweep-outline" @click="handleClearAll">批量清除</v-btn>
          </div>
        </div>

        <v-skeleton-loader v-if="loading && items.length === 0" type="list-item@8" />

        <!-- 记录列表 -->
        <div v-else-if="filteredItems.length > 0" class="d-flex flex-column ga-2">
          <div v-for="(item, index) in filteredItems" :key="item.guid || item.id" class="feed-item-card">
            <!-- 第一行：标签 + 序号 -->
            <div class="d-flex align-center justify-space-between ga-2 flex-wrap">
              <div class="d-flex align-center ga-1 flex-wrap" style="min-width: 0; flex: 1;">
                <!-- 状态标签 -->
                <v-chip size="x-small" variant="flat" :class="['meta-tag', getStateInfo(item.state).tagClass]">
                  {{ getStateInfo(item.state).label }}
                </v-chip>
                <!-- 规则名标签 -->
                <v-chip v-if="item.rule_name" size="x-small" variant="flat" :class="['meta-tag', getRuleNameTagClass(item.rule_name)]">
                  {{ item.rule_name }}
                </v-chip>
                <!-- 站点名 -->
                <v-chip v-if="item.feed_id" size="x-small" variant="flat" class="meta-tag meta-tag--feed">
                  {{ feedNameMap[item.feed_id] || `Feed #${item.feed_id}` }}
                </v-chip>
                <!-- 下载器 -->
                <v-chip v-if="item.download_client_id" size="x-small" variant="flat" class="meta-tag meta-tag--source">
                  {{ item.download_client_id }}
                </v-chip>
                <!-- 失败次数 -->
                <v-chip v-if="item.fail_count && item.fail_count > 0" size="x-small" variant="flat" class="meta-tag meta-tag--not-downloaded">
                  失败 ×{{ item.fail_count }}
                </v-chip>
              </div>
              <span class="text-caption text-medium-emphasis flex-shrink-0" style="font-family: monospace;">#{{ index + 1 }}</span>
            </div>

            <!-- 标题 -->
            <div class="text-subtitle-2 font-weight-bold mt-2" style="word-break: break-all;">
              <a v-if="item.link" :href="item.link" target="_blank" style="color: inherit; text-decoration: none;">
                {{ item.title }}
              </a>
              <span v-else>{{ item.title }}</span>
            </div>

            <!-- 描述 -->
            <div v-if="cleanDescription(item.description)" class="text-caption text-medium-emphasis mt-1" style="word-break: break-all; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
              {{ cleanDescription(item.description) }}
            </div>

            <!-- 失败原因 -->
            <div v-if="item.fail_reason" class="text-caption text-error mt-1" style="line-height: 1.4;">
              <v-icon size="12" class="mr-1">mdi-alert-circle-outline</v-icon>
              {{ item.fail_reason }}
            </div>

            <!-- 元数据行 -->
            <div class="meta-tags mt-1">
              <!-- info_hash -->
              <v-chip v-if="item.info_hash" size="x-small" variant="flat" class="meta-tag meta-tag--size">
                <span style="font-family: monospace; max-width: 120px; overflow: hidden; text-overflow: ellipsis; display: inline-block;">{{ item.info_hash }}</span>
              </v-chip>
            </div>

            <!-- 底部：时间 + 操作 -->
            <div class="d-flex align-center justify-space-between flex-wrap ga-2 mt-2">
              <div class="d-flex flex-column ga-1">
                <span class="text-caption text-medium-emphasis" style="font-family: monospace;">{{ formatTime(item.created_at) }}</span>
                <span v-if="item.updated_at && formatTime(item.updated_at) !== formatTime(item.created_at)" class="text-caption text-medium-emphasis" style="font-family: monospace; opacity: 0.6;">
                  更新: {{ formatTime(item.updated_at) }}
                </span>
              </div>
              <div class="d-flex align-center ga-1 flex-shrink-0">
                <v-btn
                  v-if="item.link"
                  size="small" variant="tonal" color="info"
                  prepend-icon="mdi-open-in-new"
                  :href="item.link" target="_blank"
                >来源</v-btn>
                <v-btn
                  size="small" variant="tonal" color="error"
                  prepend-icon="mdi-delete-outline"
                  @click="deleteItem(item.guid || String(item.id))"
                >删除</v-btn>
              </div>
            </div>
          </div>

          <!-- 无限滚动哨兵 -->
          <div ref="sentinelRef" style="height: 1px" />
          <div v-if="loading" class="text-center pa-4"><v-progress-circular indeterminate size="24" /></div>
          <div v-if="!hasMore && items.length > 0" class="text-center text-caption text-medium-emphasis pa-2">已加载全部</div>
        </div>

        <div v-else class="text-center pa-8">
          <v-icon size="64" color="primary" class="mb-4">mdi-inbox-outline</v-icon>
          <div class="text-body-2 text-medium-emphasis">暂无下载记录</div>
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
