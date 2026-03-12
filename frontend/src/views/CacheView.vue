<script setup lang="ts">
import { ref, onMounted, reactive, h, onUnmounted, watch } from 'vue'
import { 
  NCard, NDataTable, NSpace, NButton, NIcon, NInput, NTag, NImage,
  useMessage, useDialog, NGrid, NGi, NAvatar, NText, NEllipsis, NModal, 
  NForm, NFormItem, NSelect, NInputNumber, NSpin
} from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  RefreshOutlined as RefreshIcon,
  SearchOutlined as SearchIcon,
  SyncOutlined as SyncIcon,
  EditOutlined as EditIcon,
  AddOutlined as AddIcon
} from '@vicons/material'

import { getButtonStyle } from '../composables/useButtonStyles'

const message = useMessage()
const dialog = useDialog()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const loading = ref(false)
const data = ref<any[]>([])
const searchKeyword = ref('')

// Infinite Scroll State
const page = ref(1)
const pageSize = 24
const hasMore = ref(true)
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

// Search Debounce
let debounceTimer: any = null
watch(searchKeyword, () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchCache(true)
  }, 500)
})

// Edit / Add Modal State
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
    
    // Check if we reached the end (if returned items < pageSize, we are done)
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
  // 如果已经是本地代理路径，直接返回
  if (path.includes('/api/system/img')) return path
  
  // 如果是 TMDB 的远程路径，提取文件部分并转为本地代理
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    const filename = parts[parts.length - 1]
    return `${API_BASE}/api/system/img?path=/${filename}`
  }
  
  // 处理相对路径
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
    // 后端接口要求 key 为 type:id 格式
    const key = `${editForm.type}:${editForm.id}`
    const res = await fetch(`${API_BASE}/api/cache`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm)
    })
    if (res.ok) {
      message.success('保存成功')
      showEditModal.value = false
      fetchCache(true) // Refresh list
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

// SYTMDB Sync Modal
const showSyncModal = ref(false)
const syncLoading = ref(false)
const syncForm = reactive({ address: '' })

const handleSyncSytmdb = async () => {
  if (!syncForm.address) return
  syncLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/cache/sytmdb_sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(syncForm)
    })
    const result = await res.json()
    message.success(`同步完成: ${result.message}`)
    showSyncModal.value = false
    fetchCache(true)
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
          fetchStats()
          dialog.destroyAll()
        } finally {
          loading.value = false
        }
      } }, { default: () => '清空记忆' })
    ])
  })
}

onMounted(() => {
  fetchCache(true)
  
  // Setup Intersection Observer for infinite scroll
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && !loading.value && hasMore.value) {
      fetchCache(false)
    }
  }, { rootMargin: '200px' })
  
  // Wait for DOM
  setTimeout(() => {
    if (sentinel.value) observer?.observe(sentinel.value)
  }, 500)
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="cache-view">
    <div class="page-header">
      <div>
        <h1>本地缓存</h1>
        <div class="subtitle">本地元数据缓存管理</div>
      </div>
      <n-space>
        <n-button ghost type="primary" @click="openCreate">
          <template #icon><n-icon><AddIcon /></n-icon></template>手动新增
        </n-button>
        <n-button ghost type="info" @click="showSyncModal = true">
          <template #icon><n-icon><SyncIcon /></n-icon></template>同步 SYTMDB
        </n-button>
      </n-space>
    </div>

    <n-space vertical size="large">
      <div class="toolbar-row">
        <n-space>
          <n-input v-model:value="searchKeyword" placeholder="搜索标题或 TMDB ID..." @keypress.enter="handleSearch" style="width: 300px">
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-button type="primary" @click="handleSearch">搜索</n-button>
        </n-space>
        <n-space>
          <div class="stat-actions">
             <n-button ghost type="warning" @click="clearFingerprints">清空智能记忆</n-button>
          </div>
          <n-button ghost type="error" @click="clearAll">清空全部</n-button>
          <n-button v-bind="getButtonStyle('icon')" @click="handleSearch" :loading="loading">
            <template #icon><n-icon><RefreshIcon /></n-icon></template>
          </n-button>
        </n-space>
      </div>

      <!-- Cache Grid -->
      <div class="cache-grid" v-if="data.length > 0">
        <n-card 
          v-for="item in data" 
          :key="item.type + ':' + item.id" 
          bordered embedded size="small" 
          class="cache-card clickable-card"
          content-style="padding: 0;"
          @click="openEdit(item)"
        >
          <template #cover>
            <div class="poster-container">
              <n-image
                v-if="item.poster_path"
                :src="getImg(item.poster_path)"
                fallback-src="https://via.placeholder.com/150x225?text=No+Poster"
                object-fit="cover"
                class="poster-img"
                preview-disabled
              />
              <div v-else class="no-poster">暂无海报</div>
              <div :class="['type-tag', item.type === 'movie' ? 'tag-movie' : 'tag-tv']">
                {{ item.type === 'movie' ? '电影' : '剧集' }}
              </div>
              <div class="year-tag" v-if="item.year">{{ item.year }}</div>
              <div class="id-tag">{{ item.id }}</div>
            </div>
          </template>
          <div class="card-content">
            <n-text strong class="title">{{ item.title }}</n-text>
            <div class="action-row">
              <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" @click.stop="deleteCache(item)" class="del-btn">
                <template #icon><n-icon><DeleteIcon /></n-icon></template>
              </n-button>
            </div>
          </div>
        </n-card>
      </div>
      <n-empty v-else-if="!loading" description="暂无缓存记录" class="mt-12" />

      <!-- Loading Sentinel -->
      <div ref="sentinel" class="sentinel">
        <n-spin v-if="loading && data.length > 0" size="small" />
        <div v-if="!hasMore && data.length > 0" class="end-text">没有更多了</div>
      </div>
    </n-space>

    <!-- Edit/Add Cache Modal -->
    <n-modal v-model:show="showEditModal" preset="card" style="width: 750px" :title="isEditing ? '编辑缓存记录' : '新增缓存记录'">
      <n-form label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
            <n-form-item label="TMDB ID"><n-input v-model:value="editForm.id" placeholder="数字 ID" :disabled="isEditing" /></n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="媒体类型">
              <n-select v-model:value="editForm.type" :options="[{label:'剧集', value:'tv'}, {label:'电影', value:'movie'}]" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="中文标题"><n-input v-model:value="editForm.title" /></n-form-item>
        <n-form-item label="原始标题"><n-input v-model:value="editForm.original_title" /></n-form-item>
        <n-grid :cols="3" :x-gap="12">
          <n-gi>
            <n-form-item label="分类名称"><n-input v-model:value="editForm.category" placeholder="电影 / 剧集" /></n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="发行年份"><n-input v-model:value="editForm.year" placeholder="YYYY" /></n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="播出日期"><n-input v-model:value="editForm.release_date" placeholder="YYYY-MM-DD" /></n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="海报链接"><n-input v-model:value="editForm.poster_path" /></n-form-item>
        <n-form-item label="内容简介"><n-input v-model:value="editForm.overview" type="textarea" :autosize="{minRows:3}" /></n-form-item>
      </n-form>
      <template #action>
        <n-space justify="end">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" @click="saveCache">保存记录</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- SYTMDB Sync Modal -->
    <n-modal v-model:show="showSyncModal" preset="card" style="width: 450px" title="从 SYTMDB 同步缓存">
      <n-form label-placement="top">
        <n-form-item label="SYTMDB 地址 (IP:Port)">
          <n-input v-model:value="syncForm.address" placeholder="例如 192.168.1.10:8121" />
        </n-form-item>
        <div class="tip">同步将拉取远程 SYTMDB 实例中已修正的元数据并覆盖本地缓存。</div>
      </n-form>
      <template #action>
        <n-space justify="end">
          <n-button @click="showSyncModal = false">取消</n-button>
          <n-button type="primary" :loading="syncLoading" @click="handleSyncSytmdb">开始同步</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }

