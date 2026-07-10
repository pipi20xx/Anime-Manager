<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NButton, NSpace, NSelect, NInput,
  NSpin, NEmpty, NTag, NDivider, NRadioGroup, NRadio,
  NGrid, NGi, NDataTable, NSwitch, NAlert, useDialog
} from 'naive-ui'
import { h } from 'vue'
import { dataTableThemeOverrides } from '../../store/appearanceStore'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import { useRssDetect } from '../../composables/components/useRssDetect'

const dialog = useDialog()

const props = defineProps<{ show: boolean }>()
const emit = defineEmits(['update:show', 'finish'])

const {
  detecting, subscribing,
  rssUrl, previewResult, subscribeResult,
  mode, selectedTemplate, templates,
  filterRes, filterTeam, filterSource, filterCodec,
  filterAudio, filterSub, filterEffect, filterPlatform,
  includeKeywords, excludeKeywords,
  targetClientId, clients, savePath, category, autoFill,
  saveAsTask, taskName, intervalMinutes,
  tasks,
  handlePreview, handleSubscribe,
  handleRunTask, handleDeleteTask
} = useRssDetect(props, emit)

const createColumns = () => [
  { title: '番剧名称', key: 'title', width: 200 },
  { title: 'TMDB ID', key: 'tmdb_id', width: 100 },
  { title: '类型', key: 'media_type', width: 70 },
  { title: '季数', key: 'season', width: 60 },
  { title: '条目数', key: 'entry_count', width: 70 },
  {
    title: '状态',
    key: 'is_subscribed',
    width: 90,
    render: (row: any) => {
      if (row.is_subscribed) {
        return h(NTag, { type: 'warning', size: 'small' }, { default: () => '已订阅' })
      }
      return h(NTag, { type: 'success', size: 'small' }, { default: () => '新发现' })
    }
  }
]

const createTaskColumns = (runFn: Function, deleteFn: Function) => [
  { 
    title: '任务名', 
    key: 'name',
    ellipsis: { tooltip: true },
    render: (row: any) => row.name || row.rss_url.slice(0, 40)
  },
  { 
    title: 'RSS 链接', 
    key: 'rss_url',
    ellipsis: { tooltip: true }
  },
  { 
    title: '状态', 
    key: 'enabled', 
    width: 70, 
    render: (row: any) => row.enabled ? '启用' : '禁用'
  },
  { 
    title: '间隔', 
    key: 'interval_minutes', 
    width: 80, 
    render: (row: any) => `${row.interval_minutes}分钟`
  },
  { 
    title: '上次运行', 
    key: 'last_run_at', 
    width: 160, 
    render: (row: any) => row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '未运行'
  },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    render: (row: any) => h(NSpace, null, {
      default: () => [
        h(NButton, { size: 'tiny', type: 'primary', onClick: () => runFn(row.id) }, { default: () => '执行' }),
        h(NButton, { 
          size: 'tiny', type: 'error',
          onClick: () => {
            dialog.warning({
              title: '确认删除',
              content: '确定删除此任务吗？',
              positiveText: '确定删除',
              negativeText: '取消',
              onPositiveClick: () => deleteFn(row.id)
            })
          }
        }, { default: () => '删除' })
      ]
    })
  }
]
</script>

