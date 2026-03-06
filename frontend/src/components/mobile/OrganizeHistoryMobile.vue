<script setup lang="ts">
import { ref, h, onMounted, onUnmounted } from 'vue'
import { 
  NButton, NIcon, NTag, NInput, NPopconfirm, NEmpty, NSpace, NRadioGroup, NRadioButton, NAlert, NText,
  NDropdown, NCollapse, NCollapseItem, NCheckbox, NSpin, NDivider
} from 'naive-ui'
import {
  HistoryOutlined as HistoryIcon,
  DeleteOutlined as DeleteIcon,
  SearchOutlined as SearchIcon,
  FolderOutlined as FolderIcon,
  ArrowForwardOutlined as ArrowIcon,
  AccessTimeOutlined as TimeIcon,
  StorageOutlined as SizeIcon,
  DoneAllOutlined as SuccessIcon,
  ErrorOutlineOutlined as ErrorIcon,
  MoreVertOutlined as MoreIcon,
  FilterListOutlined as FilterIcon,
  RefreshOutlined as RefreshIcon,
  KeyboardDoubleArrowDownOutlined as MoreArrowIcon
} from '@vicons/material'
import { useOrganizeHistory } from '../../composables/views/useOrganizeHistory'

const {
  loading,
  searchQuery,
  statusFilter,
  filteredHistory,
  hasMore,
  fetchData,
  loadMore,
  deleteItem,
  clearAll,
  getActionLabel,
  formatTime
} = useOrganizeHistory()

const shouldDeleteFile = ref(false)
const showSearch = ref(false)

const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

import { watch, nextTick } from 'vue'

const setupObserver = (el: HTMLElement) => {
  if (observer) observer.disconnect()
  
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      loadMore()
    }
  }, { 
    threshold: 0,
    rootMargin: '200px'
  })
  observer.observe(el)
}

watch(scrollTarget, (el) => {
  if (el) {
    setupObserver(el)
  }
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

onUnmounted(() => {
  if (observer) observer.disconnect()
})

const handleRefresh = () => {
  fetchData(true)
}

const handleMenuSelect = (key: string) => {
  if (key === 'refresh') handleRefresh()
  else if (key === 'clear') {
    if(confirm('确定要清空所有历史记录吗？')) clearAll()
  }
}

const menuOptions = [
  { label: '刷新列表', key: 'refresh', icon: () => h(NIcon, null, { default: () => h(RefreshIcon) }) },
  { label: '清空历史', key: 'clear', icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }), style: { color: 'var(--n-error-color)' } }
]
</script>

