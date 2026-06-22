<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import { h, watch } from 'vue'
import { 
  NModal, NDataTable, NButton, NSpace,
  NSwitch, NPopconfirm, NTag, NEmpty, NAlert,
  NForm, NFormItem, NInput, NSelect,
  NGrid, NGi, NDivider
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

const listColumns = [
  { 
    title: '状态', key: 'enabled', width: 70, align: 'center',
    render(row: any) {
      return h(NSwitch, { 
        value: row.enabled, 
        size: 'small',
        onUpdateValue: () => toggleEnabled(row)
      })
    }
  },
  { title: '任务名称', key: 'name', width: 180,
    render(row: any) {
      return row.name || row.rss_url.slice(0, 40)
    }
  },
  { title: 'RSS 链接', key: 'rss_url', ellipsis: { tooltip: true } },
  { 
    title: '间隔', key: 'interval_minutes', width: 90,
    render(row: any) {
      return `${row.interval_minutes}分钟`
    }
  },
  { 
    title: '上次运行', key: 'last_run_at', width: 160,
    render(row: any) {
      return row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '未运行'
    }
  },
  {
    title: '操作', key: 'actions', width: 200,
    render(row: any) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', onClick: () => runTask(row.id) }, { 
            default: () => '执行'
          }),
          h(NButton, { size: 'small', onClick: () => openEdit(row) }, { 
            default: () => '编辑'
          }),
          h(NPopconfirm, { onPositiveClick: () => deleteTask(row.id) }, {
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { 
              default: () => '删除'
            }),
            default: () => '确定删除此任务？'
          })
        ]
      })
    }
  }
]

const testColumns = [
  { title: '番剧名称', key: 'title', width: 200 },
  { title: 'TMDB ID', key: 'tmdb_id', width: 100 },
  { 
    title: '季度/集数', key: 'season', width: 120,
    render(row: any) {
      const epInfo = row.total_episodes > 0 ? `S${row.season} E1-${row.total_episodes}` : `S${row.season}`
      return h('span', { style: 'font-size: 12px;' }, epInfo)
    }
  },
  { title: '条目数', key: 'entry_count', width: 70 },
  {
    title: '状态', key: 'is_subscribed', width: 90,
    render(row: any) {
      if (row.is_subscribed) {
        return h(NTag, { type: 'warning', size: 'small' }, { default: () => '已订阅' })
      }
      return h(NTag, { type: 'success', size: 'small' }, { default: () => '新发现' })
    }
  }
]
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="close"
    preset="card"
    style="width: 1100px; max-width: 98vw;"
    :title="showEdit ? (editingTask ? '编辑探测任务' : '添加探测任务') : '自动 RSS 订阅管理'"
  >
    <div v-if="!showEdit">
      <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
        <div style="color: var(--text-tertiary); font-size: 13px;">
          配置 RSS 探测任务，系统会自动识别新番剧并创建订阅
        </div>
        <n-button type="primary" size="small" @click="openAdd">
          添加任务
        </n-button>
      </div>

      <n-data-table 
        :columns="(listColumns as any)" 
        :data="tasks" 
        :loading="loading"
      />

      <n-empty v-if="!loading && tasks.length === 0" description="暂无探测任务" style="margin-top: 20px;">
        <template #extra>
          <n-button type="primary" @click="openAdd">添加第一个任务</n-button>
        </template>
      </n-empty>
    </div>

    <div v-else class="edit-form">
      <n-form label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16">
          <n-gi :span="2">
            <n-form-item>
              <AppTextField v-model:value="editModel.rss_url" label="RSS 链接" placeholder="请输入 RSS 链接">
                <template #suffix>
                  <n-button type="primary" :loading="testing" @click="testRss" style="height: 40px; border-radius: 6px; margin-right: -4px">测试</n-button>
                </template>
              </AppTextField>
            </n-form-item>
          </n-gi>

          <n-gi><n-form-item><AppTextField v-model:value="editModel.name" label="任务名称" placeholder="留空自动生成" /></n-form-item></n-gi>
          <n-gi><n-form-item label="启用状态"><n-switch v-model:value="editModel.enabled" /></n-form-item></n-gi>

          <n-divider style="grid-column: span 2;" />

          <n-gi :span="2">
            <n-form-item>
              <AppSelectField 
                v-model:value="editModel.template_id" 
                label="预设选项"
                :options="[{label: '自定义筛选', value: null}, ...templates.map(t => ({label: t.name, value: t.id}))]"
                placeholder="选择预设或自定义筛选"
                clearable
              />
            </n-form-item>
          </n-gi>

          <template v-if="!editModel.template_id">
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_res" label="分辨率" placeholder="如: 1080p, 4k" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_team" label="制作组" placeholder="如: LoliHouse, VCB-Studio" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_source" label="来源" placeholder="如: Blu-ray, Web-DL" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_codec" label="视频编码" placeholder="如: HEVC, AVC" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_audio" label="音频编码" placeholder="如: FLAC, AAC" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_sub" label="字幕语言" placeholder="如: CHS, CHT" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_effect" label="视频特效" placeholder="如: HDR10, DV" /></n-form-item></n-gi>
            <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_platform" label="发布平台" placeholder="如: Baha, Netflix" /></n-form-item></n-gi>
          </template>

          <n-divider style="grid-column: span 2;" />

          <n-gi><n-form-item>
            <AppSelectField 
              v-model:value="editModel.target_client_id" 
              label="下载客户端"
              :options="clients.map(c => ({label: c.name, value: c.id}))" 
              placeholder="默认客户端"
              clearable
            />
          </n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.save_path" label="下载目录" placeholder="留空则使用客户端默认路径" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.category" label="分类/标签" placeholder="例如: Anime" /></n-form-item></n-gi>
          <n-gi><n-form-item>
            <AppTextField v-model:value="editModel.interval_minutes" label="执行间隔（分钟）" type="number" :min="10" :max="10080" :step="30" />
          </n-form-item></n-gi>

          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.include_keywords" label="必须包含" placeholder="包含这些关键词才下载" /></n-form-item></n-gi>
          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.exclude_keywords" label="排除关键词" placeholder="包含这些关键词则跳过" /></n-form-item></n-gi>
        </n-grid>
      </n-form>

      <template v-if="testResult && testResult.detected_shows?.length > 0">
        <n-divider>测试结果 - 识别到 {{ testResult.detected_shows.length }} 个番剧</n-divider>
        <n-alert type="success" style="margin-bottom: 12px;">
          其中 {{ testResult.detected_shows.filter((s: any) => !s.is_subscribed).length }} 个可订阅
        </n-alert>
        <n-data-table 
          :columns="(testColumns as any)" 
          :data="testResult.detected_shows"
          :row-key="(row: any) => row.tmdb_id"
          size="small"
        />
      </template>
    </div>

    <template #action>
      <n-space justify="end">
        <n-button v-if="showEdit" @click="showEdit = false">返回列表</n-button>
        <n-button v-if="!showEdit" @click="close">关闭</n-button>
        <n-button v-if="showEdit" type="primary" @click="saveTask">保存任务</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.edit-form { padding-right: 12px; }
</style>
