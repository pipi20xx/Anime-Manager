<script setup lang="ts">
import AppTextField from '../../components/AppTextField.vue'
import AppSelectField from '../../components/AppSelectField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import AppGlassModal from '../../components/AppGlassModal.vue'
import { ref, onMounted, reactive, h, onUnmounted, watch } from 'vue'
import { 
  NSpace, NButton, NIcon, NInput, NTag, NImage,
  useMessage, useDialog, NText, NModal, 
  NForm, NFormItem, NSelect, NSpin
} from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  RefreshOutlined as RefreshIcon,
  SearchOutlined as SearchIcon,
  SyncOutlined as SyncIcon,
  AddOutlined as AddIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'

import { getButtonStyle } from '../../composables/useButtonStyles'
import { useRouter } from 'vue-router'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const loading = ref(false)
const data = ref<any[]>([])
const searchKeyword = ref('')

const page = ref(1)
const pageSize = 24
const hasMore = ref(true)
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

let debounceTimer: any = null
watch(searchKeyword, () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchCache(true)
  }, 500)
})

const showEditModal = ref(false)
const isEditing = ref(false)
const editForm = reactive({
  id: '',
  type: 'tv',
  title: '',
  original_title: '',
  year: '',
  release_date: '',
  category: '剧集',
  poster_path: '',
  overview: ''
})

const fetchCache = async (reset = false) => {
  if (reset) {
    page.value = 1
    data.value = []
    hasMore.value = true
  }
  
  if (!hasMore.value && !reset) return
  
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: page.value.toString(),
      size: pageSize.toString(),
      q: searchKeyword.value
    })
    const res = await fetch(`${API_BASE}/api/cache?${params.toString()}`)
    const json = await res.json()
    const items = json.items || []
    
    if (reset) data.value = items
    else data.value.push(...items)
    
    if (items.length < pageSize) {
      hasMore.value = false
    } else {
      page.value++
    }
  } catch (e) { message.error('获取缓存失败') }
  finally { loading.value = false }
}

const handleSearch = () => {
  fetchCache(true)
}

const openCreate = () => {
  isEditing.value = false
  Object.assign(editForm, {
    id: '', type: 'tv', title: '', original_title: '', year: '', release_date: '',
    category: '剧集', poster_path: '', overview: ''
  })
  showEditModal.value = true
}

const getImg = (path: string) => {
  if (!path) return ''
  if (path.includes('/api/system/img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    const filename = parts[parts.length - 1]
    return `${API_BASE}/api/system/img?path=/${filename}`
  }
  if (!path.startsWith('http')) {
    return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  }
  return path
}

const openEdit = (item: any) => {
  isEditing.value = true
  Object.assign(editForm, JSON.parse(JSON.stringify(item)))
  showEditModal.value = true
}

const saveCache = async () => {
  if (!editForm.id || !editForm.title) {
    message.warning('ID 和 标题为必填项')
    return
  }
  
  try {
    const res = await fetch(`${API_BASE}/api/cache`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm)
    })
    if (res.ok) {
      message.success('保存成功')
      showEditModal.value = false
      fetchCache(true)
    }
  } catch (e) { message.error('保存失败') }
}

const deleteCache = (item: any) => {
  const key = `${item.type}:${item.id}`
  dialog.warning({
    title: '确认删除',
    content: `确定要从缓存中移除 "${item.title}" 吗？`,
    action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
      h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
      h(NButton, { ...getButtonStyle('dialogDanger'), onClick: async () => {
        await fetch(`${API_BASE}/api/cache/${encodeURIComponent(key)}`, { method: 'DELETE' })
        message.success('已移除')
        const idx = data.value.findIndex(i => i.type === item.type && i.id === item.id)
        if (idx !== -1) data.value.splice(idx, 1)
        dialog.destroyAll()
      } }, { default: () => '确定' })
    ])
  })
}

const syncLoading = ref(false)

