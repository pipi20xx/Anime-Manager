<script setup lang="ts">
import { ref, watch, computed, h } from 'vue'
import {
  NModal, NButton, NSpace, NTag, NSpin, NEmpty, NImage, NPopconfirm,
  useDialog, useMessage
} from 'naive-ui'
import {
  DeleteSweepOutlined as ClearIcon,
  LiveTvOutlined as TvIcon,
  MovieOutlined as MovieIcon,
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

// 已推送的集数（去重）
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

// 某集是否已推送
const isEpisodePushed = (season: number, episode: number) => {
  return episodes.value.some(e => e.season === season && e.episode === episode)
}

// 选中集的推送记录
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

const selectEpisode = (season: number, episode: number) => {
  selectedEpisode.value = { season, episode }
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
    action: () => {
      return h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
        h(NButton, { ...getButtonStyle('dialogDanger'), onClick: async () => {
          try {
            await fetch(`${props.apiBase}/api/subscriptions/${props.sub.id}/episodes`, {
              method: 'DELETE'
            })
            message.success('推送记录已清空')
            fetchEpisodes()
            dialog.destroyAll()
          } catch (e) {
            message.error('操作失败')
          }
        } }, { default: () => '确定清空' })
      ])
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
    preset="card"
    style="width: 1100px; max-width: 98vw;"
    content-style="padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    :title="`订阅详情: ${sub?.title || ''}`"
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
                <div class="stat-value">{{ pushedCount }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">目标集数</div>
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

        <!-- 主体内容区 -->
        <div class="main-section">
          <!-- 左侧集数列表 -->
          <div class="episodes-panel">
            <div class="panel-title">集数</div>
            <div class="episodes-grid" v-if="episodeRange.length > 0">
              <div
                v-for="ep in episodeRange"
                :key="`${ep.season}-${ep.episode}`"
                class="episode-card"
                :class="{
                  'is-selected': selectedEpisode?.season === ep.season && selectedEpisode?.episode === ep.episode,
                  'is-pushed': isEpisodePushed(ep.season, ep.episode)
                }"
                @click="selectEpisode(ep.season, ep.episode)"
              >
                <div class="episode-card-badge">E{{ String(ep.episode).padStart(2, '0') }}</div>
                <div class="episode-card-title">第 {{ ep.episode }} 集</div>
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
            <div v-else-if="isMovie" class="movie-only">
              <n-icon size="48" :component="MovieIcon" />
              <div>电影订阅</div>
            </div>
          </div>

          <!-- 右侧推送记录 -->
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
              <div v-else>
                <div v-if="episodes.length > 0">
                  <div
                    v-for="item in episodes"
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
        <n-popconfirm
          @positive-click="handleClearHistory"
          positive-text="确定清空"
          negative-text="取消"
          :disabled="episodes.length === 0"
        >
          <template #trigger>
            <n-button
              v-bind="getButtonStyle('danger')"
              size="small"
              :disabled="episodes.length === 0"
            >
              <template #icon><n-icon><ClearIcon /></n-icon></template>
              清空所有推送记录
            </n-button>
          </template>
          清空后，系统将不再认为这些集数已下载，下次刷新或补全时可能会重复下载。确定吗？
        </n-popconfirm>
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">
          关闭窗口
        </n-button>
      </n-space>
    </template>
  </n-modal>
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

/* 主体内容区 */
.main-section {
  display: flex;
  gap: 20px;
  min-height: 420px;
}

.episodes-panel {
  width: 260px;
  flex-shrink: 0;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.records-panel {
  flex: 1;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-width: 0;
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

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-header .panel-title {
  margin-bottom: 0;
}

.panel-count {
  font-size: 12px;
  color: var(--text-muted);
}

/* 集数网格 */
.episodes-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.episode-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  cursor: pointer;
  transition: all 0.2s ease;
}

.episode-card:hover {
  border-color: var(--n-primary-color);
  transform: translateX(2px);
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
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
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

.episode-card-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.movie-only {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: 14px;
}

/* 右侧记录列表 */
.records-list {
  padding-right: 4px;
}

.record-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--app-surface-card);
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
}

.record-content {
  flex: 1;
  min-width: 0;
}

.record-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
