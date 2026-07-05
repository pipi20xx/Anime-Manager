<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import AppGlassCard from '../AppGlassCard.vue'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import AppSearchField from '../AppSearchField.vue'
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { 
  NSpace, NButton, NIcon, NGrid, NGi, NImage, NTag,
  NEmpty, NSpin, NForm, NFormItem, NPopconfirm
} from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  SearchOutlined as SearchIcon,
  FileDownloadOutlined as ExportIcon,
  CloudSyncOutlined as SytmdbIcon,
  AddOutlined as AddIcon,
  DeleteSweepOutlined as ClearIcon
} from '@vicons/material'
import { useTmdbData } from '../../composables/views/useTmdbData'
import { getButtonStyle } from '../../composables/useButtonStyles'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const showRefreshModal = ref(false)
const refreshForm = ref({
  olderThanDays: null as number | null,
  year: null as number | null,
  mediaType: null as string | null
})

const {
  browserData,
  browserTotal,
  browserSearch,
  browserLoading,
  browserHasMore,
  showEditModal,
  isEditing,
  editForm,
  fetchBrowserData,
  handleBrowserSearch,
  openCreate,
  openEdit,
  saveMetadata,
  deleteMetadata,
  handleSyncSytmdb,
  handleRefreshAll,
  handleExport,
  clearFingerprints
} = useTmdbData()

const executeRefresh = () => {
  const options: { olderThanDays?: number; year?: number; mediaType?: string } = {}
  if (refreshForm.value.olderThanDays) options.olderThanDays = refreshForm.value.olderThanDays
  if (refreshForm.value.year) options.year = refreshForm.value.year
  if (refreshForm.value.mediaType) options.mediaType = refreshForm.value.mediaType
  handleRefreshAll(options)
  showRefreshModal.value = false
  refreshForm.value = { olderThanDays: null, year: null, mediaType: null }
}

const getImg = (path: string) => {
  if (!path) return ''
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
  }
  if (!path.startsWith('http')) return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  return path
}