.toolbar-row { display: flex; justify-content: space-between; align-items: center; }

.cache-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.cache-card { height: 100%; transition: all var(--transition-fast); overflow: hidden; border: 1px solid var(--border-medium); }
.clickable-card { cursor: pointer; }
.cache-card:hover { transform: translateY(-4px); border-color: var(--n-primary-color); box-shadow: var(--shadow-md); }

.poster-container { position: relative; width: 100%; aspect-ratio: 2/3; background: var(--bg-primary); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.poster-img { width: 100%; height: 100%; transition: opacity var(--transition-normal); }
.no-poster { color: var(--text-muted); font-weight: bold; font-size: 14px; }
.type-tag { 
  position: absolute; top: 0; right: 0; z-index: 10; 
  padding: 2px 6px; 
  font-size: 10px; font-weight: bold; color: var(--text-primary); 
  border-bottom-left-radius: var(--button-border-radius, 6px);
  box-shadow: var(--shadow-sm);
}
.tag-movie { background: var(--color-warning); color: var(--text-primary); } /* Yellow/Orange for Movie */
.tag-tv { background: var(--color-success); color: var(--text-primary); }    /* Green/Mint for TV */

.year-tag {
  position: absolute; top: 0; left: 0; z-index: 10;
  padding: 2px 6px; font-size: 10px; font-weight: bold; color: var(--text-primary);
  background: var(--bg-surface-active);
  border-bottom-right-radius: 6px;
  box-shadow: var(--shadow-sm);
}
.id-tag {
  position: absolute; bottom: 0; right: 0; z-index: 10;
  padding: 2px 6px; font-size: 10px; font-weight: bold; color: var(--text-primary);
  background: var(--bg-surface-active);
  border-top-left-radius: 6px;
  box-shadow: var(--shadow-sm);
}

.card-content { padding: 10px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.card-content .title { font-size: 13px; font-weight: bold; color: var(--text-secondary); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; flex-grow: 1; }
.action-row { display: flex; align-items: flex-start; flex-shrink: 0; }
.del-btn { opacity: 0.2; transition: opacity var(--transition-fast); }
.cache-card:hover .del-btn { opacity: 1; }

.sentinel { height: 40px; display: flex; justify-content: center; align-items: center; margin-top: 24px; width: 100%; }
.end-text { font-size: 12px; color: var(--text-muted); font-style: italic; }

.tip { font-size: 12px; color: var(--text-muted); font-style: italic; }
.mt-12 { margin-top: 48px; }
</style>