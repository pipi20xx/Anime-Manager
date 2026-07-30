<script setup lang="ts">
/**
 * SubscriptionTemplateModal — 订阅预设模板管理弹窗
 *
 * 对标旧前端 SubscriptionTemplateModalDesktop:
 * - 模板列表 (表格) + 默认星标
 * - 新建/编辑模板 (筛选条件 + 下载设置 + 监控源)
 */
import { ref, reactive, watch } from 'vue'
import { subscriptionApi, clientsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void }>()

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()

const templates = ref<any[]>([])
const clients = ref<any[]>([])
const feeds = ref<any[]>([])
const loading = ref(false)
const showEdit = ref(false)
const isNew = ref(false)

const editModel = reactive({
  id: null as number | null,
  name: '',
  is_default: false,
  filter_res: '', filter_team: '', filter_source: '', filter_codec: '',
  filter_audio: '', filter_sub: '', filter_effect: '', filter_platform: '',
  include_keywords: '', exclude_keywords: '',
  target_client_id: null as number | null,
  save_path: '', category: 'Anime',
  target_feeds: [] as string[],
  auto_fill: true,
})

watch(() => props.show, (val) => {
  if (val) { fetchTemplates(); fetchClients(); fetchFeeds() }
  else showEdit.value = false
})

async function fetchTemplates() {
  loading.value = true
  try { templates.value = (await subscriptionApi.getTemplates()) || [] }
  catch { showError('加载模板失败') }
  finally { loading.value = false }
}

async function fetchClients() {
  try { clients.value = (await clientsApi.getClients()) || [] } catch { /* */ }
}

async function fetchFeeds() {
  try { feeds.value = (await subscriptionApi.getFeeds()) || [] } catch { /* */ }
}

function openAdd() {
  isNew.value = true
  Object.assign(editModel, {
    id: null, name: '', is_default: templates.value.length === 0,
    filter_res: '', filter_team: '', filter_source: '', filter_codec: '',
    filter_audio: '', filter_sub: '', filter_effect: '', filter_platform: '',
    include_keywords: '', exclude_keywords: '',
    target_client_id: clients.value.length > 0 ? clients.value[0].id : null,
    save_path: '', category: 'Anime', target_feeds: [], auto_fill: true,
  })
  showEdit.value = true
}

function openEdit(row: any) {
  isNew.value = false
  Object.assign(editModel, { ...row })
  if (typeof (editModel as any).target_feeds === 'string' && (editModel as any).target_feeds) {
    editModel.target_feeds = ((editModel as any).target_feeds as string).split(',').filter(Boolean)
  } else if (!Array.isArray(editModel.target_feeds)) {
    editModel.target_feeds = []
  }
  showEdit.value = true
}

async function saveTemplate() {
  if (!editModel.name) { warning('预设名称不能为空'); return }
  try {
    const payload = { ...editModel } as any
    if (Array.isArray(payload.target_feeds)) {
      payload.target_feeds = payload.target_feeds.join(',')
    }
    await subscriptionApi.saveTemplate(payload)
    success('保存成功')
    showEdit.value = false
    fetchTemplates()
  } catch { showError('保存失败') }
}

