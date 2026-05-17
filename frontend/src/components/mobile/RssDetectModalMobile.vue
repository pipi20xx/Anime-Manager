<script setup lang="ts">
import { 
  NModal, NButton, NSpace, NSelect, NInput, NInputNumber,
  NSpin, NEmpty, NTag, NDivider, NRadioGroup, NRadio,
  NPopconfirm, NSwitch, NAlert
} from 'naive-ui'
import { useRssDetect } from '../../composables/components/useRssDetect'

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
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="v => emit('update:show', v)"
    preset="card"
    style="width: 95vw; max-width: 500px;"
    :style="{ maxHeight: '90vh' }"
  >
    <template #header>
      <span style="font-weight: bold;">RSS 探测订阅</span>
    </template>

    <n-scrollbar style="max-height: 70vh;">
      <n-space vertical size="medium">

        <n-input-group>
          <n-input 
            v-model:value="rssUrl" 
            placeholder="输入 RSS 链接" 
            @keypress.enter="handlePreview"
          />
          <n-button type="primary" :loading="detecting" @click="handlePreview">
            探测
          </n-button>
        </n-input-group>

        <div class="label">预设选项</div>
        <n-radio-group v-model:value="mode">
          <n-space vertical>
            <n-radio value="template">使用订阅预设</n-radio>
            <n-radio value="custom">自定义筛选</n-radio>
          </n-space>
        </n-radio-group>

        <n-select 
          v-if="mode === 'template'"
          v-model:value="selectedTemplate" 
          :options="templates.map(t => ({label: t.name + (t.is_default ? ' (默认)' : ''), value: t.id}))" 
          placeholder="选择订阅预设"
        />

        <template v-if="mode === 'custom'">
          <n-input v-model:value="filterRes" placeholder="分辨率 (如: 1080p)" />
          <n-input v-model:value="filterTeam" placeholder="制作组/字幕组" />
          <n-input v-model:value="filterSource" placeholder="来源" />
          <n-input v-model:value="filterCodec" placeholder="编码" />
          <n-input v-model:value="filterSub" placeholder="字幕语言" />
        </template>

        <n-divider style="margin: 12px 0;" />

        <n-select 
          v-model:value="targetClientId" 
          :options="clients.map(c => ({label: c.name, value: c.id}))" 
          placeholder="下载客户端"
          clearable
        />
        
        <n-space align="center">
          <n-switch v-model:value="saveAsTask" size="small" />
          <span style="font-size: 13px;">保存为定时任务</span>
        </n-space>

        <template v-if="saveAsTask">
          <n-input v-model:value="taskName" placeholder="任务名称（可选）" />
          <div class="label">执行间隔: {{ intervalMinutes }} 分钟</div>
          <n-slider v-model:value="intervalMinutes" :min="30" :max="1440" :step="30" />
        </template>

        <template v-if="previewResult && !subscribeResult">
          <n-divider style="margin: 12px 0;" />
          <div class="label">探测结果</div>
          
          <n-spin :show="detecting">
            <n-empty v-if="!previewResult.detected_shows?.length" description="未识别到番剧" />
            
            <div v-else>
              <n-alert type="success" style="margin-bottom: 10px;">
                识别到 {{ previewResult.detected_shows.length }} 个番剧
              </n-alert>
              
              <div v-for="show in previewResult.detected_shows" :key="show.tmdb_id" class="mobile-show-item">
                <div class="show-info">
                  <div class="show-title">{{ show.title }}</div>
                  <n-tag :type="show.is_subscribed ? 'warning' : 'success'" size="small">
                    {{ show.is_subscribed ? '已订阅' : '新发现' }}
                  </n-tag>
                </div>
                <div class="show-meta">
                  S{{ show.season }} · {{ show.entry_count }} 条目
                </div>
              </div>
            </div>
          </n-spin>
        </template>

        <template v-if="subscribeResult">
          <n-divider style="margin: 12px 0;" />
          <n-alert :type="subscribeResult.created > 0 ? 'success' : 'info'">
            新增 {{ subscribeResult.created }} 订阅，跳过 {{ subscribeResult.skipped }}
          </n-alert>
        </template>

      </n-space>
    </n-scrollbar>

    <template #footer>
      <n-button block type="primary" 
        :loading="subscribing" 
        :disabled="!rssUrl.trim()"
        @click="handleSubscribe"
      >
        保存配置
      </n-button>
    </template>
  </n-modal>
</template>

<style scoped>
.label { font-size: 12px; margin-bottom: 6px; font-weight: bold; color: var(--text-secondary); }
.mobile-show-item {
  padding: 10px;
  background: var(--app-surface-inner);
  border-radius: 8px;
  margin-bottom: 8px;
}
.show-info { display: flex; justify-content: space-between; align-items: center; }
.show-title { font-size: 14px; font-weight: bold; }
.show-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }

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
