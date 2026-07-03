<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  NModal, NButton, NTag, NSpin, NEmpty, NImage,
  useDialog, useMessage
} from 'naive-ui'
import {
  CloseOutlined as CloseIcon,
  DeleteSweepOutlined as ClearIcon,
  LiveTvOutlined as TvIcon,
  MovieOutlined as MovieIcon,
  ArrowBackOutlined as BackIcon,
  HistoryOutlined as HistoryIcon
} from '@vicons/material'
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
const dialog = useDialog()
const message = useMessage()

const isMovie = computed(() => props.sub?.media_type === 'movie')

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

const pushedEpisodes = computed(() => {
  return episodes.value.filter((item, idx, arr) =>
    arr.findIndex(e => e.season === item.season && e.episode === item.episode) === idx
  )
})

const pushedCount = computed(() => pushedEpisodes.value.length)

const progressPercent = computed(() => {
  if (!totalEpisodes.value) return 0
  return Math.min(100, Math.round((pushedCount.value / totalEpisodes.value) * 100))
})

const isEpisodePushed = (season: number, episode: number) => {
  return episodes.value.some(e => e.season === season && e.episode === episode)
}

const selectedRecords = computed(() => {
  if (!selectedEpisode.value) return []
  return episodes.value.filter(e =>
    e.season === selectedEpisode.value?.season &&
    e.episode === selectedEpisode.value?.episode
  ).sort((a, b) => new Date(b.download_at).getTime() - new Date(a.download_at).getTime())
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

const selectEpisode = (season: number, episode: number) => {
  selectedEpisode.value = { season, episode }
}

const backToEpisodes = () => {
  selectedEpisode.value = null
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
  <n-modal
    :show="show"
    @update:show="val => emit('update:show', val)"
    :mask-closable="true"
    transform-origin="center"
  >
    <div class="mobile-detail-modal">
      <!-- 顶部导航栏 -->
      <div class="mobile-header">
        <div class="header-left">
          <n-button
            v-if="selectedEpisode"
            v-bind="getButtonStyle('icon')"
            size="small"
            @click="backToEpisodes"
          >
            <template #icon><n-icon><BackIcon /></n-icon></template>
          </n-button>
          <div class="header-title">
            <span>{{ selectedEpisode ? formatEpisode(selectedEpisode) + ' 推送记录' : '订阅详情' }}</span>
          </div>
        </div>
        <n-button
          v-bind="getButtonStyle('icon')"
          size="small"
          @click="emit('update:show', false)"
        >
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
      </div>

      <template v-if="!selectedEpisode">
        <!-- 顶部信息区 -->
        <div class="header-section">
          <div class="poster-box">
            <n-image
              v-if="posterUrl"
              :src="posterUrl"
              fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
              object-fit="cover"
              preview-disabled
              style="width: 100%; height: 100%; border-radius: var(--m-radius-md);"
            />
            <div v-else class="poster-placeholder">
              <n-icon size="32" :component="isMovie ? MovieIcon : TvIcon" />
            </div>
          </div>
          <div class="info-box">
            <div class="title-row">
              <span class="sub-title">{{ sub?.title || '未命名' }}</span>
              <n-tag
                size="tiny"
                round
                :bordered="false"
                :style="sub?.enabled
                  ? { color: '#fff', backgroundColor: '#2e7d32' }
                  : { color: '#fff', backgroundColor: '#c62828' }"
              >
                {{ sub?.enabled ? '监控' : '暂停' }}
              </n-tag>
            </div>
            <div class="meta-row">
              <span class="meta-item">
                <n-icon size="12" :component="isMovie ? MovieIcon : TvIcon" />
                {{ isMovie ? '电影' : '剧集' }}
              </span>
              <span v-if="!isMovie" class="meta-item">S{{ sub?.season ?? 1 }}</span>
              <span v-if="sub?.year" class="meta-item">{{ sub.year }}</span>
            </div>

            <div class="stats-row">
              <div class="stat-card">
                <div class="stat-label">已推送</div>
                <div class="stat-value">{{ pushedCount }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">目标</div>
                <div class="stat-value">{{ totalEpisodes }}</div>
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

        <!-- 集数网格 -->
        <div class="episodes-section">
          <div class="section-header">
            <span class="section-title">集数</span>
            <span class="section-count">{{ pushedCount }}/{{ totalEpisodes }} 已推送</span>
          </div>

          <n-spin :show="loading">
            <div class="episodes-grid" v-if="episodeRange.length > 0">
              <div
                v-for="ep in episodeRange"
                :key="`${ep.season}-${ep.episode}`"
                class="episode-card"
                :class="{ 'is-pushed': isEpisodePushed(ep.season, ep.episode) }"
                @click="selectEpisode(ep.season, ep.episode)"
              >
                <div class="episode-card-badge">E{{ String(ep.episode).padStart(2, '0') }}</div>
                <div class="episode-card-status">
                  <n-tag
                    size="tiny"
                    round
                    :bordered="false"
                    :style="isEpisodePushed(ep.season, ep.episode)
                      ? { color: '#fff', backgroundColor: '#2e7d32' }
                      : { color: 'var(--text-muted)', backgroundColor: 'var(--app-surface-inner)' }"
                  >
                    {{ isEpisodePushed(ep.season, ep.episode) ? '已推送' : '待推送' }}
                  </n-tag>
                </div>
              </div>
            </div>
            <div v-else-if="isMovie" class="movie-only">
              <n-icon size="48" :component="MovieIcon" />
              <div>电影订阅</div>
            </div>
          </n-spin>
        </div>
      </template>

      <!-- 选中集的推送记录 -->
      <div v-else class="records-section">
        <div class="section-header">
          <span class="section-title">
            <n-icon size="16"><HistoryIcon /></n-icon>
            推送记录
          </span>
          <span class="section-count">共 {{ selectedRecords.length }} 条</span>
        </div>

        <div class="records-list" v-if="selectedRecords.length > 0">
          <div
            v-for="item in selectedRecords"
            :key="item.id || item.download_at"
            class="record-item"
          >
            <div class="record-title">{{ item.title || '（未命名资源）' }}</div>
            <div class="record-time">{{ formatDateTime(item.download_at) }}</div>
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

      <!-- 底部操作 -->
      <div class="footer-bar">
        <n-button
          v-bind="getButtonStyle('danger')"
          size="small"
          block
          :disabled="episodes.length === 0"
          @click="handleClearHistory"
        >
          <template #icon><n-icon><ClearIcon /></n-icon></template>
          清空所有推送记录
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.mobile-detail-modal {
  width: 100vw;
  height: 100vh;
  background: var(--app-surface-card);
  display: flex;
  flex-direction: column;
}

.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-spacing-md);
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface-inner);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-lg);
  font-weight: bold;
  color: var(--text-primary);
}

