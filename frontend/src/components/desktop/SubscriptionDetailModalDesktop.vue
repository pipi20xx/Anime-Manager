<script setup lang="ts">
import { ref, watch, computed, nextTick, onBeforeUnmount } from 'vue'
import AppGlassModal from '../AppGlassModal.vue'
import {
  NButton, NSpace, NTag, NSpin, NEmpty, NImage,
  useDialog, useMessage
} from 'naive-ui'
import {
  TrashIcon as ClearIcon,
  TvIcon,
  FilmIcon as MovieIcon,
  ClockIcon as HistoryIcon
} from '@heroicons/vue/24/outline'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  sub: any
  apiBase: string
}>()

const emit = defineEmits(['update:show'])

const loading = ref(false)
const episodes = ref<any[]>([])
const selectedEpisode = ref<{ season: number, episode: number } | null>(null)
const episodesScrollRef = ref<HTMLElement | null>(null)
const dialog = useDialog()
const message = useMessage()

const isMovie = computed(() => props.sub?.media_type === 'movie')

// 计算目标集数范围
const episodeRange = computed(() => {
  const sub = props.sub
  if (!sub || isMovie.value) return []
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12 // 兜底显示12集
  const list = []
  for (let i = start; i <= end; i++) {
    list.push({ season: sub.season || 1, episode: i })
  }
  return list
})

const totalEpisodes = computed(() => episodeRange.value.length || 1)

// 目标集数范围标签 (如 E1156-1181)
const episodeRangeLabel = computed(() => {
  const sub = props.sub
  if (!sub || isMovie.value) return '电影'
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12
  return `E${start}-${end}`
})

// 已推送的集数（仅统计目标范围内的去重集数，洗版重推不增加计数）
const pushedEpisodes = computed(() => {
  const sub = props.sub
  if (!sub) return []
  // 电影：直接去重返回
  if (isMovie.value) {
    const seen = new Set()
    return episodes.value.filter(e => {
      const key = `${e.season}-${e.episode}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }
  // 剧集：只统计目标集数范围内、同季的去重集数
  const season = sub.season || 1
  const start = sub.start_episode || 1
  const end = sub.end_episode && sub.end_episode > 0 ? sub.end_episode : 12
  const seen = new Set()
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

// 某集是否已推送
const isEpisodePushed = (season: number, episode: number) => {
  return episodes.value.some(e => e.season === season && e.episode === episode)
}

// 最新入库的集数（已推送记录中 download_at 最新的那一集）
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
  if (!latest) return null
  return { season: latest.season, episode: latest.episode }
})

// 选中集的推送记录
const selectedRecords = computed(() => {
  if (!selectedEpisode.value) return []
  return episodes.value.filter(e =>
    e.season === selectedEpisode.value?.season &&
    e.episode === selectedEpisode.value?.episode
  ).sort((a, b) => new Date(b.download_at).getTime() - new Date(a.download_at).getTime())
})

// 全部推送记录（按推送时间倒序）
const sortedEpisodes = computed(() => {
  return [...episodes.value].sort((a, b) =>
    new Date(b.download_at).getTime() - new Date(a.download_at).getTime()
  )
})

const posterUrl = computed(() => {
  if (!props.sub?.poster_path) return ''
  const path = props.sub.poster_path
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `${props.apiBase}/api/system/img?path=/${parts[parts.length - 1]}`
  }
  if (!path.startsWith('http')) {
    return `${props.apiBase}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  }
  return path
})

const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const formatEpisode = (row: any): string => {
  if (row.season === 0 && row.episode === 0) return '电影'
  return `S${row.season}E${row.episode}`
}

// 鼠标左键按住拖动横向滑动（桌面端模拟移动端手势）
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartScrollLeft = ref(0)
const dragMoved = ref(false)

const onScrollMouseDown = (e: MouseEvent) => {
  const container = episodesScrollRef.value
  if (!container || e.button !== 0) return // 仅响应左键
  isDragging.value = true
  dragMoved.value = false
  dragStartX.value = e.pageX
  dragStartScrollLeft.value = container.scrollLeft
  document.addEventListener('mousemove', onDocMouseMove)
  document.addEventListener('mouseup', onDocMouseUp)
}

const onDocMouseMove = (e: MouseEvent) => {
  if (!isDragging.value) return
  const container = episodesScrollRef.value
  if (!container) return
  const delta = e.pageX - dragStartX.value
  if (Math.abs(delta) > 5) dragMoved.value = true // 移动超过阈值视为拖拽
  container.scrollLeft = dragStartScrollLeft.value - delta
}

const onDocMouseUp = () => {
  if (!isDragging.value) return
  isDragging.value = false
  document.removeEventListener('mousemove', onDocMouseMove)
  document.removeEventListener('mouseup', onDocMouseUp)
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDocMouseMove)
  document.removeEventListener('mouseup', onDocMouseUp)
})

