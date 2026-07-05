<script setup lang="ts">
import { ref, watch, computed, nextTick, onBeforeUnmount } from 'vue'
import AppGlassModal from '../AppGlassModal.vue'
import {
  NTag, NButton, NSpace, NSpin, NEmpty, NDropdown, NPopconfirm
} from 'naive-ui'
import { useAggregatedFeedItems } from '../../composables/modals/useAggregatedFeedItems'
import { getButtonStyle } from '../../composables/useButtonStyles'
import AppSearchField from '../AppSearchField.vue'
import AppSelectField from '../AppSelectField.vue'

const props = defineProps<{
  show: boolean
  feeds: any[]
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  total,
  offset,
  hasMore,
  clientOptions,
  selectedFeedIds,
  keyword,
  fetchItems,
  applyFilter,
  handleDownload,
  handleToggleHistory,
  handleRetryRecognition,
  handleClearHistory
} = useAggregatedFeedItems(props)

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

// 站点选项：使用用户备注名作为标签
const feedOptions = computed(() => {
  return (props.feeds || []).map(f => ({ label: f.title || f.url, value: f.id }))
})

// 下载器下拉选项
const clientDropdownOptions = computed(() => {
  return clientOptions.value.map(c => ({ label: c.label, key: c.value }))
})

// 清除下载记录的确认文案：根据是否筛选站点动态变化
const clearHistoryTip = computed(() => {
  return selectedFeedIds.value.length > 0
    ? `确认清除当前筛选的 ${selectedFeedIds.value.length} 个站点的下载记录吗？`
    : '未筛选站点，将清除全部下载记录，确认吗？'
})

const cleanDescription = (desc: string | null | undefined): string | null => {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  return clean || null
}

const formatPubDate = (dateStr: string | null | undefined): string => {
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

// IntersectionObserver：底部哨兵进入视口时自动加载下一页
const setupObserver = () => {
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

const cleanupObserver = () => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems(false).then(() => setupObserver())
  } else {
    cleanupObserver()
  }
})

// 列表变化后重新挂载 observer（确保新哨兵被监听）
watch(() => items.value.length, () => {
  if (props.show && hasMore.value) {
    setupObserver()
  }
})

onBeforeUnmount(cleanupObserver)
</script>

