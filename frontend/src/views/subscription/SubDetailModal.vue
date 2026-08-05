<script setup lang="ts">
/**
 * SubDetailModal — 订阅推送记录详情
 *
 * 对标旧前端 SubscriptionDetailModalDesktop：
 * - 顶部海报 + 信息区（标题、状态、元数据、统计卡片、进度条）
 * - 集数横向滑动条（可点击选中、已推送标记、拖拽滚动）
 * - 推送记录列表（按集筛选 / 全部展示）
 * - 清空推送记录
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { subscriptionApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getImg } from '@/composables/useDataCenter'

const props = defineProps<{
  show: boolean
  sub: any
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const episodes = ref<any[]>([])
const selectedEpisode = ref<{ season: number; episode: number } | null>(null)
const episodesScrollRef = ref<HTMLElement | null>(null)

const isMovie = computed(() => props.sub?.media_type === 'movie')

// 集数范围
const episodeRange = computed(() => {
  const sub = props.sub
  if (!sub || isMovie.value) return []
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12
  const list = []
  for (let i = start; i <= end; i++) {
    list.push({ season: sub.season || 1, episode: i })
  }
  return list
})

const totalEpisodes = computed(() => episodeRange.value.length || 1)

const episodeRangeLabel = computed(() => {
  const sub = props.sub
  if (!sub || isMovie.value) return '电影'
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12
  return `E${start}-${end}`
})

// 已推送去重集数
const pushedEpisodes = computed(() => {
  const sub = props.sub
  if (!sub) return []
  if (isMovie.value) {
    const seen = new Set<string>()
    return episodes.value.filter(e => {
      const key = `${e.season}-${e.episode}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }
  const season = sub.season || 1
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12
  const seen = new Set<string>()
  return episodes.value
    .filter(e => e.season === season && e.episode >= start && e.episode <= end)
    .filter(e => {
      const key = `${e.season}-${e.episode}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
})

const pushedCount = computed(() => pushedEpisodes.value.length)

const progressPercent = computed(() => {
  if (!totalEpisodes.value) return 0
  return Math.min(100, Math.round((pushedCount.value / totalEpisodes.value) * 100))
})

// 最新入库集
const latestEpisode = computed(() => {
  if (!episodes.value.length) return null
  let latest: any = null
  let latestTime = -Infinity
  for (const e of episodes.value) {
    const t = new Date(e.download_at).getTime()
    if (!isNaN(t) && t > latestTime) {
      latestTime = t
      latest = e
    }
  }
  return latest ? { season: latest.season, episode: latest.episode } : null
})

function isEpisodePushed(season: number, episode: number): boolean {
  return episodes.value.some(e => e.season === season && e.episode === episode)
}

// 选中集的推送记录
const selectedRecords = computed(() => {
  if (!selectedEpisode.value) return []
  return episodes.value
    .filter(e => e.season === selectedEpisode.value?.season && e.episode === selectedEpisode.value?.episode)
    .sort((a, b) => new Date(b.download_at).getTime() - new Date(a.download_at).getTime())
})

// 全部推送记录（按时间倒序）
const sortedEpisodes = computed(() => {
  return [...episodes.value].sort((a, b) =>
    new Date(b.download_at).getTime() - new Date(a.download_at).getTime()
  )
})

const posterUrl = computed(() => {
  if (!props.sub?.poster_path) return ''
  return getImg(props.sub.poster_path)
})

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    })
  } catch { return dateStr }
}

function formatEpisode(row: any): string {
  if (row.season === 0 && row.episode === 0) return '电影'
  return `S${row.season}E${row.episode}`
}

// --- 拖拽滚动 ---
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartScrollLeft = ref(0)
const dragMoved = ref(false)

function onScrollMouseDown(e: MouseEvent) {
  const container = episodesScrollRef.value
  if (!container || e.button !== 0) return
  isDragging.value = true
  dragMoved.value = false
  dragStartX.value = e.pageX
  dragStartScrollLeft.value = container.scrollLeft
  document.addEventListener('mousemove', onDocMouseMove)
  document.addEventListener('mouseup', onDocMouseUp)
}

function onDocMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const container = episodesScrollRef.value
  if (!container) return
  const delta = e.pageX - dragStartX.value
  if (Math.abs(delta) > 5) dragMoved.value = true
  container.scrollLeft = dragStartScrollLeft.value - delta
}

function onDocMouseUp() {
  if (!isDragging.value) return
  isDragging.value = false
  document.removeEventListener('mousemove', onDocMouseMove)
  document.removeEventListener('mouseup', onDocMouseUp)
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDocMouseMove)
  document.removeEventListener('mouseup', onDocMouseUp)
})

function selectEpisode(season: number, episode: number) {
  if (dragMoved.value) { dragMoved.value = false; return }
  selectedEpisode.value = { season, episode }
}

function scrollToEpisode(season: number, episode: number) {
  nextTick(() => {
    const container = episodesScrollRef.value
    if (!container) return
    const target = container.querySelector(`[data-ep-key="${season}-${episode}"]`) as HTMLElement | null
    if (!target) return
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const offset = targetRect.left - containerRect.left - (containerRect.width - targetRect.width) / 2
    container.scrollBy({ left: offset, behavior: 'smooth' })
  })
}

// --- 数据获取 ---
async function fetchEpisodes() {
  if (!props.sub?.id) return
  loading.value = true
  episodes.value = []
  selectedEpisode.value = null
  try {
    const data = await subscriptionApi.getSubscriptionEpisodes(props.sub.id)
    episodes.value = Array.isArray(data) ? data : []
    const latest = latestEpisode.value
    if (latest) {
      selectedEpisode.value = { season: latest.season, episode: latest.episode }
      scrollToEpisode(latest.season, latest.episode)
    } else if (episodeRange.value.length > 0) {
      const first = episodeRange.value[0]
      selectedEpisode.value = { season: first.season, episode: first.episode }
      scrollToEpisode(first.season, first.episode)
    }
  } catch { episodes.value = [] }
  finally { loading.value = false }
}

async function handleClearHistory() {
  if (!props.sub) return
  const ok = await confirm({
    title: '确认清空推送记录？',
    content: '清空后，系统将不再认为这些集数已下载，下次刷新或补全时可能会重复下载。确定吗？',
    confirmColor: 'error'
  })
  if (!ok) return
  try {
    await subscriptionApi.clearSubscriptionEpisodes(props.sub.id)
    success('推送记录已清空')
    fetchEpisodes()
  } catch { showError('操作失败') }
}

watch(() => props.show, (val) => {
  if (val) fetchEpisodes()
})
</script>

<template>
  <v-dialog :model-value="show" max-width="1100" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-format-list-checks</v-icon>
        订阅推送记录 — {{ sub?.title || '' }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="$emit('update:show', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-skeleton-loader v-if="loading" type="card@2" />

        <template v-else-if="sub">
          <!-- 顶部信息区 -->
          <div class="detail-header">
            <div class="detail-poster">
              <v-img v-if="posterUrl" :src="posterUrl" cover aspect-ratio="2/3" class="rounded-lg" />
              <div v-else class="detail-poster-placeholder d-flex align-center justify-center">
                <v-icon size="40" color="grey">{{ isMovie ? 'mdi-filmstrip' : 'mdi-television-classic' }}</v-icon>
              </div>
            </div>
            <div class="detail-info">
              <div class="d-flex align-center ga-3 mb-2">
                <span class="text-h6 font-weight-bold">{{ sub?.title || '未命名' }}</span>
                <v-chip size="small" :color="sub?.enabled ? 'success' : 'error'" variant="tonal">
                  {{ sub?.enabled ? '监控中' : '已暂停' }}
                </v-chip>
              </div>
              <div class="d-flex align-center ga-4 text-body-2 text-medium-emphasis mb-3">
                <span class="d-flex align-center ga-1">
                  <v-icon size="16">{{ isMovie ? 'mdi-filmstrip' : 'mdi-television-classic' }}</v-icon>
                  {{ isMovie ? '电影' : '剧集' }}
                </span>
                <span v-if="!isMovie">S{{ sub?.season ?? 1 }}</span>
                <span v-if="sub?.year">{{ sub.year }}</span>
                <span v-if="!isMovie && sub?.start_episode">
                  E{{ sub.start_episode }}{{ sub?.end_episode > 0 ? '-' + sub.end_episode : '+' }}
                </span>
              </div>

              <div class="d-flex ga-3 mb-3">
                <v-card class="glass-card pa-3 text-center flex-1" variant="flat">
                  <div class="text-caption text-medium-emphasis">已推送</div>
                  <div class="text-h6 font-weight-bold text-primary">{{ pushedCount }}/{{ totalEpisodes }}</div>
                </v-card>
                <v-card class="glass-card pa-3 text-center flex-1" variant="flat">
                  <div class="text-caption text-medium-emphasis">总集数</div>
                  <div class="text-h6 font-weight-bold text-primary" style="font-family: monospace; font-size: 18px;">{{ episodeRangeLabel }}</div>
                </v-card>
                <v-card class="glass-card pa-3 text-center flex-1" variant="flat">
                  <div class="text-caption text-medium-emphasis">完成度</div>
                  <div class="text-h6 font-weight-bold text-primary">{{ progressPercent }}%</div>
                </v-card>
              </div>

              <v-progress-linear
                v-if="!isMovie"
                :model-value="progressPercent"
                color="primary"
                height="6"
                rounded="pill"
                class="mt-1"
              />
            </div>
          </div>

          <!-- 集数横向滑动条 -->
          <v-card v-if="!isMovie && episodeRange.length > 0" class="glass-card pa-4 mb-4" variant="flat">
            <div class="d-flex justify-space-between align-center mb-2">
              <div class="text-subtitle-2 font-weight-medium d-flex align-center ga-2">
                <v-icon size="16">mdi-television-classic</v-icon>
                集数 {{ episodeRangeLabel }}
              </div>
              <div class="text-caption text-medium-emphasis">
                共 {{ totalEpisodes }} 集 · 已推送 {{ pushedCount }} 集
                <span class="ml-2 pl-2" style="border-left: 1px solid rgba(var(--v-theme-on-surface),0.12);">可横向滑动</span>
              </div>
            </div>

            <div
              class="detail-episodes-scroll"
              :class="{ 'is-dragging': isDragging }"
              ref="episodesScrollRef"
              @mousedown="onScrollMouseDown"
            >
              <div class="detail-episodes-track">
                <div
                  v-for="ep in episodeRange"
                  :key="`${ep.season}-${ep.episode}`"
                  :data-ep-key="`${ep.season}-${ep.episode}`"
                  class="detail-episode-card"
                  :class="{
                    'is-selected': selectedEpisode?.season === ep.season && selectedEpisode?.episode === ep.episode,
                    'is-pushed': isEpisodePushed(ep.season, ep.episode)
                  }"
                  @click="selectEpisode(ep.season, ep.episode)"
                >
                  <div class="detail-episode-badge">E{{ ep.episode }}</div>
                  <div class="detail-episode-status">
                    {{ isEpisodePushed(ep.season, ep.episode) ? '已推送' : '待推送' }}
                  </div>
                </div>
              </div>
            </div>
          </v-card>

          <!-- 推送记录 -->
          <v-card class="glass-card pa-4" variant="flat">
            <div class="d-flex justify-space-between align-center mb-2">
              <div class="text-subtitle-2 font-weight-medium d-flex align-center ga-2">
                <v-icon size="16">mdi-history</v-icon>
                推送记录
                <span v-if="selectedEpisode" class="text-caption text-medium-emphasis font-weight-normal">
                  · {{ formatEpisode(selectedEpisode) }}
                </span>
              </div>
              <div class="text-caption text-medium-emphasis">
                共 {{ selectedEpisode ? selectedRecords.length : episodes.length }} 条
              </div>
            </div>

            <div class="detail-records-list">
              <template v-if="selectedEpisode">
                <div v-if="selectedRecords.length > 0">
                  <v-card v-for="item in selectedRecords" :key="item.id || item.download_at" class="glass-card hover-lift pa-3 mb-2 d-flex align-start ga-3" variant="flat">
                    <div class="flex-1 min-width-0">
                      <div class="text-body-2 font-weight-medium">{{ item.title || '（未命名资源）' }}</div>
                      <div class="text-caption text-medium-emphasis" style="font-family: monospace;">{{ formatDateTime(item.download_at) }}</div>
                    </div>
                    <v-chip v-if="item.quality_score && item.quality_score > 0" size="x-small" variant="tonal" color="brown">
                      分数 {{ item.quality_score }}
                    </v-chip>
                  </v-card>
                </div>
                <div v-else class="text-center pa-6 text-medium-emphasis text-body-2">该集暂无推送记录</div>
              </template>
              <template v-else>
                <div v-if="sortedEpisodes.length > 0">
                  <v-card v-for="item in sortedEpisodes" :key="`${item.season}-${item.episode}-${item.id || item.download_at}`" class="glass-card hover-lift pa-3 mb-2 d-flex align-start ga-3" variant="flat">
                    <v-chip size="x-small" variant="flat" color="primary" class="flex-shrink-0" style="font-family: monospace;">
                      {{ formatEpisode(item) }}
                    </v-chip>
                    <div class="flex-1 min-width-0">
                      <div class="text-body-2 font-weight-medium">{{ item.title || '（未命名资源）' }}</div>
                      <div class="text-caption text-medium-emphasis" style="font-family: monospace;">{{ formatDateTime(item.download_at) }}</div>
                    </div>
                    <v-chip v-if="item.quality_score && item.quality_score > 0" size="x-small" variant="tonal" color="brown">
                      分数 {{ item.quality_score }}
                    </v-chip>
                  </v-card>
                </div>
                <div v-else class="text-center pa-6 text-medium-emphasis text-body-2">暂无推送记录</div>
              </template>
            </div>
          </v-card>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-sweep-outline" :disabled="episodes.length === 0" @click="handleClearHistory">清空所有推送记录</v-btn>
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭窗口</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 顶部信息区 — 布局 */
.detail-header {
  display: flex;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  margin-bottom: 20px;
}
.detail-poster {
  width: 120px;
  height: 180px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.detail-poster-placeholder {
  width: 100%;
  height: 100%;
}
.detail-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* 集数横向滑动 — 交互逻辑 */
.detail-episodes-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  padding: 4px 2px 8px;
  cursor: grab;
  user-select: none;
}
.detail-episodes-scroll.is-dragging {
  cursor: grabbing;
  scroll-behavior: auto;
}
.detail-episodes-track {
  display: flex;
  gap: 8px;
  padding: 2px;
  width: max-content;
  min-width: 100%;
}
.detail-episode-card {
  flex-shrink: 0;
  width: 88px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 8px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, transform 0.2s;
}
.detail-episode-card:hover {
  border-color: rgb(var(--v-theme-primary));
  transform: translateY(-2px);
}
.detail-episode-card.is-selected {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
  box-shadow: 0 0 0 1px rgb(var(--v-theme-primary));
}
.detail-episode-card.is-pushed:not(.is-selected) {
  border-color: rgba(76, 175, 80, 0.3);
}
.detail-episode-badge {
  min-width: 56px;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(var(--v-theme-primary), 0.15);
  color: rgb(var(--v-theme-primary));
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
}
.detail-episode-card.is-selected .detail-episode-badge {
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
.detail-episode-status {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.4);
}
.detail-episode-card.is-pushed .detail-episode-status {
  color: #4caf50;
}
.detail-episode-card.is-selected .detail-episode-status {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

/* 推送记录列表 — 滚动容器 */
.detail-records-list {
  max-height: 400px;
  overflow-y: auto;
}
</style>