const selectEpisode = (season: number, episode: number) => {
  // 拖拽产生的点击不触发选中
  if (dragMoved.value) {
    dragMoved.value = false
    return
  }
  selectedEpisode.value = { season, episode }
}

// 滚动到指定集数（居中显示在可视区域）
const scrollToEpisode = (season: number, episode: number) => {
  nextTick(() => {
    const container = episodesScrollRef.value
    if (!container) return
    const target = container.querySelector(
      `[data-ep-key="${season}-${episode}"]`
    ) as HTMLElement | null
    if (!target) return
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const offset = targetRect.left - containerRect.left -
      (containerRect.width - targetRect.width) / 2
    container.scrollBy({ left: offset, behavior: 'smooth' })
  })
}

const fetchEpisodes = async () => {
  if (!props.sub?.id) return
  loading.value = true
  episodes.value = []
  selectedEpisode.value = null
  try {
    const res = await fetch(`${props.apiBase}/api/subscriptions/${props.sub.id}/episodes`)
    const data = await res.json()
    episodes.value = Array.isArray(data) ? data : []
    // 默认定位到最新入库的集数
    const latest = latestEpisode.value
    if (latest) {
      selectedEpisode.value = { season: latest.season, episode: latest.episode }
      scrollToEpisode(latest.season, latest.episode)
    } else if (episodeRange.value.length > 0) {
      // 暂无推送记录时，默认选中第一集并定位
      const first = episodeRange.value[0]
      selectedEpisode.value = { season: first.season, episode: first.episode }
      scrollToEpisode(first.season, first.episode)
    }
  } catch (e) {
    console.error('获取推送记录失败', e)
  } finally {
    loading.value = false
  }
}

const handleClearHistory = () => {
  dialog.warning({
    title: '确认清空推送记录？',
    content: '清空后，系统将不再认为这些集数已下载，下次刷新或补全时可能会重复下载。确定吗？',
    positiveText: '确定清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await fetch(`${props.apiBase}/api/subscriptions/${props.sub.id}/episodes`, {
          method: 'DELETE'
        })
        message.success('推送记录已清空')
        fetchEpisodes()
      } catch (e) {
        message.error('操作失败')
      }
    }
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) fetchEpisodes()
})
</script>