const handleSyncSytmdb = async () => {
  syncLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/sytmdb/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
    const result = await res.json()
    if (res.ok) {
      message.success(result.message || '同步任务已启动')
    } else {
      message.error(result.detail || '同步失败')
    }
  } catch (e) { message.error('同步失败') }
  finally { syncLoading.value = false }
}

const clearAll = () => {
  dialog.error({
    title: '极其危险',
    content: '这将永久删除所有本地匹配缓存记录，确定吗？',
    action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
      h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
      h(NButton, { ...getButtonStyle('dialogDanger'), onClick: async () => {
        await fetch(`${API_BASE}/api/cache/clear`, { method: 'POST' })
        message.success('已清空')
        fetchCache(true)
        dialog.destroyAll()
      } }, { default: () => '清空全部' })
    ])
  })
}

const clearFingerprints = async () => {
  dialog.warning({
    title: '确认清空智能记忆',
    content: '这将删除所有智能记忆缓存。识别速度可能会暂时变慢，但不会影响已刮削的数据。',
    action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
      h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
      h(NButton, { ...getButtonStyle('dialogDanger'), onClick: async () => {
        loading.value = true
        try {
          const res = await fetch(`${API_BASE}/api/cache/clear_fingerprints`, { method: 'POST' })
          const data = await res.json()
          message.success(data.message)
          dialog.destroyAll()
        } finally {
          loading.value = false
        }
      } }, { default: () => '清空记忆' })
    ])
  })
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  fetchCache(true)
  
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && !loading.value && hasMore.value) {
      fetchCache(false)
    }
  }, { rootMargin: '200px' })
  
  setTimeout(() => {
    if (sentinel.value) observer?.observe(sentinel.value)
  }, 500)
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- Header -->
    <div class="m-header">
      <div class="m-header-left">
        <n-button text size="small" @click="goBack">
          <template #icon><n-icon size="22"><BackIcon /></n-icon></template>
        </n-button>
      </div>
      <div class="m-header-title">本地缓存</div>
      <div class="m-header-right">
        <n-button text size="small" @click="openCreate">
          <template #icon><n-icon size="20"><AddIcon /></n-icon></template>
        </n-button>
      </div>
    </div>

    <!-- Content -->
    <div class="m-page-scrollable">
      <div class="cache-toolbar">
        <AppSearchField v-model:value="searchKeyword" placeholder="搜索标题或 TMDB ID..." :loading="loading" @search="handleSearch" />
        <n-button type="primary" ghost @click="handleSearch" :loading="loading">
          <template #icon><n-icon><RefreshIcon /></n-icon></template>
        </n-button>
      </div>

      <div class="cache-actions">
        <n-button type="primary" block :loading="syncLoading" @click="handleSyncSytmdb">
          <template #icon><n-icon><SyncIcon /></n-icon></template>
          同步 SYTMDB
        </n-button>
        <n-button block @click="clearFingerprints">
          清空智能记忆
        </n-button>
        <n-button type="error" ghost block @click="clearAll">
          清空全部缓存
        </n-button>
      </div>

      <!-- Cache Grid -->
      <div class="cache-grid-mobile" v-if="data.length > 0">
        <div 
          v-for="item in data" 
          :key="item.type + ':' + item.id" 
          class="cache-card-mobile"
          @click="openEdit(item)"
        >
          <div class="poster-container-mobile">
            <n-image
              v-if="item.poster_path"
              :src="getImg(item.poster_path)"
              fallback-src="https://via.placeholder.com/150x225?text=No+Poster"
              object-fit="cover"
              preview-disabled
              style="width: 100%; height: 100%;"
            />
            <div v-else class="no-poster-mobile">暂无海报</div>
            <div :class="['type-tag-mobile', item.type === 'movie' ? 'tag-movie' : 'tag-tv']">
              {{ item.type === 'movie' ? '电影' : '剧集' }}
            </div>
            <div class="year-tag-mobile" v-if="item.year">{{ item.year }}</div>
          </div>
          <div class="card-content-mobile">
            <div class="card-title-mobile">{{ item.title }}</div>
            <div class="card-id-mobile">ID: {{ item.id }}</div>
          </div>
          <n-button 
            class="card-delete-mobile" 
            text 
            type="error" 
            size="tiny" 
            @click.stop="deleteCache(item)"
          >
            <template #icon><n-icon><DeleteIcon /></n-icon></template>
          </n-button>
        </div>
      </div>
      <div v-else-if="!loading" class="m-empty" style="padding: var(--m-spacing-3xl) 0;">
        <div class="m-empty-title">暂无缓存记录</div>
      </div>

      <!-- Loading Sentinel -->
      <div ref="sentinel" class="sentinel-mobile">
        <n-spin v-if="loading && data.length > 0" size="small" />
        <div v-if="!hasMore && data.length > 0" class="end-text-mobile">没有更多了</div>
      </div>
    </div>

    <!-- Edit/Add Cache Modal -->
    <AppGlassModal 
      v-model:show="showEditModal" 
      style="width: 92%; max-width: 480px; max-height: 90vh" 
      :title="isEditing ? '编辑缓存记录' : '新增缓存记录'"
      :segmented="{ content: true, action: true }"
    >
      <div style="overflow-y: auto; max-height: calc(90vh - 120px); padding-right: 4px;">
        <n-form label-placement="top">
          <n-form-item>
            <AppTextField v-model:value="editForm.id" label="TMDB ID" :disabled="isEditing" placeholder="数字 ID" />
          </n-form-item>
          <n-form-item>
            <AppSelectField v-model:value="editForm.type" label="媒体类型" :options="[{label:'剧集', value:'tv'}, {label:'电影', value:'movie'}]" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.title" label="中文标题" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.original_title" label="原始标题" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.category" label="分类名称" placeholder="电影 / 剧集" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.year" label="发行年份" placeholder="YYYY" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.release_date" label="播出日期" placeholder="YYYY-MM-DD" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.poster_path" label="海报链接" />
          </n-form-item>
          <n-form-item>
            <AppTextField v-model:value="editForm.overview" label="内容简介" type="textarea" :autosize="{minRows:3, maxRows: 6}" />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <n-space justify="end" style="width: 100%;">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" @click="saveCache">保存记录</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.cache-toolbar {
  display: flex;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-lg);
  padding-bottom: var(--m-spacing-md);
}

