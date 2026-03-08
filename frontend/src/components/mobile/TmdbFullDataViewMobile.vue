<script setup lang="ts">
import { h } from 'vue'
import { 
  NSpace, NButton, NIcon, NText, NInput, NInputGroup, 
  NTooltip, NModal, NForm, NFormItem, NSelect, NTag, NGrid, NGi,
  NList, NListItem, NThing, NDropdown, NPopconfirm
} from 'naive-ui'
import {
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  SearchOutlined as SearchIcon,
  RefreshOutlined as SyncIcon,
  FileDownloadOutlined as ExportIcon,
  CloudSyncOutlined as SytmdbIcon,
  CheckCircleOutlined as CustomIcon,
  MoreVertOutlined as MoreIcon,
  ArrowBackOutlined as PrevIcon,
  ArrowForwardOutlined as NextIcon
} from '@vicons/material'
import { useTmdbData } from '../../composables/views/useTmdbData'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { useBackClose } from '../../composables/useBackClose'

const {
  browserData,
  browserTotal,
  browserPage,
  browserSearch,
  browserLoading,
  showEditModal,
  isEditing,
  editForm,
  showSyncModal,
  syncLoading,
  syncForm,
  fetchBrowserData,
  handleBrowserSearch,
  openCreate,
  openEdit,
  saveMetadata,
  deleteMetadata,
  handleSyncSytmdb,
  runSyncSytmdb,
  handleRefreshAll,
  handleExport,
  clearFingerprints
} = useTmdbData()

useBackClose(showEditModal)
useBackClose(showSyncModal)

const menuOptions = [
  { label: '手动新增', key: 'create' },
  { label: '同步 SYTMDB', key: 'sync' },
  { label: '全量刷新', key: 'refresh_all' },
  { label: '导出字典', key: 'export' },
  { label: '清空记忆', key: 'clear_fp' }
]

const handleMenuSelect = (key: string) => {
  if (key === 'create') openCreate()
  else if (key === 'sync') handleSyncSytmdb()
  else if (key === 'refresh_all') handleRefreshAll()
  else if (key === 'export') handleExport()
  else if (key === 'clear_fp') clearFingerprints()
}

const prevPage = () => { if (browserPage.value > 1) { browserPage.value--; fetchBrowserData() } }
const nextPage = () => { if (browserData.value.length === 20) { browserPage.value++; fetchBrowserData() } }
</script>

<template>
  <div class="tmdb-full-view-mobile">
    <div class="mobile-toolbar">
      <n-input-group style="flex: 1;">
        <n-input v-model:value="browserSearch" placeholder="搜索..." @keypress.enter="handleBrowserSearch" size="small" />
        <n-button type="primary" size="small" @click="handleBrowserSearch">
          搜索
        </n-button>
      </n-input-group>
      
      <n-dropdown trigger="click" :options="menuOptions" @select="handleMenuSelect">
        <n-button v-bind="getButtonStyle('icon')" size="small" style="margin-left: 8px;">
          <template #icon><n-icon><MoreIcon /></n-icon></template>
        </n-button>
      </n-dropdown>
    </div>

    <div class="list-container">
      <div v-if="browserData.length > 0" class="metadata-grid">
        <div v-for="item in browserData" :key="item.tmdb_id" class="metadata-card" @click="openEdit(item)">
          <div class="card-main">
            <div class="item-header">
              <span class="item-title">{{ item.title }}</span>
              <n-icon v-if="item.manual" color="var(--n-primary-color)" size="14"><CustomIcon /></n-icon>
            </div>
            <div class="item-meta">
              <span class="meta-tag">{{ item.media_type === 'movie' ? '电影' : '剧集' }}</span>
              <span class="meta-tag" v-if="item.first_air_date">{{ item.first_air_date.slice(0,4) }}</span>
              <span class="meta-id">ID: {{ item.tmdb_id }}</span>
            </div>
            <div class="item-genres">
              <n-tag v-for="g in (item.genres || []).slice(0, 3)" :key="g" size="tiny" type="success" ghost round>{{ g }}</n-tag>
            </div>
          </div>
          <div class="card-actions" @click.stop>
            <n-popconfirm @positive-click="deleteMetadata(item)">
              <template #trigger>
                <n-button v-bind="getButtonStyle('iconDanger')" size="small"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
              </template>
              确认删除?
            </n-popconfirm>
          </div>
        </div>
      </div>
      <div v-if="browserData.length === 0 && !browserLoading" style="padding: 40px; text-align: center; color: var(--text-muted);">暂无数据</div>
    </div>

    <div class="mobile-pagination">
      <n-button v-bind="getButtonStyle('icon')" size="small" :disabled="browserPage <= 1" @click="prevPage"><template #icon><n-icon><PrevIcon/></n-icon></template></n-button>
      <span class="page-info">第 {{ browserPage }} 页</span>
      <n-button v-bind="getButtonStyle('icon')" size="small" :disabled="browserData.length < 20" @click="nextPage"><template #icon><n-icon><NextIcon/></n-icon></template></n-button>
    </div>

    <!-- 编辑/新增元数据弹窗 -->
    <n-modal v-model:show="showEditModal" preset="card" style="width: 100%; height: 100vh; margin: 0;" content-style="padding: 16px; overflow-y: auto;" :title="isEditing ? '修正元数据' : '新增元数据'">
      <n-form label-placement="top">
        <n-form-item label="TMDB ID"><n-input v-model:value="editForm.id" :disabled="isEditing" placeholder="ID" /></n-form-item>
        <n-form-item label="媒体类型"><n-select v-model:value="editForm.type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" /></n-form-item>
        <n-form-item label="显示标题"><n-input v-model:value="editForm.title" /></n-form-item>
        <n-form-item label="海报链接"><n-input v-model:value="editForm.poster_path" /></n-form-item>
        <n-form-item label="内容简介"><n-input v-model:value="editForm.overview" type="textarea" :autosize="{minRows:3}" /></n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end"><n-button v-bind="getButtonStyle('ghost')" @click="showEditModal = false">取消</n-button><n-button v-bind="getButtonStyle('primary')" @click="saveMetadata">保存</n-button></n-space>
      </template>
    </n-modal>

    <!-- SYTMDB 同步弹窗 -->
    <n-modal v-model:show="showSyncModal" preset="card" style="width: 100%; top: 20px;" title="同步 SYTMDB">
      <n-form label-placement="top">
        <n-form-item label="SYTMDB 地址 (IP:Port)"><n-input v-model:value="syncForm.address" placeholder="192.168.1.10:8121" /></n-form-item>
      </n-form>
      <template #footer><n-button type="primary" block :loading="syncLoading" @click="runSyncSytmdb">开始同步</n-button></template>
    </n-modal>
  </div>
</template>

<style scoped>
.tmdb-full-view-mobile { display: flex; flex-direction: column; height: 100%; }
.mobile-toolbar { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid var(--app-border-light); }
.list-container { flex: 1; overflow-y: auto; padding: 12px; box-sizing: border-box; }
.metadata-grid { display: flex; flex-direction: column; gap: 12px; }
.metadata-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-main { flex: 1; min-width: 0; }
.card-actions { margin-left: 12px; flex-shrink: 0; }

.item-header { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.item-title { font-weight: bold; font-size: 15px; color: var(--n-text-color-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-tertiary); margin-bottom: 6px; }
.meta-id { font-family: monospace; color: var(--text-muted); }
.item-genres { display: flex; gap: 4px; flex-wrap: wrap; }
</style>