<template>
  <AppGlassModal
    appearance-key="subscription-detail-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 1100px;"
    content-style="padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    :title="`订阅推送记录详情: ${sub?.title || ''}`"
  >
    <div class="detail-container">
      <n-spin :show="loading">
        <!-- 顶部信息区 -->
        <div class="header-section">
          <div class="poster-box">
            <n-image
              v-if="posterUrl"
              :src="posterUrl"
              fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
              object-fit="cover"
              preview-disabled
              style="width: 100%; height: 100%; border-radius: 8px;"
            />
            <div v-else class="poster-placeholder">
              <n-icon size="40" :component="isMovie ? MovieIcon : TvIcon" />
            </div>
          </div>
          <div class="info-box">
            <div class="title-row">
              <span class="sub-title">{{ sub?.title || '未命名' }}</span>
              <n-tag
                size="small"
                round
                :bordered="false"
                :style="sub?.enabled
                  ? { color: '#fff', backgroundColor: '#2e7d32' }
                  : { color: '#fff', backgroundColor: '#c62828' }"
              >
                {{ sub?.enabled ? '监控中' : '已暂停' }}
              </n-tag>
            </div>
            <div class="meta-row">
              <span class="meta-item">
                <n-icon size="14" :component="isMovie ? MovieIcon : TvIcon" />
                {{ isMovie ? '电影' : '剧集' }}
              </span>
              <span v-if="!isMovie" class="meta-item">S{{ sub?.season ?? 1 }}</span>
              <span v-if="sub?.year" class="meta-item">{{ sub.year }}</span>
              <span v-if="!isMovie && sub?.start_episode" class="meta-item">
                E{{ sub.start_episode }}{{ sub?.end_episode > 0 ? '-' + sub.end_episode : '+' }}
              </span>
            </div>

            <div class="stats-row">
              <div class="stat-card">
                <div class="stat-label">已推送</div>
                <div class="stat-value">{{ pushedCount }}/{{ totalEpisodes }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">总集数</div>
                <div class="stat-value stat-value-range">{{ episodeRangeLabel }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">完成度</div>
                <div class="stat-value">{{ progressPercent }}%</div>
              </div>
            </div>

            <div class="progress-bar" v-if="!isMovie">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- 主体内容区 - 上下布局 -->
        <div class="main-section">
          <!-- 顶部集数横向滑动条 -->
          <div
            class="episodes-panel"
            v-if="!isMovie && episodeRange.length > 0"
          >
            <div class="panel-header">
              <div class="panel-title">
                <n-icon size="16"><TvIcon /></n-icon>
                <span>集数 {{ episodeRangeLabel }}</span>
              </div>
              <div class="panel-count">
                共 {{ totalEpisodes }} 集 · 已推送 {{ pushedCount }} 集
                <span class="panel-hint">可横向滑动浏览，默认定位至最新入库</span>
              </div>
            </div>

            <div
              class="episodes-scroll"
              :class="{ 'is-dragging': isDragging }"
              ref="episodesScrollRef"
              @mousedown="onScrollMouseDown"
            >
              <div class="episodes-track">
                <div
                  v-for="ep in episodeRange"
                  :key="`${ep.season}-${ep.episode}`"
                  :data-ep-key="`${ep.season}-${ep.episode}`"
                  class="episode-card"
                  :class="{
                    'is-selected': selectedEpisode?.season === ep.season && selectedEpisode?.episode === ep.episode,
                    'is-pushed': isEpisodePushed(ep.season, ep.episode)
                  }"
                  @click="selectEpisode(ep.season, ep.episode)"
                >
                  <div class="episode-card-badge">E{{ ep.episode }}</div>
                  <div class="episode-card-status">
                    {{ isEpisodePushed(ep.season, ep.episode) ? '已推送' : '待推送' }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 下方推送记录 -->
          <div class="records-panel">
            <div class="panel-header">
              <div class="panel-title">
                <n-icon size="16"><HistoryIcon /></n-icon>
                <span>
                  推送记录
                  <span v-if="selectedEpisode" class="panel-subtitle">
                    · {{ formatEpisode(selectedEpisode) }}
                  </span>
                </span>
              </div>
              <div class="panel-count" v-if="selectedEpisode">
                共 {{ selectedRecords.length }} 条
              </div>
              <div class="panel-count" v-else>
                共 {{ episodes.length }} 条
              </div>
            </div>

            <div class="records-list">
              <div v-if="selectedEpisode">
                <div v-if="selectedRecords.length > 0">
                  <div
                    v-for="item in selectedRecords"
                    :key="item.id || item.download_at"
                    class="record-item"
                  >
                    <div class="record-content">
                      <div class="record-title">{{ item.title || '（未命名资源）' }}</div>
                      <div class="record-time">{{ formatDateTime(item.download_at) }}</div>
                    </div>
                    <n-tag
                      v-if="item.quality_score && item.quality_score > 0"
                      size="tiny"
                      round
                      :bordered="false"
                      :style="{ color: '#fff', backgroundColor: '#6d4c41' }"
                    >
                      分数 {{ item.quality_score }}
                    </n-tag>
                  </div>
                </div>
                <div v-else class="empty-state">
                  <n-empty description="该集暂无推送记录" />
                </div>
              </div>
              <div v-else>
                <div v-if="sortedEpisodes.length > 0">
                  <div
                    v-for="item in sortedEpisodes"
                    :key="`${item.season}-${item.episode}-${item.id || item.download_at}`"
                    class="record-item"
                  >
                    <div class="record-badge">{{ formatEpisode(item) }}</div>
                    <div class="record-content">
                      <div class="record-title">{{ item.title || '（未命名资源）' }}</div>
                      <div class="record-time">{{ formatDateTime(item.download_at) }}</div>
                    </div>
                    <n-tag
                      v-if="item.quality_score && item.quality_score > 0"
                      size="tiny"
                      round
                      :bordered="false"
                      :style="{ color: '#fff', backgroundColor: '#6d4c41' }"
                    >
                      分数 {{ item.quality_score }}
                    </n-tag>
                  </div>
                </div>
                <div v-else class="empty-state">
                  <n-empty description="暂无推送记录" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </n-spin>
    </div>

    <template #footer>
      <n-space justify="space-between" align="center">
        <n-button
          v-bind="getButtonStyle('danger')"
          size="small"
          :disabled="episodes.length === 0"
          @click="handleClearHistory"
        >
          <template #icon><n-icon><ClearIcon /></n-icon></template>
          清空所有推送记录
        </n-button>
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">
          关闭窗口
        </n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.detail-container {
  padding: 16px 20px;
  min-height: 300px;
}

/* 顶部信息区 */
.header-section {
  display: flex;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--app-border-light);
  margin-bottom: 20px;
}

.poster-box {
  width: 120px;
  height: 180px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.info-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sub-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--text-secondary);
  font-size: 13px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stats-row {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.stat-card {
  flex: 1;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  padding: 12px 16px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--n-primary-color);
}

.stat-value-range {
  font-size: 18px;
  font-family: monospace;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: var(--app-surface-inner);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 4px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--n-primary-color), #9c64d9);
  border-radius: 3px;
  transition: width 0.4s ease;
}