.cache-toolbar .n-input {
  flex: 1;
}

.cache-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-spacing-md);
  padding: 0 var(--m-spacing-lg) var(--m-spacing-lg);
}

.cache-actions .n-button:first-child {
  grid-column: 1 / -1;
}

.cache-grid-mobile {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-spacing-md);
  padding: 0 var(--m-spacing-lg) var(--m-spacing-lg);
}

.cache-card-mobile {
  position: relative;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-md);
  overflow: hidden;
  cursor: pointer;
}

.poster-container-mobile {
  position: relative;
  width: 100%;
  aspect-ratio: 2/3;
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.no-poster-mobile {
  color: var(--text-muted);
  font-size: var(--m-text-xs);
  text-align: center;
  padding: var(--m-spacing-md);
}

.type-tag-mobile {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 10;
  padding: 2px 5px;
  font-size: 10px;
  font-weight: bold;
  color: var(--text-primary);
  border-bottom-left-radius: var(--m-radius-sm);
}

.tag-movie { background: var(--color-warning); }
.tag-tv { background: var(--color-success); }

.year-tag-mobile {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
  padding: 2px 5px;
  font-size: 10px;
  font-weight: bold;
  color: var(--text-primary);
  background: var(--bg-surface-active);
  border-bottom-right-radius: var(--m-radius-sm);
}

.card-content-mobile {
  padding: var(--m-spacing-sm);
}

.card-title-mobile {
  font-size: var(--m-text-sm);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-id-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  margin-top: var(--m-spacing-xs);
}

.card-delete-mobile {
  position: absolute;
  bottom: 4px;
  right: 4px;
  z-index: 20;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sentinel-mobile {
  height: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: var(--m-spacing-md);
  width: 100%;
}

.end-text-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-muted);
  font-style: italic;
}
</style>
