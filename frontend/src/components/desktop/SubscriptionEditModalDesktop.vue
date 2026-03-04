<script setup lang="ts">
import { watch } from 'vue'
import { 
  NModal, NCard, NForm, NFormItem, NInput, NSelect, NButton, 
  NSpace, NGrid, NGi, NSwitch, NImage, NInputGroup,
  NInputNumber, NScrollbar, NDivider, NIcon
} from 'naive-ui'
import { SearchOutlined as SearchIcon } from '@vicons/material'
import { useSubscriptionEdit } from '../../composables/modals/useSubscriptionEdit'

const props = defineProps<{
  show: boolean
  subData?: any
  isNew: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])

const {
  loading,
  searchResults,
  searchQuery,
  formModel,
  tmdbSeasons,
  bangumiName,
  templates,
  profiles,
  feeds,
  getImg,
  applyTemplate,
  handleSearch,
  selectResult,
  onSeasonChange,
  handleSave,
  init
} = useSubscriptionEdit(props, emit)

watch(() => props.show, (newVal) => {
  if (newVal) init()
})
</script>

<template>
  <n-modal :show="show" @update:show="v => emit('update:show', v)">
    <n-card
      style="width: 700px"
      :title="isNew ? '新建订阅' : '编辑订阅'"
      bordered
      size="huge"
      role="dialog"
      aria-modal="true"
    >
      <n-form label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="12">
          <n-gi :span="2" v-if="isNew && templates.length > 0">
            <n-form-item label="套用预设">
              <n-select 
                placeholder="快速选择已保存的订阅预设..." 
                :options="templates.map(t => ({label: t.name, value: t.id}))"
                @update:value="applyTemplate"
              />
            </n-form-item>
          </n-gi>
          
          <n-gi :span="2">
             <n-form-item label="优先级策略">
              <n-select 
                v-model:value="formModel.quality_profile_id"
                placeholder="选择洗版/优先级策略 (可选)" 
                :options="profiles.map(p => ({label: p.name, value: p.id}))"
                clearable
              />
            </n-form-item>
             <n-divider style="margin-top: 0" />
          </n-gi>

          <n-gi :span="2">
            <n-form-item label="搜索/选择">
              <n-input-group>
                <n-select 
                  v-model:value="formModel.media_type" 
                  :options="[{label:'剧集', value:'tv'}, {label:'电影', value:'movie'}]" 
                  style="width: 100px"
                />
                <n-input v-model:value="searchQuery" placeholder="输入名称搜索 TMDB..." @keypress.enter="handleSearch" />
                <n-button type="primary" @click="handleSearch" :loading="loading">
                  <template #icon><n-icon :component="SearchIcon" /></template>
                  搜索
                </n-button>
              </n-input-group>
            </n-form-item>
          </n-gi>

          <n-gi :span="2" v-if="searchResults.length > 0">
            <n-scrollbar style="max-height: 300px" class="search-results">
              <div v-for="item in searchResults" :key="item.id" class="result-item" @click="selectResult(item)">
                <n-image width="40" :src="getImg(item.poster_path)" preview-disabled />
                <div class="result-info">
                  <div class="res-title">{{ item.title }} ({{ item.year }})</div>
                  <div class="res-sub">{{ item.original_title }}</div>
                </div>
              </div>
            </n-scrollbar>
          </n-gi>

          <n-gi>
            <n-form-item label="TMDB ID">
              <n-input v-model:value="formModel.tmdb_id" placeholder="手动输入" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="Bangumi ID">
              <n-input v-model:value="formModel.bangumi_id" placeholder="可选: 关联 Bangumi" />
              <template #feedback>
                <div v-if="bangumiName" style="color: var(--n-primary-color); font-size: 12px; font-weight: bold;">
                  📺 {{ bangumiName }}
                </div>
              </template>
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="标题">
              <n-input v-model:value="formModel.title" placeholder="基础名称" />
            </n-form-item>
          </n-gi>

          <n-gi :span="2">
             <div class="poster-preview" v-if="formModel.poster_path">
                <n-image width="100" :src="getImg(formModel.poster_path)" />
                <div style="margin-left: 12px">
                  <div style="font-weight: bold">{{ formModel.title }}</div>
                  <div style="color: #888">Year: {{ formModel.year }} | Type: {{ formModel.media_type }}</div>
                </div>
             </div>
          </n-gi>

          <n-gi><n-form-item label="分辨率"><n-input v-model:value="formModel.filter_res" placeholder="如: 1080P" /></n-form-item></n-gi>
          <n-gi><n-form-item label="制作组"><n-input v-model:value="formModel.filter_team" placeholder="如: LoliHouse" /></n-form-item></n-gi>
          <n-gi><n-form-item label="来源"><n-input v-model:value="formModel.filter_source" placeholder="如: Web-DL" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频编码"><n-input v-model:value="formModel.filter_codec" placeholder="如: HEVC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="音频编码"><n-input v-model:value="formModel.filter_audio" placeholder="如: FLAC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="字幕语言"><n-input v-model:value="formModel.filter_sub" placeholder="如: CHS" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频特效"><n-input v-model:value="formModel.filter_effect" placeholder="如: HDR10" /></n-form-item></n-gi>
          <n-gi><n-form-item label="发布平台"><n-input v-model:value="formModel.filter_platform" placeholder="如: Baha" /></n-form-item></n-gi>
          <n-gi><n-form-item label="下载目录"><n-input v-model:value="formModel.save_path" placeholder="留空默认" /></n-form-item></n-gi>
          <n-gi><n-form-item label="必须包含"><n-input v-model:value="formModel.include_keywords" placeholder="关键词" /></n-form-item></n-gi>
          <n-gi><n-form-item label="排除关键词"><n-input v-model:value="formModel.exclude_keywords" placeholder="排除词" /></n-form-item></n-gi>

          <n-gi>
            <n-form-item label="下载客户端">
              <n-select 
                v-model:value="formModel.target_client_id" 
                :options="clients.map(c => ({label: c.name, value: c.id}))" 
              />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="监控订阅源">
              <n-select 
                v-model:value="formModel.target_feeds" 
                multiple
                placeholder="留空则监控所有"
                :options="feeds.map(f => ({label: f.title || f.url, value: String(f.id)}))"
                :fallback-option="(val) => ({ label: `源ID: ${val}`, value: val })"
              />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="分类/标签">
              <n-input v-model:value="formModel.category" placeholder="分类" />
            </n-form-item>
          </n-gi>

          <n-gi v-if="formModel.media_type === 'tv'">
            <n-form-item label="订阅季度">
              <n-select 
                v-model:value="formModel.season" 
                filterable
                tag
                :options="[{label: '全部季度', value: 0}, ...tmdbSeasons.map(s => ({label: `第 ${s.season_number} 季 (${s.episode_count}集)`, value: s.season_number}))]"
                @update:value="onSeasonChange"
                placeholder="选择季度"
              />
            </n-form-item>
          </n-gi>
          <n-gi v-if="formModel.media_type === 'tv'">
            <n-form-item label="起始集数">
              <n-input-number v-model:value="formModel.start_episode" :min="0" placeholder="0" style="width: 100%" />
            </n-form-item>
          </n-gi>
          <n-gi v-if="formModel.media_type === 'tv'">
            <n-form-item label="结束集数">
              <n-input-number v-model:value="formModel.end_episode" :min="0" placeholder="0" style="width: 100%" />
            </n-form-item>
          </n-gi>

          <n-gi>
            <n-form-item label="启用订阅">
              <n-switch v-model:value="formModel.enabled" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="定时补全">
              <n-switch v-model:value="formModel.auto_fill" />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button @click="emit('update:show', false)">取消</n-button>
          <n-button type="primary" @click="handleSave">保存订阅</n-button>
        </n-space>
      </template>
    </n-card>
  </n-modal>
</template>

<style scoped>
.search-results {
  border: 1px solid var(--app-border-light);
  border-radius: var(--code-radius, 6px);
  margin-bottom: 12px;
  background: var(--app-surface-inner);
}
.result-item {
  display: flex;
  padding: 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--app-border-light);
  transition: background 0.2s;
}
.result-item:hover {
  background: var(--app-surface-card);
}
.result-item :deep(img) {
  border-radius: var(--button-border-radius, 4px);
}
.result-info {
  margin-left: 12px;
}
.res-title {
  font-weight: bold;
  color: var(--n-text-color-1);
}
.res-sub {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.poster-preview {
  display: flex;
  align-items: center;
  background: var(--app-surface-card);
  padding: 12px;
  border-radius: var(--card-border-radius, 12px);
  border: 1px solid var(--app-border-light);
  margin-bottom: 16px;
}
.poster-preview :deep(img) {
  border-radius: var(--button-border-radius, 6px);
}
</style>