/* 主体内容区 - 上下布局 */
.main-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 420px;
}

/* 集数横向滑动面板 */
.episodes-panel {
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.panel-header .panel-title {
  margin-bottom: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: normal;
}

.panel-count {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  padding-left: 8px;
  border-left: 1px solid var(--app-border-light);
}

/* 集数横向滚动容器 */
.episodes-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  padding: 4px 2px 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--app-border-light) transparent;
  cursor: grab;
  user-select: none;
}

/* 拖拽中：禁用过渡与 hover 偏移，避免卡片跳动 */
.episodes-scroll.is-dragging {
  cursor: grabbing;
  scroll-behavior: auto;
}

.episodes-scroll.is-dragging .episode-card:hover {
  transform: none;
  border-color: var(--app-border-light);
}

.episodes-scroll::-webkit-scrollbar {
  height: 8px;
}

.episodes-scroll::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.episodes-scroll::-webkit-scrollbar-thumb {
  background: var(--app-border-light);
  border-radius: 4px;
}

.episodes-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--n-primary-color);
}

.episodes-track {
  display: flex;
  gap: 8px;
  padding: 2px;
  width: max-content;
  min-width: 100%;
}

/* 集数卡片 - 紧凑横向布局 */
.episode-card {
  flex-shrink: 0;
  width: 88px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 8px;
  border-radius: 10px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
  user-select: none;
}

.episode-card:hover {
  border-color: var(--n-primary-color);
  transform: translateY(-2px);
}

.episode-card.is-selected {
  border-color: var(--n-primary-color);
  background: rgba(187, 134, 252, 0.08);
  box-shadow: 0 0 0 1px var(--n-primary-color);
}

.episode-card.is-pushed:not(.is-selected) {
  border-color: rgba(46, 125, 50, 0.3);
}

.episode-card-badge {
  min-width: 56px;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(187, 134, 252, 0.15);
  color: var(--n-primary-color);
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
}

.episode-card.is-selected .episode-card-badge {
  background: var(--n-primary-color);
  color: #fff;
}

.episode-card-status {
  font-size: 11px;
  color: var(--text-muted);
}

.episode-card.is-pushed .episode-card-status {
  color: #2e7d32;
}

.episode-card.is-selected .episode-card-status {
  color: var(--n-primary-color);
  font-weight: 600;
}

/* 推送记录面板 */
.records-panel {
  flex: 1;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 340px;
}

.records-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.record-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  margin-bottom: 8px;
}

.record-badge {
  flex-shrink: 0;
  min-width: 60px;
  text-align: center;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--n-primary-color);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  font-family: monospace;
  margin-top: 1px;
}

.record-content {
  flex: 1;
  min-width: 0;
}

.record-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.record-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
  font-family: monospace;
}

.empty-state {
  padding: 60px 0;
  text-align: center;
}
</style>