<template>
  <AppGlassModal
    appearance-key="aggregated-feed-items-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 1400px;"
    title="订阅源详情"
  >
    <!-- 顶部工具栏：搜索 + 筛选 + 操作按钮 -->
    <div class="toolbar">
      <div class="filter-bar">
        <AppSearchField
          :value="keyword"
          placeholder="搜索资源标题或识别名..."
          :loading="loading"
          class="filter-item"
          @update:value="val => keyword = val"
          @search="applyFilter"
        />
        <AppSelectField
          :value="selectedFeedIds"
          label="筛选站点"
          placeholder="筛选站点（可多选）"
          :options="feedOptions"
          multiple
          filterable
          clearable
          :max-tag-count="'responsive'"
          class="filter-item"
          @update:value="val => { selectedFeedIds = val; applyFilter() }"
        />
      </div>
      <div class="action-bar">
        <span class="total-text">共 {{ total }} 条</span>
        <n-popconfirm @positive-click="handleClearHistory" positive-text="确认清除" negative-text="取消">
          <template #trigger>
            <n-button v-bind="getButtonStyle('text')" size="small" style="color: var(--n-error-color);">清除下载记录</n-button>
          </template>
          {{ clearHistoryTip }}
        </n-popconfirm>
        <n-button v-bind="getButtonStyle('secondary')" size="small" @click="handleRetryRecognition" :loading="loading">
          重试识别失败项
        </n-button>
        <n-button v-bind="getButtonStyle('dialogCancel')" size="small" @click="emit('update:show', false)">
          关闭
        </n-button>
      </div>
    </div>

    <!-- 卡片列表（自然撑开，走浏览器滚动条） -->
    <div v-if="items.length > 0" class="cards-list">
      <div
        v-for="(item, index) in items"
        :key="item.guid"
        class="feed-card-item"
      >
        <!-- 左侧主内容 -->
        <div class="card-main">
          <div class="card-top-row">
            <div class="card-tags-left">
              <n-tag size="small" round :bordered="false" style="color: #fff; background: #6d4c50; border-radius: 12px;">
                {{ item.feed_name || '-' }}
              </n-tag>
              <n-tag
                size="small"
                round
                :bordered="false"
                :style="item.is_downloaded
                  ? { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' }
                  : { color: '#fff', backgroundColor: '#757575', borderRadius: '12px' }"
              >
                {{ item.is_downloaded ? '已下载' : '未下载' }}
              </n-tag>
              <span v-if="item.tmdb_title" class="card-tmdb-inline">
                🎯 {{ item.tmdb_title }}
              </span>
            </div>
            <span class="card-index">#{{ index + 1 }}</span>
          </div>

          <div class="card-title">{{ item.title }}</div>

          <div v-if="cleanDescription(item.description)" class="card-desc">
            {{ cleanDescription(item.description) }}
          </div>

          <div class="card-tags">
            <n-tag v-if="item.in_subscription" size="small" round :bordered="false" style="color: #fff; background: #0288d1; border-radius: 12px;">已订阅</n-tag>
            <n-tag v-if="item.episode_collected" size="small" round :bordered="false" style="color: #fff; background: #2e7d32; border-radius: 12px;">订阅已下载</n-tag>

            <template v-if="item.recognition_done && item.tmdb_id">
              <a
                :href="`https://www.themoviedb.org/${item.media_type === 'movie' ? 'movie' : 'tv'}/${item.tmdb_id}`"
                target="_blank"
                class="tmdb-id-tag"
              >ID: {{ item.tmdb_id }}</a>
              <n-tag size="small" round :bordered="false" style="color: #fff; background: #1565c0; border-radius: 12px;">
                {{ item.media_type === 'movie' ? '🎬 电影' : '📺 剧集' }}
              </n-tag>
              <n-tag v-if="item.media_type === 'tv'" size="small" round :bordered="false" style="color: #fff; background: #3B82F6; border-radius: 12px;">
                S{{ item.season || 1 }} E{{ item.episode || '-' }}
              </n-tag>
            </template>
            <n-tag v-else-if="item.recognition_done" size="small" round :bordered="false" style="color: var(--color-warning); background: var(--color-warning-bg);">未命中</n-tag>

            <n-tag v-if="item.team" size="small" round :bordered="false" style="color: #fff; background: #0d47a1; border-radius: 12px;">{{ item.team }}</n-tag>
            <n-tag v-if="item.source" size="small" round :bordered="false" style="color: #fff; background: #c62828; border-radius: 12px;">{{ item.source }}</n-tag>
            <n-tag v-if="item.platform" size="small" round :bordered="false" style="color: #fff; background: #c62828; border-radius: 12px;">{{ item.platform }}</n-tag>
            <n-tag v-if="item.resolution" size="small" round :bordered="false" style="color: #fff; background: #e65100; border-radius: 12px;">{{ item.resolution }}</n-tag>
            <n-tag v-if="item.video_effect" size="small" round :bordered="false" style="color: #fff; background: #e65100; border-radius: 12px;">{{ item.video_effect }}</n-tag>
            <n-tag v-if="item.video_encode" size="small" round :bordered="false" style="color: #fff; background: #e65100; border-radius: 12px;">{{ item.video_encode }}</n-tag>
            <n-tag v-if="item.audio_encode" size="small" round :bordered="false" style="color: #fff; background: #e65100; border-radius: 12px;">{{ item.audio_encode }}</n-tag>
            <n-tag v-if="item.subtitle" size="small" round :bordered="false" style="color: #fff; background: #e65100; border-radius: 12px;">{{ item.subtitle }}</n-tag>
          </div>
        </div>

        <!-- 右侧操作区 -->
        <div class="card-aside">
          <div class="card-time">{{ formatPubDate(item.pub_date) }}</div>
          <div class="card-actions">
            <n-button
              v-bind="getButtonStyle('primary')"
              size="small"
              @click="handleToggleHistory(item, !item.is_downloaded)"
            >
              {{ item.is_downloaded ? '清除下载记录' : '设为已下载' }}
            </n-button>
            <n-dropdown
              trigger="click"
              placement="bottom-end"
              :options="clientDropdownOptions"
              :disabled="clientOptions.length === 0"
              @select="(key: string) => handleDownload(item, key)"
            >
              <n-button
                v-bind="getButtonStyle('secondary')"
                size="small"
                :disabled="clientOptions.length === 0"
              >
                {{ clientOptions.length === 0 ? '无下载器' : '手动下载' }}
              </n-button>
            </n-dropdown>
          </div>
        </div>
      </div>

      <!-- 底部哨兵 + 加载状态 -->
      <div ref="sentinelRef" class="sentinel">
        <div v-if="loading && offset > 0" class="loading-more">
          <n-spin size="small" />
          <span>加载中...</span>
        </div>
        <div v-else-if="!hasMore" class="no-more">
          已全部加载
        </div>
      </div>
    </div>

    <div v-else-if="loading" class="empty-state">
      <n-spin />
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无数据" />
    </div>
  </AppGlassModal>
</template>

<style scoped>
/* 顶部工具栏 */
.toolbar {
  margin-bottom: 12px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
  margin-bottom: 8px;
}
.filter-item {
  flex: 1;
}
.filter-item :deep(.app-search-field),
.filter-item :deep(.app-search-field__box) {
  height: 100%;
}

.action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.total-text {
  font-size: 12px;
  color: var(--text-muted);
  margin-right: auto;
}

/* 卡片列表 */
.cards-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 单张卡片 */
.feed-card-item {
  display: flex;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  transition: all 0.2s ease;
}

.feed-card-item:hover {
  border-color: var(--n-primary-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

/* 左侧主内容 */
.card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-tags-left {
  display: flex;
  gap: 6px;
  align-items: center;
  min-width: 0;
  overflow: hidden;
  flex: 1;
}

.card-index {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  flex-shrink: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
}

.card-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding-right: 48px;
}

.card-tmdb-inline {
  font-size: 12px;
  font-weight: bold;
  color: var(--n-primary-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.tmdb-id-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 500;
  color: #fff;
  background: #2e7d32;
  border-radius: 12px;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tmdb-id-tag:hover {
  opacity: 0.85;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

/* 右侧操作区 */
.card-aside {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  min-width: 180px;
}

.card-time {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* 底部哨兵 */
.sentinel {
  min-height: 1px;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.no-more {
  text-align: center;
  padding: 16px 0;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-state {
  padding: 80px 0;
  text-align: center;
}
</style>
