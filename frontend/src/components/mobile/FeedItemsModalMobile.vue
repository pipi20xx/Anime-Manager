<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { 
  NModal, NButton, NSpace, NIcon, NTag, NDrawer, NDrawerContent
} from 'naive-ui'
import { 
  DownloadOutlined as DownloadIcon, 
  HistoryOutlined as HistoryIcon,
  CloseOutlined as CloseIcon,
  RefreshOutlined as RefreshIcon
} from '@vicons/material'
import { useFeedItems } from '../../composables/modals/useFeedItems'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  feed: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  offset,
  hasMore,
  clientOptions,
  fetchItems,
  handleDownload,
  handleToggleHistory,
  handleRetryRecognition
} = useFeedItems(props)

const mobileListRef = ref<any>(null)
const showClientDrawer = ref(false)
const currentItem = ref<any>(null)

const cleanDescription = (desc: string | null | undefined): string | null => {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  if (clean.length > 100) {
    clean = clean.substring(0, 100) + '...'
  }
  return clean || null
}

const formatPubDate = (dateStr: string | null | undefined): string => {
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

const openDownloadDrawer = (item: any) => {
  if (clientOptions.value.length === 0) return
  
  if (clientOptions.value.length === 1) {
    handleDownload(item, clientOptions.value[0].value)
  } else {
    currentItem.value = item
    showClientDrawer.value = true
  }
}

const selectClient = (clientId: string) => {
  if (currentItem.value) {
    handleDownload(currentItem.value, clientId)
  }
  showClientDrawer.value = false
  currentItem.value = null
}

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  if (!target || loading.value || !hasMore.value) return
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50) {
    fetchItems(true)
  }
}

