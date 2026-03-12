<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { 
  NButton, NIcon, NTag, NInput, NPopconfirm, NEmpty, NSpace, NRadioGroup, NRadioButton, NAlert, NText, NCheckbox, NSpin, NDivider
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
  KeyboardDoubleArrowDownOutlined as MoreIcon,
  RefreshOutlined as RefreshIcon
} from '@vicons/material'
import { useOrganizeHistory } from '../../composables/views/useOrganizeHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
</script>

<template>
  <div class="history-view">
    <div class="page-header mb-6">
      <div class="d-flex align-center gap-3">
        <div>
          <h1 class="m-0">整理历史</h1>
          <div class="subtitle">记录所有成功的媒体识别与入库流水</div>
        </div>
      </div>
      <n-space>
        <n-radio-group v-model:value="statusFilter" size="medium">
          <n-radio-button value="all">全部</n-radio-button>
          <n-radio-button value="success">成功</n-radio-button>
          <n-radio-button value="skipped">跳过</n-radio-button>
          <n-radio-button value="failed">失败</n-radio-button>
        </n-radio-group>
        <n-input v-model:value="searchQuery" placeholder="搜索标题或文件名..." style="width: 250px">
          <template #prefix><n-icon><SearchIcon /></n-icon></template>
        </n-input>
        <n-popconfirm @positive-click="clearAll" positive-text="确定清空" negative-text="我再想想">
          <template #trigger>
            <n-button v-bind="getButtonStyle('danger')">
              清空历史
            </n-button>
          </template>
          确定要彻底删除所有整理记录吗？这不会影响磁盘上的文件。
        </n-popconfirm>
        <n-button v-bind="getButtonStyle('secondary')" @click="handleRefresh" :loading="loading">
          刷新数据
        </n-button>
      </n-space>
    </div>

    <div v-if="filteredHistory.length > 0" class="history-list">
      <div v-for="item in filteredHistory" :key="item.id" class="history-item">
        <!-- 现有项内容保持不变 -->
        <!-- 1. Header: Title & Meta -->
        <div class="item-row header-row">
          <div class="title-group">
            <span class="item-title">{{ item.title || item.filename }}</span>
            <span class="item-year" v-if="item.year">({{ item.year }})</span>
            <span class="item-se" v-if="item.season || item.episode">
              S{{ item.season?.toString().padStart(2, '0') }}E{{ item.episode }}
            </span>
            <n-tag v-if="item.media_type" size="small" :type="item.media_type === '电影' ? 'warning' : 'success'" quaternary round class="ml-2">
              {{ item.media_type }}
            </n-tag>
            
            <n-tag size="tiny" type="info" bordered class="ml-2" v-if="item.resolution">{{ item.resolution }}</n-tag>
            <n-tag size="tiny" type="warning" bordered class="ml-1" v-if="item.video_encode">{{ item.video_encode }}</n-tag>
            <n-tag size="tiny" type="default" bordered class="ml-1" v-if="item.team">{{ item.team }}</n-tag>
          </div>
          <div class="item-status">
            <n-tag 
              :type="item.status === 'failed' ? 'error' : (item.status === 'skipped' ? 'warning' : 'success')" 
              size="small" 
              ghost 
              bordered
            >
              <template #icon>
                <n-icon v-if="item.status === 'failed'"><ErrorIcon /></n-icon>
                <n-icon v-else-if="item.status === 'skipped'"><ArrowIcon /></n-icon>
                <n-icon v-else><SuccessIcon /></n-icon>
              </template>
              {{ item.status === 'failed' ? '失败' : (item.status === 'skipped' ? '跳过' : '成功') }}
            </n-tag>
            <n-popconfirm 
              @positive-click="deleteItem(item.id, shouldDeleteFile)" 
              @negative-click="shouldDeleteFile = false"
              positive-text="确定删除"
              negative-text="取消"
            >
              <template #trigger>
                <n-button v-bind="getButtonStyle('iconDanger')" size="small" class="ml-2">
                  <template #icon><n-icon><DeleteIcon /></n-icon></template>
                </n-button>
              </template>
              <div style="max-width: 240px">
                <p class="m-0 mb-2">确定要删除这条整理记录吗？</p>
                <n-checkbox v-model:checked="shouldDeleteFile">
                  <span style="color: var(--n-error-color)">同时物理删除源文件</span>
                </n-checkbox>
                <div v-if="shouldDeleteFile" style="font-size: 11px; color: var(--n-text-color-3); margin-top: 4px; line-height: 1.2;">
                   警告：这将尝试永久删除原始源路径下的文件。
                </div>
              </div>
            </n-popconfirm>
          </div>
        </div>

        <!-- Error Message Row -->
        <div v-if="item.status === 'failed' && item.message" class="error-msg-row mt-2">
          <n-alert type="error" :show-icon="false" size="small" class="py-1">
            {{ item.message }}
          </n-alert>
        </div>

        <!-- Skipped Message Row -->
        <div v-if="item.status === 'skipped' && item.message" class="skipped-msg-row mt-2">
          <n-alert type="warning" :show-icon="false" size="small" class="py-1">
            {{ item.message }}
          </n-alert>
        </div>

        <!-- 2. Paths (Vertical Stacked) -->
        <div class="path-container mt-3">
          <div class="path-item source">
            <div class="path-label">源路径</div>
            <div class="path-content">
              <n-icon><FolderIcon /></n-icon>
              <span class="path-text">{{ item.source_path }}</span>
            </div>
          </div>
          <div class="path-divider">
            <div class="line"></div>
            <n-icon size="14"><ArrowIcon /></n-icon>
            <div class="line"></div>
          </div>
          <div class="path-item target">
            <div class="path-label">目标路径</div>
            <div class="path-content">
              <n-icon style="color: var(--n-primary-color)"><FolderIcon /></n-icon>
              <span class="path-text">{{ item.target_path }}</span>
            </div>
          </div>
        </div>

        <!-- 3. Footer: Details -->
        <div class="item-row footer-row mt-3">
          <div class="detail-group">
            <div class="detail-item">
              <span class="label">转移方式：</span>
              <n-tag size="tiny" type="info" secondary>{{ getActionLabel(item.action_type) }}</n-tag>
            </div>
            <div class="detail-item">
              <n-icon><SizeIcon /></n-icon>
              <span>{{ item.file_size || '未知大小' }}</span>
            </div>
            <div class="detail-item">
              <n-icon><TimeIcon /></n-icon>
              <span>{{ formatTime(item.processed_at) }}</span>
            </div>
            <div class="detail-item" v-if="item.tmdb_id">
              <n-text depth="3" code>TMDB: {{ item.tmdb_id }}</n-text>
            </div>
          </div>
        </div>
      </div>

      <!-- Sentinel for Infinite Scroll -->
      <div ref="scrollTarget" class="load-more-sentinel">
        <n-spin v-if="loading" size="small" description="正在加载更多..." />
        <div v-else-if="!hasMore" class="end-of-list">
          <n-divider dashed>
            <n-text depth="3" style="font-size: 12px">到底了，共 {{ filteredHistory.length }} 条记录</n-text>
          </n-divider>
        </div>
        <div v-else class="can-load-more">
           <n-icon size="16"><MoreIcon /></n-icon>
           向下滚动加载更多
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <n-empty description="暂无整理历史" />
    </div>
  </div>