/* 顶部信息区 */
.header-section {
  display: flex;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-bottom: 1px solid var(--app-border-light);
}

.poster-box {
  width: 80px;
  height: 120px;
  flex-shrink: 0;
  border-radius: var(--m-radius-md);
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
  gap: var(--m-spacing-sm);
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.sub-title {
  font-size: var(--m-text-md);
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  color: var(--text-secondary);
  font-size: var(--m-text-xs);
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 2px;
}

.stats-row {
  display: flex;
  gap: var(--m-spacing-sm);
  margin-top: var(--m-spacing-xs);
}

.stat-card {
  flex: 1;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-md);
  padding: var(--m-spacing-sm);
  text-align: center;
}

.stat-label {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-bottom: 2px;
}

.stat-value {
  font-size: var(--m-text-md);
  font-weight: 700;
  color: var(--n-primary-color);
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--app-surface-inner);
  border-radius: 2px;
  overflow: hidden;
  margin-top: var(--m-spacing-xs);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--n-primary-color), #9c64d9);
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* 集数区域 */
.episodes-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--m-spacing-md);
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-spacing-sm);
}

.section-title {
  font-size: var(--m-text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.section-count {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
}

.episodes-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--m-spacing-sm);
  padding-right: 4px;
}

.episode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--m-spacing-sm);
  border-radius: var(--m-radius-md);
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  cursor: pointer;
  transition: all 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.episode-card:active {
  border-color: var(--n-primary-color);
  background: rgba(187, 134, 252, 0.08);
}

.episode-card.is-pushed {
  border-color: rgba(46, 125, 50, 0.3);
}

.episode-card-badge {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--m-radius-md);
  background: rgba(187, 134, 252, 0.15);
  color: var(--n-primary-color);
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
}

.movie-only {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: var(--m-text-sm);
}

/* 推送记录区域 */
.records-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--m-spacing-md);
  overflow: hidden;
}

.records-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.record-item {
  padding: var(--m-spacing-sm);
  border-radius: var(--m-radius-md);
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.record-title {
  font-size: var(--m-text-sm);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-all;
}

.record-time {
  font-size: 10px;
  color: var(--text-muted);
  font-family: monospace;
}

.empty-state {
  padding: 60px 0;
  text-align: center;
}

.empty-state :deep(.n-empty__icon) {
  font-size: 48px;
}

.empty-state :deep(.n-empty__description) {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}

/* 底部操作栏 */
.footer-bar {
  padding: var(--m-spacing-md);
  border-top: 1px solid var(--app-border-light);
  background: var(--app-surface-inner);
}
</style>