const setupScrollListener = () => {
  nextTick(() => {
    const el = mobileListRef.value
    if (el) {
      el.removeEventListener('scroll', handleScroll)
      el.addEventListener('scroll', handleScroll)
    }
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems(false)
    setupScrollListener()
  }
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)"
    :mask-closable="true"
    transform-origin="center"
  >
    <div class="mobile-feed-modal">
      <div class="mobile-header">
        <div class="header-title">
          <span>订阅源详情</span>
        </div>
        <n-button 
          v-bind="getButtonStyle('icon')" 
          size="small" 
          @click="emit('update:show', false)"
        >
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
      </div>

      <div class="mobile-subtitle" v-if="feed?.title || feed?.url">
        {{ feed.title || feed.url }}
      </div>

      <div class="mobile-content" ref="mobileListRef">
        <div v-if="items.length > 0" class="items-list">
          <div v-for="item in items" :key="item.guid" class="feed-item">
            <div class="item-header">
              <div class="status-indicator" :class="{ downloaded: item.is_downloaded }"></div>
              <div class="item-title">{{ item.title }}</div>
            </div>
            
            <div class="item-desc" v-if="cleanDescription(item.description)">
              {{ cleanDescription(item.description) }}
            </div>
            
            <div class="item-time">{{ formatPubDate(item.pub_date) }}</div>

            <div v-if="item.tmdb_title" class="tmdb-info">
              <span class="tmdb-icon">🎯</span>
              <span class="tmdb-title">{{ item.tmdb_title }}</span>
            </div>

            <div class="item-tags">
              <n-tag v-if="item.in_subscription" size="tiny" round :bordered="false" 
                style="color: #fff; background: #0288d1;">
                已订阅
              </n-tag>
              <n-tag v-if="item.episode_collected" size="tiny" round :bordered="false"
                style="color: #fff; background: #2e7d32;">
                已下载
              </n-tag>

              <template v-if="item.recognition_done && item.tmdb_id">
                <a 
                  :href="`https://www.themoviedb.org/${item.media_type === 'movie' ? 'movie' : 'tv'}/${item.tmdb_id}`"
                  target="_blank"
                  class="tmdb-link"
                >ID: {{ item.tmdb_id }}</a>
                <n-tag size="tiny" round :bordered="false" style="color: #fff; background: #1565c0;">
                  {{ item.media_type === 'movie' ? '🎬' : '📺' }}
                </n-tag>
                <n-tag v-if="item.media_type === 'tv'" size="tiny" round :bordered="false"
                  style="color: #fff; background: #3B82F6;">
                  S{{ item.season || 1 }} E{{ item.episode || '-' }}
                </n-tag>
              </template>
              <n-tag v-else-if="item.recognition_done" size="tiny" round :bordered="false"
                style="color: #fff; background: #f57c00;">
                未命中
              </n-tag>

              <n-tag v-if="item.team" size="tiny" round :bordered="false"
                style="color: #fff; background: #0d47a1;">
                {{ item.team }}
              </n-tag>
              <n-tag v-if="item.resolution" size="tiny" round :bordered="false"
                style="color: #fff; background: #e65100;">
                {{ item.resolution }}
              </n-tag>
              <n-tag v-if="item.source" size="tiny" round :bordered="false"
                style="color: #fff; background: #c62828;">
                {{ item.source }}
              </n-tag>
            </div>

            <div class="item-actions">
              <n-button 
                v-bind="getButtonStyle('primary')" 
                size="small"
                @click="openDownloadDrawer(item)"
                :disabled="clientOptions.length === 0"
              >
                <template #icon><n-icon><DownloadIcon/></n-icon></template>
                {{ clientOptions.length === 0 ? '无下载器' : '下载' }}
              </n-button>
              <n-button 
                v-bind="getButtonStyle('secondary')"
                size="small"
                @click="handleToggleHistory(item)"
              >
                <template #icon><n-icon><HistoryIcon/></n-icon></template>
                {{ item.is_downloaded ? '清除' : '标记' }}
              </n-button>
            </div>
          </div>
        </div>

        <div v-if="loading" class="loading-state">
          <n-icon size="24" class="spin-icon"><RefreshIcon /></n-icon>
          <span>加载中...</span>
        </div>

        <div v-if="!loading && items.length === 0" class="empty-state">
          <span>暂无数据</span>
        </div>
      </div>

      <div class="mobile-footer">
        <div class="footer-info">
          已加载 {{ items.length }} 条
          <span v-if="loading && offset > 0">...</span>
        </div>
        <n-space>
          <n-button 
            v-bind="getButtonStyle('secondary')"
            size="small"
            @click="handleRetryRecognition" 
            :loading="loading"
          >
            重试识别
          </n-button>
        </n-space>
      </div>
    </div>
  </n-modal>

  <n-drawer 
    v-model:show="showClientDrawer" 
    placement="bottom" 
    :height="clientOptions.length * 60 + 100"
    style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;"
  >
    <n-drawer-content title="选择下载客户端" closable :native-scrollbar="false">
      <div class="client-list">
        <div 
          v-for="client in clientOptions" 
          :key="client.value"
          class="client-item"
          @click="selectClient(client.value)"
        >
          <div class="client-icon">
            <n-icon size="20"><DownloadIcon /></n-icon>
          </div>
          <span class="client-name">{{ client.label }}</span>
        </div>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.mobile-feed-modal {
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

.header-title {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  font-size: var(--m-text-lg);
  font-weight: bold;
  color: var(--text-primary);
}

.mobile-subtitle {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  background: var(--app-surface-inner);
  border-bottom: 1px solid var(--app-border-light);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-spacing-md);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.feed-item {
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.item-header {
  display: flex;
  align-items: flex-start;
  gap: var(--m-spacing-sm);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
  flex-shrink: 0;
  margin-top: 6px;
}

.status-indicator.downloaded {
  background: var(--n-success-color);
  box-shadow: 0 0 6px var(--n-success-color);
}

.item-title {
  font-size: var(--m-text-sm);
  font-weight: bold;
  line-height: 1.4;
  word-break: break-all;
  color: var(--text-primary);
  flex: 1;
}

.item-desc {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-time {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  font-family: monospace;
}

.tmdb-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--app-surface-card);
  border-radius: var(--m-radius-sm);
  border: 1px solid var(--app-border-light);
}

.tmdb-icon {
  font-size: 14px;
}

.tmdb-title {
  font-size: var(--m-text-xs);
  font-weight: bold;
  color: var(--n-primary-color);
}

.item-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.tmdb-link {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 500;
  color: #fff;
  background: #2e7d32;
  border-radius: 10px;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tmdb-link:active {
  opacity: 0.8;
  transform: scale(0.95);
}

.item-actions {
  display: flex;
  gap: var(--m-spacing-sm);
  margin-top: var(--m-spacing-sm);
  padding-top: var(--m-spacing-sm);
  border-top: 1px solid var(--app-border-light);
}

.item-actions .n-button {
  flex: 1;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-spacing-sm);
  padding: var(--m-spacing-xl);
  color: var(--text-muted);
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px var(--m-spacing-lg);
  color: var(--text-muted);
  font-size: var(--m-text-md);
}

.mobile-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-md);
  border-top: 1px solid var(--app-border-light);
  background: var(--app-surface-inner);
}

.footer-info {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
}

.client-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}

.client-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
  background: var(--app-surface-inner);
}

.client-item:active {
  background: var(--bg-surface-hover);
}

.client-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--n-primary-color);
  border-radius: var(--m-radius-md);
  color: #fff;
}

.client-name {
  font-size: var(--m-text-md);
  font-weight: 500;
  color: var(--text-primary);
}
</style>