</template>

<style scoped>
.history-view { width: 100%; padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h1 { margin: 0; font-size: 26px; font-weight: bold; color: var(--text-primary); }
.subtitle { font-size: 12px; color: var(--n-primary-color); letter-spacing: 1px; }
.page-header :deep(.n-space) { align-items: stretch; }
.page-header :deep(.n-radio-group) { height: 34px; }
.page-header :deep(.n-input) { height: 34px; }
.page-header :deep(.n-button) { height: 34px; }

.history-list { display: flex; flex-direction: column; gap: 16px; margin-bottom: 40px; }

.history-item {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 12px);
  padding: 16px 20px;
  transition: all var(--transition-normal);
}
.history-item:hover {
  background: var(--app-surface-inner);
  border-color: var(--n-primary-color);
  transform: translateY(-2px);
}

.item-row { display: flex; align-items: center; justify-content: space-between; }

/* Header Row */
.title-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.item-title { font-size: 17px; font-weight: bold; color: var(--n-text-color-1); }
.item-year { font-size: 13px; color: var(--n-text-color-3); }
.item-se {
  color: var(--n-primary-color);
  font-family: var(--code-font);
  font-weight: bold;
  background: var(--primary-light);
  padding: 2px 6px;
  border-radius: var(--code-radius, 4px);
}

/* Path Container (Vertical) */
.path-container {
  display: flex;
  flex-direction: column;
  background: transparent;
  border-radius: var(--code-radius, 8px);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
}

.path-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  gap: 12px;
}

.path-item.source {
  background: var(--warning-subtle);
}

.path-item.target {
  background: var(--primary-subtle);
}

.path-label {
  font-size: 9px;
  font-weight: 900;
  padding: 2px 4px;
  border-radius: var(--button-border-radius, 3px);
  min-width: 45px;
  text-align: center;
  flex-shrink: 0;
}

.source .path-label {
  background: var(--warning-light);
  color: var(--n-warning-color); 
}
.target .path-label {
  background: var(--primary-light);
  color: var(--n-primary-color);
}

.path-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.path-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source .path-text { color: var(--n-text-color-3); }
.target .path-text { color: var(--n-text-color-2); }

.path-divider {
  height: 1px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  opacity: var(--opacity-disabled);
  color: var(--app-border-light);
  background: var(--app-border-light);
}
.path-divider .line { display: none; }
.path-divider .n-icon { margin: 0 auto; }

/* Footer Row */
.footer-row { color: var(--n-text-color-3); font-size: 13px; }
.detail-group { display: flex; align-items: center; gap: 24px; }
.detail-item { display: flex; align-items: center; gap: 6px; }
.label { color: var(--n-text-color-3); }

.ml-2 { margin-left: 8px; }
.mt-3 { margin-top: 12px; }
.mb-6 { margin-bottom: 24px; }
.d-flex { display: flex; }
.align-center { align-items: center; }
.gap-3 { gap: 12px; }
.m-0 { margin: 0; }

.empty-state { padding: 100px 0; }

.load-more-sentinel {
  padding: 24px 0 48px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.end-of-list {
  width: 100%;
  opacity: var(--opacity-secondary);
}

.can-load-more {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--n-text-color-3);
  font-size: 13px;
  opacity: var(--opacity-primary);
}
</style>
