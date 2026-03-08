<script setup lang="ts">
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NAlert, NSelect, 
  NInput, NRadioGroup, NRadioButton, NGrid, NGi, NInputNumber, 
  NScrollbar, NList, NListItem, NAvatar, NButton, NIcon, NCheckbox, NDynamicTags
} from 'naive-ui'
import {
  SearchOutlined as SearchIcon,
  PlayArrowOutlined as PlayIcon,
  TuneOutlined as TuneIcon
} from '@vicons/material'
import { useManualOrganizeModal } from '../../composables/components/useManualOrganizeModal'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  currentPath: string
  availableRules: any[]
  apiBase: string
  defaultTask: any
}>()

const emit = defineEmits(['update:show', 'run', 'run-background'])

const {
  manualTask,
  manualSearch,
  getImg,
  searchTmdb,
  handleConfirm
} = useManualOrganizeModal(props, emit)
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    class="mobile-modal"
    title="手动整理"
  >
    <div class="modal-content">
      <n-alert type="info" :bordered="false" size="small" style="margin-bottom: 12px">
        当前路径: {{ currentPath }}
      </n-alert>

      <n-form label-placement="top" size="small">
        <n-form-item label="整理规则">
          <n-select v-model:value="manualTask.rule_id" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择规则" />
        </n-form-item>

        <n-form-item label="目标目录">
          <n-input v-model:value="manualTask.target_dir" placeholder="例如: /Media" />
        </n-form-item>

        <n-form-item label="操作类型">
          <n-radio-group v-model:value="manualTask.action_type" size="small">
            <n-grid :cols="3" :x-gap="8" :y-gap="8">
              <n-gi><n-radio-button value="move" style="width: 100%; text-align: center">移动</n-radio-button></n-gi>
              <n-gi><n-radio-button value="copy" style="width: 100%; text-align: center">复制</n-radio-button></n-gi>
              <n-gi><n-radio-button value="link" style="width: 100%; text-align: center">硬链</n-radio-button></n-gi>
              <n-gi><n-radio-button value="cd2_move" style="width: 100%; text-align: center">CD2移</n-radio-button></n-gi>
              <n-gi><n-radio-button value="cd2_copy" style="width: 100%; text-align: center">CD2复</n-radio-button></n-gi>
            </n-grid>
          </n-radio-group>
        </n-form-item>

        <!-- 强制参数部分 -->
        <div class="forced-section">
           <div class="section-title"><n-icon><TuneIcon /></n-icon> 强制参数 (可选)</div>
           
           <n-space vertical :size="8">
             <n-input v-model:value="manualTask.forced_tmdb_id" placeholder="TMDB ID" />
             <div class="row-inputs">
                <n-select v-model:value="manualTask.forced_type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" style="width: 100px" />
                <n-input-number v-model:value="manualTask.forced_season" placeholder="季 (S)" :show-button="false" style="flex: 1" />
             </div>
             
             <!-- 搜索栏 -->
             <n-input v-model:value="manualSearch.keyword" placeholder="搜剧名自动填入..." @keypress.enter="searchTmdb">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="searchTmdb" :loading="manualSearch.loading">
                    <template #icon><n-icon><SearchIcon /></n-icon></template>
                  </n-button>
                </template>
             </n-input>
             
             <!-- 搜索结果 -->
             <n-scrollbar v-if="manualSearch.results.length > 0" style="max-height: 120px" class="search-res-list">
                <n-list hoverable clickable>
                  <n-list-item v-for="res in manualSearch.results" :key="res.id" @click="manualTask.forced_tmdb_id = String(res.id); manualTask.forced_type = res.media_type || manualTask.forced_type; manualSearch.results = []">
                    <template #prefix><n-avatar :src="getImg(res.poster_path)" size="small" /></template>
                    <div style="font-size:11px; line-height: 1.2"><b>{{ res.title }}</b><br>ID: {{ res.id }}</div>
                  </n-list-item>
                </n-list>
             </n-scrollbar>
           </n-space>
        </div>

        <!-- 策略 -->
        <n-collapse arrow-placement="right" style="margin-top: 12px">
           <n-collapse-item title="高级策略与过滤" name="advanced">
              <n-space vertical :size="12">
                 <n-input-number v-model:value="manualTask.process_interval" placeholder="处理间隔 (s)" :min="0" />
                 <n-dynamic-tags v-model:value="manualTask.ignore_file_regex" />
                 <div class="checkbox-grid">
                    <n-checkbox v-model:checked="manualTask.anime_priority">动漫优化</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.overwrite_mode">覆盖模式</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.trigger_strm">联动STRM</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.ignore_history">忽略历史</n-checkbox>
                 </div>
              </n-space>
           </n-collapse-item>
        </n-collapse>

      </n-form>
    </div>

    <template #action>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleConfirm">
          开始
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.mobile-modal {
  width: calc(100vw - 32px) !important;
  max-width: 400px;
  margin-top: 60px;
}

.modal-content {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.forced-section {
  background: var(--app-surface-inner);
  padding: 12px;
  border-radius: 8px;
  margin-top: 12px;
  border: 1px solid var(--app-border-light);
}

.section-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--n-warning-color);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.row-inputs {
  display: flex;
  gap: 8px;
}

.search-res-list {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: 6px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
</style>
