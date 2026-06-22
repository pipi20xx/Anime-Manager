<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import { watch } from 'vue'
import { 
  NModal, NButton, NSpace,
  NSwitch, NPopconfirm, NTag, NEmpty, NAlert,
  NForm, NFormItem, NInput, NSelect,
  NScrollbar
} from 'naive-ui'
import { useRssDetectManager } from '../../composables/components/useRssDetectManager'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show', 'finish'])

const {
  tasks, loading, showEdit, editingTask, testResult, testing,
  templates, clients, editModel,
  openAdd, openEdit, saveTask, deleteTask, runTask, testRss, toggleEnabled, init
} = useRssDetectManager()

watch(() => props.show, (val) => {
  if (val) init()
})

const close = () => {
  showEdit.value = false
  emit('update:show', false)
}
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="close"
    preset="card"
    style="width: 95vw; max-width: 500px;"
    :title="showEdit ? (editingTask ? '编辑任务' : '添加任务') : '自动 RSS 订阅管理'"
  >
    <div v-if="!showEdit">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
        <n-button type="primary" size="small" @click="openAdd">添加任务</n-button>
      </div>

      <div v-for="task in tasks" :key="task.id" class="task-item">
        <div class="task-header">
          <div class="task-name">{{ task.name || task.rss_url.slice(0, 30) }}</div>
          <n-switch :value="task.enabled" size="small" @update:value="() => toggleEnabled(task)" />
        </div>
        <div class="task-meta">
          <n-tag :type="task.enabled ? 'success' : 'default'" size="small">
            {{ task.enabled ? '启用' : '禁用' }}
          </n-tag>
          <span>{{ task.interval_minutes }}分钟</span>
        </div>
        <div class="task-actions">
          <n-button size="tiny" type="primary" @click="runTask(task.id)">执行</n-button>
          <n-button size="tiny" @click="openEdit(task)">编辑</n-button>
          <n-popconfirm @positive-click="deleteTask(task.id)">
            <template #trigger><n-button size="tiny" type="error">删除</n-button></template>
            确定删除？
          </n-popconfirm>
        </div>
      </div>

      <n-empty v-if="!loading && tasks.length === 0" description="暂无探测任务">
        <template #extra>
          <n-button type="primary" @click="openAdd">添加第一个任务</n-button>
        </template>
      </n-empty>
    </div>

    <n-scrollbar v-else style="max-height: 60vh;">
      <n-form label-placement="left" label-width="80">
        <n-space vertical size="medium">

          <n-form-item>
            <AppTextField v-model:value="editModel.rss_url" label="RSS 链接" placeholder="输入 RSS 链接">
              <template #suffix>
                <n-button type="primary" :loading="testing" @click="testRss" style="height: 40px; border-radius: 6px; margin-right: -4px">测试</n-button>
              </template>
            </AppTextField>
          </n-form-item>

          <n-form-item><AppTextField v-model:value="editModel.name" label="任务名称" placeholder="留空自动生成" /></n-form-item>
          
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="label">启用状态</span>
            <n-switch v-model:value="editModel.enabled" />
          </div>

          <AppSelectField 
            v-model:value="editModel.template_id"
            label="预设选项"
            :options="[{label: '自定义筛选', value: null}, ...templates.map(t => ({label: t.name, value: t.id}))]"
            placeholder="选择预设或自定义筛选"
            clearable
          />

          <template v-if="!editModel.template_id">
            <AppTextField v-model:value="editModel.filter_res" label="任务名称" placeholder="分辨率 (如: 1080p, 4k)" />
            <AppTextField v-model:value="editModel.filter_team" label="任务名称" placeholder="制作组 (如: LoliHouse)" />
            <AppTextField v-model:value="editModel.filter_source" label="任务名称" placeholder="来源 (如: Blu-ray, Web-DL)" />
            <AppTextField v-model:value="editModel.filter_codec" label="任务名称" placeholder="视频编码 (如: HEVC, AVC)" />
            <AppTextField v-model:value="editModel.filter_audio" label="任务名称" placeholder="音频编码 (如: FLAC, AAC)" />
            <AppTextField v-model:value="editModel.filter_sub" label="任务名称" placeholder="字幕语言 (如: CHS, CHT)" />
            <AppTextField v-model:value="editModel.filter_effect" label="任务名称" placeholder="视频特效 (如: HDR10, DV)" />
            <AppTextField v-model:value="editModel.filter_platform" label="任务名称" placeholder="发布平台 (如: Baha, Netflix)" />
          </template>

          <AppSelectField 
            v-model:value="editModel.target_client_id" 
            label="下载客户端"
            :options="clients.map(c => ({label: c.name, value: c.id}))" 
            placeholder="下载客户端"
            clearable
          />

          <AppTextField v-model:value="editModel.save_path" label="任务名称" placeholder="下载目录（留空使用默认路径）" />
          <AppTextField v-model:value="editModel.category" label="任务名称" placeholder="分类/标签 (例如: Anime)" />

          <div class="label">执行间隔: {{ editModel.interval_minutes }} 分钟</div>

          <AppTextField v-model:value="editModel.include_keywords" label="任务名称" placeholder="必须包含（包含这些关键词才下载）" />
          <AppTextField v-model:value="editModel.exclude_keywords" label="任务名称" placeholder="排除关键词（包含这些关键词则跳过）" />

          <template v-if="testResult?.detected_shows?.length > 0">
            <n-alert type="success">
              识别到 {{ testResult.detected_shows.length }} 个番剧，其中 {{ testResult.detected_shows.filter((s: any) => !s.is_subscribed).length }} 个可订阅
            </n-alert>
            
            <div v-for="show in testResult.detected_shows" :key="show.tmdb_id" class="mobile-show-item">
              <div class="show-info">
                <div class="show-title">{{ show.title }}</div>
                <n-tag :type="show.is_subscribed ? 'warning' : 'success'" size="small">
                  {{ show.is_subscribed ? '已订阅' : '新发现' }}
                </n-tag>
              </div>
              <div class="show-meta">
                {{ show.total_episodes > 0 ? `S${show.season} E1-${show.total_episodes}` : `S${show.season}` }} · {{ show.entry_count }} 条目
              </div>
            </div>
          </template>

        </n-space>
      </n-form>
    </n-scrollbar>

    <template #action>
      <n-space>
        <n-button v-if="showEdit" block @click="showEdit = false">返回列表</n-button>
        <n-button v-if="!showEdit" block @click="close">关闭</n-button>
        <n-button v-if="showEdit" block type="primary" @click="saveTask">保存任务</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.label { font-size: 12px; margin-bottom: 6px; font-weight: bold; color: var(--text-secondary); }

.task-item {
  padding: 12px;
  background: var(--app-surface-inner);
  border-radius: 10px;
  margin-bottom: 10px;
}
.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.task-name {
  font-size: 14px;
  font-weight: bold;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
.task-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}
.task-actions {
  display: flex;
  gap: 6px;
}

.mobile-show-item {
  padding: 10px;
  background: var(--app-surface-inner);
  border-radius: 8px;
  margin-bottom: 8px;
}
.show-info { display: flex; justify-content: space-between; align-items: center; }
.show-title { font-size: 14px; font-weight: bold; }
.show-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
</style>
