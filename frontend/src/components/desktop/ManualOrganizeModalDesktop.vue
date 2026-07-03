<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import AppSearchField from '../AppSearchField.vue'
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NAlert, NSelect, 
  NInput, NRadioGroup, NRadioButton, NGrid, NGi, 
  NScrollbar, NImage, NButton, NIcon, NCheckbox, 
  NSwitch, NDynamicTags
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
    style="width: 750px" 
    title="手动整理当前目录 (临时任务)"
  >
    <n-form label-placement="left" label-width="100" size="small">
      <n-tabs type="line" animated>
        <!-- 1. 核心配置 -->
        <n-tab-pane name="basic" tab="核心配置">
          <n-space vertical size="large" class="mt-4">
            <n-alert type="info" :bordered="false">整理针对目录: {{ currentPath }}</n-alert>
            
            <n-form-item>
              <AppSelectField v-model:value="manualTask.rule_id" label="整理规则" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择重命名规则" clearable />
            </n-form-item>

            <n-form-item>
              <AppTextField v-model:value="manualTask.target_dir" label="目标目录" placeholder="媒体库绝对路径 (如: /vol1/1000/Media)" />
            </n-form-item>

            <n-form-item>
              <AppSelectField v-model:value="manualTask.action_type" label="操作类型" :options="[
                {label:'物理移动', value:'move'},
                {label:'完整复制', value:'copy'},
                {label:'建立硬链', value:'link'},
                {label:'CD2 移动', value:'cd2_move'},
                {label:'CD2 复制', value:'cd2_copy'},
                {label:'仅记录哈希', value:'hash_only'}
              ]" />
            </n-form-item>

            <div class="forced-box">
              <div class="pl"><n-icon><TuneIcon /></n-icon> 强制元数据 (可选)</div>
              <n-grid :cols="3" :x-gap="12">
                <n-gi><AppTextField v-model:value="manualTask.forced_tmdb_id" label="TMDB ID" placeholder="TMDB ID" /></n-gi>
                <n-gi><AppSelectField v-model:value="manualTask.forced_type" label="类型" :options="[{label:'自动',value:null},{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" placeholder="自动" clearable /></n-gi>
                <n-gi><AppTextField v-model:value="manualTask.forced_season" label="季号" placeholder="自动" type="number" /></n-gi>
              </n-grid>

              <AppSearchField v-model:value="manualSearch.keyword" placeholder="搜索剧名自动填入 ID 和类型..." :loading="manualSearch.loading" @search="searchTmdb" class="mt-2" />
              <n-scrollbar v-if="manualSearch.results.length > 0" class="search-res-list mt-2">
                <div
                  v-for="res in manualSearch.results"
                  :key="res.id"
                  class="search-result-item"
                  @click="manualTask.forced_tmdb_id = String(res.id); manualTask.forced_type = res.media_type || manualTask.forced_type; manualSearch.results = []"
                >
                  <n-image width="50" :src="getImg(res.poster_path)" preview-disabled />
                  <div class="search-result-info">
                      <div class="search-result-title">{{ res.title }} ({{ res.year }})</div>
                      <div class="search-result-sub">ID: {{ res.id }} · {{ res.category }} · {{ res.original_title || '-' }}</div>
                      <div v-if="res.genres?.length" class="search-result-sub">流派：{{ res.genres.join(' / ') }}</div>
                    </div>
                </div>
              </n-scrollbar>
            </div>
          </n-space>
        </n-tab-pane>

        <!-- 2. 过滤规则 -->
        <n-tab-pane name="filters" tab="过滤规则">
          <n-space vertical size="large" class="mt-4">
            <n-form-item>
              <AppTextField v-model:value="manualTask.process_interval" label="处理间隔(s)" type="number" :min="0" />
            </n-form-item>

            <n-form-item label="忽略文件正则">
              <n-dynamic-tags v-model:value="manualTask.ignore_file_regex" placeholder="输入正则后回车" />
            </n-form-item>

            <n-form-item label="忽略目录正则">
              <n-dynamic-tags v-model:value="manualTask.ignore_dir_regex" placeholder="输入正则后回车" />
            </n-form-item>
          </n-space>
        </n-tab-pane>

        <!-- 3. 高级选项 -->
        <n-tab-pane name="advanced" tab="高级选项">
          <n-space vertical size="medium" class="mt-4">
            <div class="switch-row">
              <n-switch v-model:value="manualTask.anime_priority" />
              <span class="switch-row__label">动漫优先</span>
              <span class="switch-row__desc">优先使用动漫专用识别策略，提高动漫识别准确率</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.overwrite_mode" :disabled="manualTask.action_type === 'hash_only'" />
              <span class="switch-row__label">覆盖模式</span>
              <span class="switch-row__desc">目标路径已存在文件时允许覆盖<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.trigger_strm" :disabled="manualTask.action_type === 'hash_only'" />
              <span class="switch-row__label">联动 STRM</span>
              <span class="switch-row__desc">整理完成后自动生成/更新 STRM 文件<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.clean_empty_dir" :disabled="manualTask.action_type === 'hash_only'" />
              <span class="switch-row__label">清理空目录</span>
              <span class="switch-row__desc">整理后删除源目录中的空文件夹<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.ignore_history" />
              <span class="switch-row__label">忽略历史</span>
              <span class="switch-row__desc">跳过已成功整理或已跳过的历史记录，不重新处理</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.retry_failed" />
              <span class="switch-row__label">重试失败项</span>
              <span class="switch-row__desc">重新尝试之前识别失败的文件（TMDB 数据可能已更新）</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.check_emby_exists" :disabled="manualTask.action_type === 'hash_only'" />
              <span class="switch-row__label">Emby 检查</span>
              <span class="switch-row__desc">检测 Emby 库是否存在，存在则跳过处理<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row" style="align-items: flex-start;">
              <n-switch v-model:value="manualTask.calculate_hash" :disabled="manualTask.action_type === 'hash_only'" />
              <n-space vertical :size="4">
                <div class="switch-row">
                  <span class="switch-row__label">哈希计算</span>
                  <span class="switch-row__desc">整理时计算 SHA1 和 ED2K 哈希值并记录<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下强制启用）</span></span>
                </div>
                <div v-if="manualTask.action_type !== 'hash_only'" style="font-size: 11px; color: var(--color-error); padding: 4px 8px; background: var(--color-error-bg); border-radius: 4px;">
                  ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                </div>
              </n-space>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="manualTask.series_fingerprint" />
              <span class="switch-row__label">智能记忆</span>
              <span class="switch-row__desc">自动记住系列特征，后续文件实现秒级识别</span>
            </div>

            <n-alert type="warning" :bordered="false" size="small">
              提示：模拟预览不会修改任何文件。正式执行将按照上述配置物理处理文件。
            </n-alert>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-form>
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleConfirm">
          启动整理任务
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.mt-4 { margin-top: 16px; }
.mt-2 { margin-top: 8px; }
.forced-box {
  background: var(--app-surface-card);
  padding: 16px;
  border-radius: var(--card-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.forced-box .pl { font-size: 12px; font-weight: bold; color: var(--n-warning-color); margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
.search-res-list { 
  background: var(--app-surface-inner); 
  border: 1px solid var(--app-border-light); 
  border-radius: var(--code-radius, 6px); 
}
.search-result-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid var(--app-border-light); transition: background var(--transition-fast); }
.search-result-item:last-child { border-bottom: none; }
.search-result-item:hover { background: var(--app-surface-card); }
.search-result-item :deep(img) { border-radius: var(--button-border-radius, 4px); object-fit: cover; flex-shrink: 0; }
.search-result-info { flex: 1; min-width: 0; }
.search-result-title { font-size: 14px; font-weight: 600; color: var(--text-primary); line-height: 1.4; }
.search-result-sub { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; line-height: 1.4; }

.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-row__label {
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
.switch-row__desc {
  font-size: 12px;
  color: var(--text-tertiary);
}
.inactive-hint {
  color: var(--text-disabled);
  font-style: italic;
}
</style>