<template>
  <AppGlassModal 
    appearance-key="rss-detect-modal"
    :show="show" 
    @update:show="v => emit('update:show', v)"
    style="width: 950px; max-width: 95vw;"
  >
    <template #header>
      <div class="header-box">
        <div>
          <div class="title">RSS 探测自动订阅</div>
          <div class="subtitle">填入 RSS 链接，自动识别番剧并创建订阅</div>
        </div>
      </div>
    </template>

    <n-scrollbar style="max-height: 65vh; padding-right: 10px;">
      <n-space vertical size="medium">

        <n-alert type="info" v-if="tasks.length > 0">
          已有 {{ tasks.length }} 个定时任务，可在下方管理
        </n-alert>

        <AppTextField 
          v-model:value="rssUrl" 
          label="RSS 链接"
          placeholder="请输入 RSS 链接，例如: https://example.com/feed.xml" 
          @keyup.enter="handlePreview"
        >
          <template #suffix>
            <n-button type="primary" :loading="detecting" @click="handlePreview" style="height: 40px; border-radius: 6px; margin-right: -4px">
              探测
            </n-button>
          </template>
        </AppTextField>

        <div class="section-title">预设选项</div>
        <n-radio-group v-model:value="mode">
          <n-space>
            <n-radio value="template">使用订阅预设</n-radio>
            <n-radio value="custom">自定义筛选</n-radio>
          </n-space>
        </n-radio-group>

        <n-grid :cols="mode === 'custom' ? 3 : 1" :x-gap="16" :y-gap="12">
          <n-gi v-if="mode === 'template'">
            <AppSelectField 
              v-model:value="selectedTemplate" 
              label="订阅预设"
              :options="templates.map(t => ({label: t.name + (t.is_default ? ' (默认)' : ''), value: t.id}))" 
              placeholder="选择订阅预设"
              clearable
            />
          </n-gi>

          <template v-if="mode === 'custom'">
            <n-gi>
              <AppTextField v-model:value="filterRes" label="分辨率" placeholder="如: 1080P, 4K" />
            </n-gi>
            <n-gi>
              <AppTextField v-model:value="filterTeam" label="制作组/字幕组" placeholder="如: 某字幕组" />
            </n-gi>
            <n-gi>
              <AppTextField v-model:value="filterSource" label="介质来源" placeholder="如: WEB-DL, Blu-ray" />
            </n-gi>
            <n-gi>
              <AppTextField v-model:value="filterCodec" label="编码" placeholder="如: H.265, H.264" />
            </n-gi>
            <n-gi>
              <AppTextField v-model:value="filterAudio" label="音频" placeholder="如: FLAC, AAC" />
            </n-gi>
            <n-gi>
              <AppTextField v-model:value="filterSub" label="字幕" placeholder="如: 简体内封, 繁日内嵌" />
            </n-gi>
          </template>
        </n-grid>

        <n-divider />

        <n-grid :cols="3" :x-gap="16">
          <n-gi>
            <AppSelectField 
              v-model:value="targetClientId" 
              label="下载客户端"
              :options="clients.map(c => ({label: c.name, value: c.id}))" 
              placeholder="默认客户端"
              clearable
            />
          </n-gi>
          <n-gi>
            <AppTextField v-model:value="savePath" label="保存路径" placeholder="可选，留空使用默认" />
          </n-gi>
          <n-gi>
            <AppTextField v-model:value="category" label="分类" placeholder="默认: Anime" />
          </n-gi>
        </n-grid>

        <n-grid :cols="2" :x-gap="16">
          <n-gi>
            <AppTextField v-model:value="includeKeywords" label="包含关键词" placeholder="可选，逗号分隔" />
          </n-gi>
          <n-gi>
            <AppTextField v-model:value="excludeKeywords" label="排除关键词" placeholder="可选，逗号分隔" />
          </n-gi>
        </n-grid>

        <n-divider />

        <div class="section-title">定时任务（可选）</div>
        <n-space align="center">
          <n-switch v-model:value="saveAsTask" />
          <span>保存为定时任务，自动定期探测</span>
        </n-space>

        <n-grid v-if="saveAsTask" :cols="2" :x-gap="16">
          <n-gi>
            <AppTextField v-model:value="taskName" label="任务名称" placeholder="可选，留空自动生成" />
          </n-gi>
          <n-gi>
            <AppTextField v-model:value="intervalMinutes" label="执行间隔（分钟）" type="number" :min="10" :max="10080" :step="30" />
          </n-gi>
        </n-grid>

        <n-divider v-if="previewResult" />

        <template v-if="previewResult && !subscribeResult">
          <div class="section-title">探测结果</div>
          <n-spin :show="detecting">
            <n-empty v-if="!previewResult.detected_shows || previewResult.detected_shows.length === 0" description="未识别到任何番剧" />
            
            <div v-else>
              <n-alert type="success" style="margin-bottom: 12px;">
                共识别到 {{ previewResult.detected_shows.length }} 个番剧，
                其中 {{ previewResult.detected_shows.filter((s: any) => !s.is_subscribed).length }} 个可订阅
              </n-alert>
              
              <n-data-table
                :theme-overrides="dataTableThemeOverrides"
                :columns="createColumns()"
                :data="previewResult.detected_shows"
                :row-key="(row: any) => row.tmdb_id"
                :pagination="{ pageSize: 8 }"
                size="small"
              />
            </div>
          </n-spin>
        </template>

        <template v-if="subscribeResult">
          <div class="section-title">订阅结果</div>
          <n-alert :type="subscribeResult.created > 0 ? 'success' : 'info'">
            <template #header>执行完成</template>
            新增 {{ subscribeResult.created }} 个订阅 · 跳过 {{ subscribeResult.skipped }} 个已存在
            <span v-if="subscribeResult.task_saved"> · 已保存为定时任务</span>
          </n-alert>
          
          <n-data-table
            :theme-overrides="dataTableThemeOverrides"
            v-if="subscribeResult.shows && subscribeResult.shows.length > 0"
            :columns="createColumns()"
            :data="subscribeResult.shows.map((s: any) => ({
              ...s,
              is_subscribed: s.status !== 'created',
              entry_count: '-'
            }))"
            :row-key="(row: any) => row.tmdb_id"
            size="small"
            style="margin-top: 12px;"
          />
        </template>

        <n-divider v-if="tasks.length > 0" />

        <template v-if="tasks.length > 0">
          <div class="section-title">已有定时任务</div>
          <n-data-table
            :theme-overrides="dataTableThemeOverrides"
            :columns="createTaskColumns(handleRunTask, handleDeleteTask)"
            :data="tasks"
            :row-key="(row: any) => row.id"
            size="small"
          />
        </template>

      </n-space>
    </n-scrollbar>

    <template #action>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">关闭</n-button>
        <n-button 
          type="primary" 
          :loading="subscribing" 
          :disabled="!rssUrl.trim()"
          @click="handleSubscribe"
        >
          保存配置
        </n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.header-box { display: flex; align-items: center; gap: 10px; }
.title { font-size: 18px; font-weight: bold; }
.subtitle { font-size: 12px; color: var(--text-tertiary); }
.section-title { font-size: 14px; font-weight: bold; margin-bottom: 8px; color: var(--text-primary); }
.field-label { font-size: 12px; margin-bottom: 6px; color: var(--text-secondary); }

:deep(.n-radio__dot) {
  transition: all 0.2s;
}
:deep(.n-radio--checked .n-radio__dot .n-radio__dot-border) {
  border-color: var(--n-primary-color);
}
:deep(.n-radio--checked .n-radio__dot .n-radio__dot-box) {
  background-color: var(--n-primary-color);
}
</style>