<template>
  <div class="mobile-history-view">
    <!-- Top Bar -->
    <div class="mobile-header">
      <div class="header-left">
        <n-icon size="24" style="color: var(--n-primary-color); margin-right: 8px;"><HistoryIcon /></n-icon>
        <span class="header-title">整理历史</span>
      </div>
      <div class="header-right">
        <n-button circle quaternary @click="showSearch = !showSearch">
          <template #icon><n-icon><SearchIcon /></n-icon></template>
        </n-button>
        <n-dropdown trigger="click" :options="menuOptions" @select="handleMenuSelect">
          <n-button circle quaternary>
            <template #icon><n-icon><MoreIcon /></n-icon></template>
          </n-button>
        </n-dropdown>
      </div>
    </div>

    <!-- Search & Filter Bar (Expandable) -->
    <div v-if="showSearch" class="search-bar">
      <n-input v-model:value="searchQuery" placeholder="搜索..." size="small" clearable>
        <template #prefix><n-icon><SearchIcon /></n-icon></template>
      </n-input>
      <div class="filter-row">
        <n-radio-group v-model:value="statusFilter" size="small">
          <n-radio-button value="all">全部</n-radio-button>
          <n-radio-button value="success">成功</n-radio-button>
          <n-radio-button value="skipped">跳过</n-radio-button>
          <n-radio-button value="failed">失败</n-radio-button>
        </n-radio-group>
      </div>
    </div>

    <!-- List -->
    <div v-if="filteredHistory.length > 0" class="history-list">
      <div v-for="item in filteredHistory" :key="item.id" class="history-card">
        <div class="card-top">
          <div class="card-title-group">
            <div class="card-title">{{ item.title || item.filename }}</div>
            <div class="card-meta-inline">
              <span v-if="item.year" class="meta-year">({{ item.year }})</span>
              <span v-if="item.season || item.episode" class="meta-se">S{{ String(item.season || 1).padStart(2, '0') }}E{{ item.episode }}</span>
              <n-tag v-if="item.media_type" size="tiny" :type="item.media_type === '电影' ? 'warning' : 'success'" quaternary round>
                {{ item.media_type }}
              </n-tag>
            </div>
          </div>
          <div class="card-status">
             <n-icon v-if="item.status === 'failed'" color="#e88080" size="20"><ErrorIcon/></n-icon>
             <n-icon v-else-if="item.status === 'skipped'" color="#f0a020" size="20"><ArrowIcon/></n-icon>
             <n-icon v-else color="#63e2b7" size="20"><SuccessIcon/></n-icon>
          </div>
        </div>
        
        <div class="card-tags">
           <n-tag v-if="item.resolution" size="tiny" type="info" bordered>{{ item.resolution }}</n-tag>
           <n-tag v-if="item.video_encode" size="tiny" type="warning" bordered>{{ item.video_encode }}</n-tag>
           <n-tag v-if="item.team" size="tiny" type="default" bordered>{{ item.team }}</n-tag>
           <n-tag size="tiny" quaternary>{{ getActionLabel(item.action_type) }}</n-tag>
           <n-tag v-if="item.file_size" size="tiny" quaternary color="#888">{{ item.file_size }}</n-tag>
        </div>

        <div v-if="item.status === 'failed' && item.message" class="error-box">
           {{ item.message }}
        </div>

        <div v-if="item.status === 'skipped' && item.message" class="skipped-box">
           {{ item.message }}
        </div>

        <div class="path-info">
           <div class="path-row">
             <span class="path-label">源</span>
             <span class="path-text">{{ item.source_path }}</span>
           </div>
           <div class="path-row">
             <span class="path-label">至</span>
             <span class="path-text highlight">{{ item.target_path }}</span>
           </div>
        </div>

        <div class="card-footer">
           <div class="footer-left">
             <div class="footer-time">{{ formatTime(item.processed_at) }}</div>
             <div v-if="item.tmdb_id" class="footer-tmdb">TMDB: {{ item.tmdb_id }}</div>
           </div>
           <n-popconfirm 
              @positive-click="deleteItem(item.id, shouldDeleteFile)" 
              @negative-click="shouldDeleteFile = false"
              positive-text="确定"
              negative-text="取消"
            >
              <template #trigger>
                <n-button size="tiny" quaternary type="error" circle><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
              </template>
              <div style="max-width: 200px">
                <p style="margin: 0 0 8px 0">删除此记录?</p>
                <n-checkbox v-model:checked="shouldDeleteFile">
                   <span style="color: var(--n-error-color); font-size: 12px">同时物理删除源文件</span>
                </n-checkbox>
              </div>
           </n-popconfirm>
        </div>
      </div>

      <!-- Sentinel for Infinite Scroll -->
      <div ref="scrollTarget" class="load-more-sentinel">
        <n-spin v-if="loading" size="small" description="正在加载..." />
        <div v-else-if="!hasMore" class="end-of-list">
          <n-divider dashed>
            <n-text depth="3" style="font-size: 11px">到底了 (共{{ filteredHistory.length }}条)</n-text>
          </n-divider>
        </div>
        <div v-else class="can-load-more">
           <n-icon size="14"><MoreArrowIcon /></n-icon>
           向上滑动加载更多
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <n-empty description="没有找到记录" />
    </div>
  </div>
</template>

<style scoped>
.mobile-history-view {
  padding-bottom: 20px;
}
.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px 12px 4px;
}
.header-left { display: flex; align-items: center; }
.header-title { font-size: 18px; font-weight: bold; }

.search-bar {
  background: var(--app-surface-inner);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.filter-row { margin-top: 8px; display: flex; justify-content: center; }

.history-list { display: flex; flex-direction: column; gap: 12px; }

.history-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
}

.card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.card-title-group { flex: 1; min-width: 0; }
.card-title { font-weight: bold; font-size: 15px; line-height: 1.3; margin-bottom: 4px; word-break: break-all; color: var(--n-text-color-1); }
.card-meta-inline { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.meta-year { font-size: 12px; color: var(--n-text-color-3); }
.meta-se { font-size: 12px; font-weight: bold; color: var(--n-primary-color); font-family: monospace; }

.card-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 12px; }

.error-box {
  background: rgba(232, 128, 128, 0.1);
  color: #e88080;
  font-size: 11px;
  padding: 6px;
  border-radius: var(--button-border-radius, 4px);
  margin-bottom: 10px;
}

.skipped-box {
  background: rgba(240, 160, 32, 0.1);
  color: #f0a020;
  font-size: 11px;
  padding: 6px;
  border-radius: var(--button-border-radius, 4px);
  margin-bottom: 10px;
}

.path-info {
  background: var(--app-surface-inner);
  border-radius: var(--button-border-radius, 6px);
  padding: 8px;
  margin-bottom: 12px;
  border: 1px solid var(--app-border-light);
}
.path-row { display: flex; align-items: flex-start; margin-bottom: 4px; }
.path-row:last-child { margin-bottom: 0; }
.path-label { font-size: 10px; color: #666; width: 16px; flex-shrink: 0; margin-top: 2px; font-weight: bold; }
.path-text { font-size: 11px; color: #888; word-break: break-all; font-family: monospace; line-height: 1.3; }
.path-text.highlight { color: #bbb; }

.card-footer { display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; }
.footer-left { display: flex; flex-direction: column; gap: 2px; }
.footer-time { font-size: 11px; color: #666; }
.footer-tmdb { font-size: 10px; color: #444; font-family: monospace; }

.empty-state { padding: 40px 0; text-align: center; }

.load-more-sentinel {
  padding: 20px 0 30px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.end-of-list {
  width: 100%;
  opacity: 0.5;
}

.can-load-more {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--n-text-color-3);
  font-size: 11px;
}
</style>
