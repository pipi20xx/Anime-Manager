<script setup lang="ts">
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NAlert, NSelect, 
  NInput, NRadioGroup, NRadioButton, NGrid, NGi, NInputNumber, 
  NScrollbar, NList, NListItem, NAvatar, NButton, NIcon, NCheckbox, 
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
            
            <n-form-item label="整理规则">
              <n-select v-model:value="manualTask.rule_id" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择重命名规则" />
            </n-form-item>

            <n-form-item label="目标目录">
              <n-input v-model:value="manualTask.target_dir" placeholder="媒体库绝对路径 (如: /vol1/1000/Media)" />
            </n-form-item>

            <n-form-item label="操作类型">
              <n-radio-group v-model:value="manualTask.action_type">
                <n-radio-button value="move">物理移动</n-radio-button>
                <n-radio-button value="copy">完整复制</n-radio-button>
                <n-radio-button value="link">建立硬链</n-radio-button>
                <n-radio-button value="cd2_move">CD2 移动</n-radio-button>
                <n-radio-button value="cd2_copy">CD2 复制</n-radio-button>
              </n-radio-group>
            </n-form-item>

            <div class="forced-box">
              <div class="pl"><n-icon><TuneIcon /></n-icon> 强制元数据 (可选)</div>
              <n-grid :cols="3" :x-gap="12">
                <n-gi><n-input v-model:value="manualTask.forced_tmdb_id" placeholder="TMDB ID" size="small" /></n-gi>
                <n-gi><n-select v-model:value="manualTask.forced_type" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" size="small" /></n-gi>
                <n-gi><n-input-number v-model:value="manualTask.forced_season" placeholder="季号 (自动)" :show-button="false" size="small" style="width: 100%" /></n-gi>
              </n-grid>

              <n-input v-model:value="manualSearch.keyword" placeholder="搜索剧名自动填入 ID 和类型..." size="small" class="mt-2" @keypress.enter="searchTmdb">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="searchTmdb" :loading="manualSearch.loading">
                    <template #icon><n-icon><SearchIcon /></n-icon></template>
                  </n-button>
                </template>
              </n-input>
              <n-scrollbar v-if="manualSearch.results.length > 0" style="max-height: 120px" class="search-res-list mt-2">
                <n-list hoverable clickable>
                  <n-list-item v-for="res in manualSearch.results" :key="res.id" @click="manualTask.forced_tmdb_id = String(res.id); manualTask.forced_type = res.media_type || manualTask.forced_type; manualSearch.results = []">
                    <template #prefix><n-avatar :src="getImg(res.poster_path)" size="small" /></template>
                    <div style="font-size:12px; color: var(--text-secondary)"><b>{{ res.title }}</b> ({{ res.year }}) - ID: {{ res.id }}</div>
                  </n-list-item>
                </n-list>
              </n-scrollbar>
            </div>
          </n-space>
        </n-tab-pane>

        <!-- 2. 策略与过滤 -->
        <n-tab-pane name="automation" tab="策略与过滤">
          <n-space vertical size="large" class="mt-4">
            <n-grid :cols="2" :x-gap="12">
              <n-gi>
                <n-form-item label="处理间隔(s)">
                  <n-input-number v-model:value="manualTask.process_interval" :min="0" style="width: 100%" />
                </n-form-item>
              </n-gi>
            </n-grid>

            <n-form-item label="忽略文件正则">
              <n-dynamic-tags v-model:value="manualTask.ignore_file_regex" placeholder="输入正则后回车" />
            </n-form-item>

            <n-form-item label="忽略目录正则">
              <n-dynamic-tags v-model:value="manualTask.ignore_dir_regex" placeholder="输入正则后回车" />
            </n-form-item>

            <n-space justify="space-around" class="mt-2">
              <n-checkbox v-model:checked="manualTask.anime_priority">动漫识别优化</n-checkbox>
              <n-checkbox v-model:checked="manualTask.overwrite_mode">覆盖模式</n-checkbox>
              <n-checkbox v-model:checked="manualTask.trigger_strm">联动 STRM</n-checkbox>
              <n-checkbox v-model:checked="manualTask.clean_empty_dir">清理空目录</n-checkbox>
              <n-checkbox v-model:checked="manualTask.ignore_history">忽略历史</n-checkbox>
            </n-space>
            
            <n-form-item label="Emby 检查" class="mt-4">
              <n-space align="center">
                <n-switch v-model:value="manualTask.check_emby_exists" />
                <span style="font-size: 12px; color: var(--text-muted);">检测 Emby 库是否存在，存在则跳过处理</span>
              </n-space>
            </n-form-item>
            
            <n-form-item label="哈希计算" class="mt-2">
              <n-space vertical :size="8">
                <n-space align="center">
                  <n-switch v-model:value="manualTask.calculate_hash" />
                  <span style="font-size: 12px; color: var(--text-muted);">整理时计算 SHA1 和 ED2K 哈希值并记录</span>
                </n-space>
                <div style="font-size: 11px; color: var(--color-error); padding: 4px 8px; background: var(--color-error-bg); border-radius: 4px;">
                  ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                </div>
              </n-space>
            </n-form-item>
            
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
  background: var(--warning-subtle);
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
</style>