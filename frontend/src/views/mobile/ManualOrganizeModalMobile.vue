<script setup lang="ts">
import AppTextField from '../../components/AppTextField.vue'
import AppSelectField from '../../components/AppSelectField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import AppGlassModal from '../../components/AppGlassModal.vue'
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NAlert, NSelect, 
  NInput, NRadioGroup, NRadioButton, NGrid, NGi, 
  NScrollbar, NList, NListItem, NAvatar, NButton, NIcon, NCheckbox, 
  NSwitch, NCollapse, NCollapseItem, NDynamicTags
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
  <AppGlassModal 
    appearance-key="manual-organize-modal"
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    title="手动整理"
  >
    <n-alert type="info" :bordered="false" size="small" style="margin-bottom: 12px">
      当前路径: {{ currentPath }}
    </n-alert>

    <n-form label-placement="top" size="small">
        <n-form-item>
          <AppSelectField v-model:value="manualTask.rule_id" label="整理规则" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择规则" clearable />
        </n-form-item>

        <n-form-item>
          <AppTextField v-model:value="manualTask.target_dir" label="目标目录" placeholder="例如: /Media" />
        </n-form-item>

        <n-form-item>
          <n-radio-group v-model:value="manualTask.action_type" size="small">
            <n-grid :cols="3" :x-gap="8" :y-gap="8">
              <n-gi><n-radio-button value="move" style="width: 100%; text-align: center">移动</n-radio-button></n-gi>
              <n-gi><n-radio-button value="copy" style="width: 100%; text-align: center">复制</n-radio-button></n-gi>
              <n-gi><n-radio-button value="link" style="width: 100%; text-align: center">硬链</n-radio-button></n-gi>
              <n-gi><n-radio-button value="cd2_move" style="width: 100%; text-align: center">CD2移</n-radio-button></n-gi>
              <n-gi><n-radio-button value="cd2_copy" style="width: 100%; text-align: center">CD2复</n-radio-button></n-gi>
              <n-gi><n-radio-button value="hash_only" style="width: 100%; text-align: center">记哈希</n-radio-button></n-gi>
            </n-grid>
          </n-radio-group>
        </n-form-item>

        <!-- 强制参数部分 -->
        <div class="forced-section">
           <div class="section-title"><n-icon><TuneIcon /></n-icon> 强制参数 (可选)</div>
           
           <n-space vertical :size="8">
             <AppTextField v-model:value="manualTask.forced_tmdb_id" label="操作类型" placeholder="TMDB ID" />
             <div class="row-inputs">
                <AppSelectField v-model:value="manualTask.forced_type" label="类型" :options="[{label:'自动',value:null},{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="自动" clearable style="width: 120px" />
                <AppTextField v-model:value="manualTask.forced_season" label="季 (S)" placeholder="季号" type="number" style="flex: 1" />
             </div>
             
             <!-- 搜索栏 -->
             <AppSearchField v-model:value="manualSearch.keyword" placeholder="搜剧名自动填入..." :loading="manualSearch.loading" @search="searchTmdb" />
             
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
                 <AppTextField v-model:value="manualTask.process_interval" label="处理间隔 (s)" type="number" :min="0" />
                 <n-dynamic-tags v-model:value="manualTask.ignore_file_regex" />
                 <div class="checkbox-grid">
                    <n-checkbox v-model:checked="manualTask.anime_priority">动漫优化</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.overwrite_mode" :disabled="manualTask.action_type === 'hash_only'">覆盖模式</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.trigger_strm" :disabled="manualTask.action_type === 'hash_only'">联动STRM</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.clean_empty_dir" :disabled="manualTask.action_type === 'hash_only'">清理空目录</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.ignore_history">忽略历史</n-checkbox>
                    <n-checkbox v-model:checked="manualTask.retry_failed">重试失败</n-checkbox>
                 </div>
                 <div v-if="manualTask.action_type === 'hash_only'" class="inactive-notice">
                    覆盖/联动STRM/清理空目录 在「仅记录哈希」模式下无效
                 </div>
                 
                 <div class="switch-section">
                    <div class="switch-item">
                       <span class="switch-label">Emby 检查</span>
                       <n-switch v-model:value="manualTask.check_emby_exists" size="small" :disabled="manualTask.action_type === 'hash_only'" />
                    </div>
                    <div class="switch-desc">检测 Emby 库是否存在，存在则跳过处理<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（无效）</span></div>
                    
                    <div class="switch-item">
                       <span class="switch-label">哈希计算</span>
                       <n-switch v-model:value="manualTask.calculate_hash" size="small" :disabled="manualTask.action_type === 'hash_only'" />
                    </div>
                    <div class="switch-desc">整理时计算 SHA1 和 ED2K 哈希值并记录<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（强制启用）</span></div>
                    <div v-if="manualTask.action_type !== 'hash_only'" class="switch-warning">⚠️ 需要读取整个文件，云盘环境不建议开启</div>
                 </div>
              </n-space>
           </n-collapse-item>
        </n-collapse>

    </n-form>

    <template #action>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleConfirm">
          开始
        </n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.forced-section {
  background: var(--app-surface-card-mixed);
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
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: 6px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.switch-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border-light);
}

.switch-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.switch-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.switch-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding-left: 4px;
}

.switch-warning {
  font-size: 10px;
  color: var(--color-error);
  padding: 4px 8px;
  background: var(--color-error-bg);
  border-radius: 4px;
  margin-top: 4px;
}

.inactive-notice {
  font-size: 11px;
  color: var(--text-muted);
  padding: 6px 8px;
  background: var(--app-surface-inner);
  border-radius: 4px;
  margin-top: 8px;
}

.inactive-hint {
  color: var(--text-disabled);
  font-style: italic;
}
</style>