async function deleteTemplate(row: any) {
  const ok = await confirm({ title: '确认删除', content: `确定删除模板「${row.name}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try { await subscriptionApi.deleteTemplate(row.id); success('已删除'); fetchTemplates() }
  catch { showError('删除失败') }
}

async function setDefault(row: any) {
  try {
    await subscriptionApi.saveTemplate({ ...row, is_default: true })
    success('已设为默认')
    fetchTemplates()
  } catch { showError('设置失败') }
}
</script>

<template>
  <v-dialog :model-value="show" max-width="850" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-file-document-outline</v-icon>
        {{ showEdit ? (editModel.id ? '编辑订阅预设' : '新增订阅预设') : '订阅预设模板管理' }}
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 列表视图 -->
        <template v-if="!showEdit">
          <div class="d-flex justify-space-between align-center mb-4">
            <div class="text-body-2 text-medium-emphasis">点击星标可将模板设为一键订阅时的默认配置</div>
            <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAdd">创建新预设</v-btn>
          </div>

          <v-skeleton-loader v-if="loading" type="card@3" />

          <v-row v-else-if="templates.length > 0" dense>
            <v-col v-for="row in templates" :key="row.id" cols="12" sm="6">
              <v-card variant="outlined" class="rounded-xl h-100 d-flex flex-column">
                <v-card-item class="pb-2">
                  <div class="d-flex align-center ga-2">
                    <v-btn
                      :icon="row.is_default ? 'mdi-star' : 'mdi-star-outline'"
                      size="small" variant="text"
                      :color="row.is_default ? 'warning' : 'grey'"
                      density="comfortable"
                      @click="!row.is_default && setDefault(row)"
                    />
                    <v-card-title class="text-subtitle-1 font-weight-bold pa-0 flex-grow-1">{{ row.name }}</v-card-title>
                  </div>
                </v-card-item>
                <v-card-text class="pt-0 flex-grow-1">
                  <div class="d-flex flex-wrap ga-2 mb-2">
                    <v-chip v-if="row.category" size="x-small" variant="tonal" color="primary" label>{{ row.category }}</v-chip>
                    <v-chip v-if="row.is_default" size="x-small" variant="tonal" color="warning" label>默认</v-chip>
                  </div>
                  <div v-if="row.include_keywords" class="text-body-2 text-medium-emphasis">
                    <v-icon size="14" class="mr-1">mdi-filter-variant</v-icon>{{ row.include_keywords }}
                  </div>
                  <div v-if="row.filter_res || row.filter_team || row.filter_codec" class="text-caption text-medium-emphasis mt-1">
                    <span v-if="row.filter_res">{{ row.filter_res }}</span>
                    <span v-if="row.filter_res && row.filter_team"> · </span>
                    <span v-if="row.filter_team">{{ row.filter_team }}</span>
                    <span v-if="(row.filter_res || row.filter_team) && row.filter_codec"> · </span>
                    <span v-if="row.filter_codec">{{ row.filter_codec }}</span>
                  </div>
                </v-card-text>
                <v-card-actions class="pa-3 pt-0">
                  <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil-outline" @click="openEdit(row)">编辑</v-btn>
                  <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteTemplate(row)">删除</v-btn>
                </v-card-actions>
              </v-card>
            </v-col>
          </v-row>

          <div v-else class="text-center pa-6 text-medium-emphasis">暂无预设模板</div>
        </template>

        <!-- 编辑视图 -->
        <template v-else>
          <v-text-field v-model="editModel.name" label="预设名称" placeholder="例如: 默认动漫预设" variant="outlined" density="compact" class="mb-3" />

          <div class="text-subtitle-2 font-weight-medium mb-2">筛选条件</div>
          <v-row dense>
            <v-col cols="6"><v-text-field v-model="editModel.filter_res" label="分辨率" placeholder="如: 1080P, 4K" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_team" label="制作组" placeholder="如: LoliHouse" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_source" label="介质来源" placeholder="如: Blu-ray, WEB-DL" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_codec" label="视频编码" placeholder="如: H.265, H.264" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_audio" label="音频编码" placeholder="如: FLAC, AAC" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_sub" label="字幕语言" placeholder="如: 简体内封" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_effect" label="视频特效" placeholder="如: HDR10" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="editModel.filter_platform" label="发布平台" placeholder="如: Baha, Netflix" variant="outlined" density="compact" /></v-col>
          </v-row>

          <v-divider class="my-3" />

          <v-row dense>
            <v-col cols="12"><v-text-field v-model="editModel.include_keywords" label="必须包含" placeholder="包含这些关键词才下载" variant="outlined" density="compact" /></v-col>
            <v-col cols="12"><v-text-field v-model="editModel.exclude_keywords" label="排除关键词" placeholder="包含这些关键词则跳过" variant="outlined" density="compact" /></v-col>
          </v-row>

          <v-divider class="my-3" />

          <div class="text-subtitle-2 font-weight-medium mb-2">下载设置</div>
          <v-row dense>
            <v-col cols="12"><v-text-field v-model="editModel.save_path" label="下载目录" placeholder="留空则使用客户端默认路径" variant="outlined" density="compact" /></v-col>
            <v-col cols="6">
              <v-select v-model="editModel.target_client_id" label="下载客户端" :items="clients.map((c: any) => ({ title: c.name, value: c.id }))" clearable variant="outlined" density="compact" />
            </v-col>
            <v-col cols="6"><v-text-field v-model="editModel.category" label="分类/标签" placeholder="例如: Anime" variant="outlined" density="compact" /></v-col>
            <v-col cols="12">
              <v-select v-model="editModel.target_feeds" label="监控订阅源" :items="feeds.map((f: any) => ({ title: f.title || f.url, value: String(f.id) }))" multiple chips clearable variant="outlined" density="compact" placeholder="留空则监控所有" />
            </v-col>
            <v-col cols="6"><v-switch v-model="editModel.auto_fill" color="primary" density="compact" hide-details label="定时补全" /></v-col>
          </v-row>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn v-if="showEdit" variant="tonal" prepend-icon="mdi-arrow-left" @click="showEdit = false">返回列表</v-btn>
        <v-btn v-if="!showEdit" variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
        <v-btn v-if="showEdit" color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveTemplate">保存该预设</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