// 无限滚动
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const setupObserver = () => {
  cleanupObserver()
  nextTick(() => {
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !browserLoading.value && browserHasMore.value) {
          fetchBrowserData(true)
        }
      },
      { rootMargin: '300px' }
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

// 搜索时重新挂载 observer
watch(() => browserData.value.length, () => {
  if (browserHasMore.value) {
    setupObserver()
  }
})

onBeforeUnmount(cleanupObserver)
</script>

<template>
  <div class="tmdb-full-view">
    <!-- 工具栏 -->
    <div class="toolbar-row">
      <AppSearchField v-model:value="browserSearch" placeholder="搜索标题或 TMDB ID..." :loading="browserLoading" @search="handleBrowserSearch" style="width: 300px" />
      <n-space>
        <n-button v-bind="getButtonStyle('secondary')" @click="handleExport">导出字典</n-button>
        <n-button v-bind="getButtonStyle('warning')" @click="showRefreshModal = true">全量刷新</n-button>
        <n-button v-bind="getButtonStyle('warning')" @click="clearFingerprints">清空智能记忆</n-button>
        <n-button v-bind="getButtonStyle('warning')" @click="handleSyncSytmdb">同步 SYTMDB</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="openCreate">手动新增</n-button>
      </n-space>
    </div>

    <!-- 全量刷新弹窗 -->
    <AppGlassModal appearance-key="tmdb-full-data-modal" v-model:show="showRefreshModal" title="全量刷新设置" style="width: 450px">
      <n-form label-placement="left" label-width="120px">
        <n-form-item>
          <AppTextField 
            v-model:value="refreshForm.olderThanDays" 
            label="更新时间筛选"
            placeholder="留空表示不限制"
            type="number"
            :min="1"
          >
            <template #suffix>天前的数据</template>
          </AppTextField>
        </n-form-item>
        <n-form-item>
          <AppTextField 
            v-model:value="refreshForm.year" 
            label="首播年份筛选"
            placeholder="留空表示不限制"
            type="number"
            :min="1900" 
            :max="2100"
          />
        </n-form-item>
        <n-form-item>
          <AppSelectField 
            v-model:value="refreshForm.mediaType"
            label="媒体类型筛选"
            placeholder="留空表示不限制"
            clearable
            :options="[
              { label: '全部类型', value: null },
              { label: '电影', value: 'movie' },
              { label: '剧集', value: 'tv' }
            ]"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showRefreshModal = false">取消</n-button>
          <n-popconfirm @positive-click="executeRefresh" positive-text="确认" negative-text="取消">
            <template #trigger>
              <n-button type="warning">开始刷新</n-button>
            </template>
            确定要执行全量刷新吗？此操作将在后台异步进行。
          </n-popconfirm>
        </n-space>
      </template>
    </AppGlassModal>

    <!-- 卡片网格 -->
    <div class="cards-container">
      <n-spin :show="browserLoading">
        <n-grid v-if="browserData.length > 0" :x-gap="16" :y-gap="16" cols="2 600:3 900:4 1200:5 1600:6">
          <n-gi v-for="item in browserData" :key="item.tmdb_id">
            <AppGlassCard appearance-key="tmdb-data-card" hoverable class="meta-card" content-style="padding: 0;" :bordered="true">
              <div class="card-content">
                <!-- 海报 -->
                <div class="poster-box" @click="openEdit(item)">
                  <n-image
                    v-if="item.poster_path"
                    :src="getImg(item.poster_path)"
                    fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
                    object-fit="cover"
                    preview-disabled
                    style="width: 100%; height: 100%;"
                  />
                  <div v-else class="poster-placeholder">
                    <n-icon size="40" :component="item.media_type === 'movie' ? SytmdbIcon : SearchIcon" />
                  </div>
                  <div class="type-badge" :class="item.media_type">
                    {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                  </div>
                </div>

                <!-- 信息区 -->
                <div class="info-box">
                  <div class="meta-title" :title="item.title" @click="openEdit(item)">{{ item.title }}</div>
                  <div class="meta-sub">
                    <span class="meta-year">{{ item.first_air_date?.slice(0, 4) || '-' }}</span>
                    <span class="meta-id">ID: {{ item.tmdb_id }}</span>
                  </div>
                  <div class="meta-genres">
                    <n-tag
                      v-for="g in (item.genres || []).slice(0, 3)"
                      :key="g"
                      size="tiny"
                      round
                      :bordered="false"
                      style="color: #fff; background: #2e7d32;"
                    >{{ g }}</n-tag>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" @click="deleteMetadata(item)">
                      <template #icon><n-icon><DeleteIcon /></n-icon></template>
                    </n-button>
                  </div>
                </div>
              </div>
            </AppGlassCard>
          </n-gi>
        </n-grid>

        <!-- 底部哨兵 + 加载状态 -->
        <div ref="sentinelRef" class="sentinel">
          <div v-if="browserLoading && browserData.length > 0" class="loading-more">
            <n-spin size="small" />
            <span>加载中...</span>
          </div>
          <div v-else-if="!browserHasMore && browserData.length > 0" class="no-more">
            已全部加载（共 {{ browserTotal }} 条）
          </div>
        </div>

        <div v-if="browserData.length === 0 && !browserLoading" class="empty-state">
          <n-empty description="暂无元数据" />
        </div>
      </n-spin>
    </div>

    <!-- 编辑/新增元数据弹窗 -->
    <AppGlassModal appearance-key="tmdb-full-data-modal" v-model:show="showEditModal" style="width: 700px" :title="isEditing ? '修正元数据' : '手动新增元数据'">
      <n-form label-placement="left" label-width="90">
        <n-grid :cols="2" :x-gap="12">
          <n-gi><n-form-item><AppTextField v-model:value="editForm.id" label="TMDB ID" :disabled="isEditing" placeholder="请输入 TMDB ID" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppSelectField v-model:value="editForm.type" label="媒体类型" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" /></n-form-item></n-gi>
        </n-grid>
        <n-form-item><AppTextField v-model:value="editForm.title" label="显示标题" placeholder="请输入显示标题" /></n-form-item>
        <n-form-item><AppTextField v-model:value="editForm.poster_path" label="海报链接" placeholder="请输入海报链接" /></n-form-item>
        <n-form-item><AppTextField v-model:value="editForm.overview" label="内容简介" placeholder="请输入内容简介" type="textarea" :autosize="{minRows:12}" /></n-form-item>
      </n-form>
      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showEditModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveMetadata">保存并固定</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

/* 卡片容器 */
.cards-container {
  min-height: 200px;
  margin-bottom: 16px;
}

/* 单张卡片 - 边框/圆角/背景由全局外观系统统一管理 */
.meta-card {
  overflow: hidden;
  transition: all var(--transition-normal);
}

.meta-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.card-content {
  display: flex;
  flex-direction: column;
}

/* 海报区 */
.poster-box {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  background: var(--app-surface-inner);
  overflow: hidden;
  cursor: pointer;
}

.poster-box :deep(img) {
  width: 100%;
  height: 100%;
  transition: transform var(--transition-slow);
}

.meta-card:hover .poster-box :deep(img) {
  transform: scale(1.08);
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.type-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  color: #fff;
  background: var(--bg-overlay);
  backdrop-filter: blur(8px);
}

.type-badge.movie {
  background: rgba(198, 40, 40, 0.85);
}

.type-badge.tv {
  background: rgba(21, 101, 192, 0.85);
}

/* 信息区 */
.info-box {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-title {
  font-weight: 700;
  font-size: 13px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
  cursor: pointer;
}

.meta-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text-tertiary);
}

.meta-year {
  color: var(--n-primary-color);
  font-weight: 600;
}

.meta-id {
  font-family: monospace;
}

.meta-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  min-height: 20px;
}

.meta-genres :deep(.n-button) {
  margin-left: auto;
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
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.no-more {
  text-align: center;
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-state {
  padding: 80px 0;
  text-align: center;
}
</style>
