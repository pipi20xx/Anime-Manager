<script setup lang="ts">
import { h } from 'vue'
import { 
  NSpace, NButton, NIcon, NText, NDataTable, NInput, NInputGroup, 
  NTooltip, NModal, NForm, NFormItem, NSelect, NTag, NGrid, NGi
} from 'naive-ui'
import {
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  SearchOutlined as SearchIcon,
  FileDownloadOutlined as ExportIcon,
  CloudSyncOutlined as SytmdbIcon,
  CheckCircleOutlined as CustomIcon,
  AddOutlined as AddIcon,
  DeleteSweepOutlined as ClearIcon
} from '@vicons/material'
import { useTmdbData } from '../../composables/views/useTmdbData'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
</script>

<template>
  <div class="tmdb-full-view">
    <n-space vertical size="large">
      <div class="toolbar-row">
        <n-space>
          <n-input-group>
            <n-input v-model:value="browserSearch" placeholder="搜索标题或 TMDB ID..." @keypress.enter="handleBrowserSearch" style="width: 300px" />
            <n-button type="primary" @click="handleBrowserSearch">
              搜索
            </n-button>
          </n-input-group>
        </n-space>
        <n-space>
          <n-button v-bind="getButtonStyle('secondary')" @click="handleExport">
            导出字典
          </n-button>
          <n-button v-bind="getButtonStyle('warning')" @click="handleRefreshAll">
            全量刷新
          </n-button>
          <n-button v-bind="getButtonStyle('warning')" @click="clearFingerprints">
            清空智能记忆
          </n-button>
          <n-button v-bind="getButtonStyle('warning')" @click="handleSyncSytmdb">
            同步 SYTMDB
          </n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="openCreate">
            手动新增
          </n-button>
        </n-space>
      </div>

      <div class="browser-wrapper">
        <n-data-table
          remote
          :loading="browserLoading"
          :columns="[
            { 
              title: '标题', key: 'title', width: 250, fixed: 'left',
              render: (row) => h('span', { style: 'font-weight: bold' }, row.title)
            },
            { title: '类型', key: 'media_type', width: 80, render: (row) => row.media_type === 'movie' ? '电影' : '剧集' },
            { title: '年份', key: 'first_air_date', width: 90, render: (row) => row.first_air_date?.slice(0,4) },
            { 
              title: '流派', key: 'genres', width: 180, 
              render: (row) => h(NSpace, { size: 4 }, () => (row.genres || []).map((g: string) => h(NTag, { size: 'tiny', type: 'success', ghost: true, round: true }, () => g))) 
            },
            { 
              title: '操作', key: 'actions', width: 100, fixed: 'right',
              render: (row) => h(NSpace, null, () => [
                h(NButton, { ...getButtonStyle('icon'), size: 'tiny', onClick: () => openEdit(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
                h(NButton, { ...getButtonStyle('iconDanger'), size: 'tiny', onClick: () => deleteMetadata(row) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
              ])
            }
          ]"
          :data="browserData"
          :pagination="{
            page: browserPage, pageSize: 20, itemCount: browserTotal,
            onChange: (p) => { browserPage = p; fetchBrowserData() }
          }"
          :bordered="false"
          size="small"
        />
      </div>
    </n-space>

    <!-- 编辑/新增元数据弹窗 -->
    <n-modal v-model:show="showEditModal" preset="card" style="width: 700px" :title="isEditing ? '修正元数据' : '手动新增元数据'">
      <n-form label-placement="left" label-width="90">
        <n-grid :cols="2" :x-gap="12">
          <n-gi><n-form-item label="TMDB ID"><n-input v-model:value="editForm.id" :disabled="isEditing" placeholder="请输入 TMDB ID" /></n-form-item></n-gi>
          <n-gi><n-form-item label="媒体类型"><n-select v-model:value="editForm.type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" /></n-form-item></n-gi>
        </n-grid>
        <n-form-item label="显示标题"><n-input v-model:value="editForm.title" placeholder="请输入显示标题" /></n-form-item>
        <n-form-item label="海报链接"><n-input v-model:value="editForm.poster_path" placeholder="请输入海报链接" /></n-form-item>
        <n-form-item label="内容简介"><n-input v-model:value="editForm.overview" placeholder="请输入内容简介" type="textarea" :autosize="{minRows:3}" /></n-form-item>
      </n-form>
      <template #action>
        <n-space justify="end"><n-button v-bind="getButtonStyle('dialogCancel')" @click="showEditModal = false">取消</n-button><n-button v-bind="getButtonStyle('primary')" @click="saveMetadata">保存并固定</n-button></n-space>
      </template>
    </n-modal>

    <!-- SYTMDB 同步弹窗 -->
    <n-modal v-model:show="showSyncModal" preset="card" style="width: 400px" title="同步 SYTMDB 修正数据">
      <n-form label-placement="top">
        <n-form-item label="SYTMDB 地址 (IP:Port)"><n-input v-model:value="syncForm.address" placeholder="192.168.1.10:8121" /></n-form-item>
      </n-form>
      <template #action><n-button type="primary" block :loading="syncLoading" @click="runSyncSytmdb">开始同步</n-button></template>
    </n-modal>
  </div>
</template>

<style scoped>
.toolbar-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.browser-wrapper { background: var(--bg-surface); border-radius: 8px; border: 1px solid var(--app-border-light); padding: 8px; }
</style>
