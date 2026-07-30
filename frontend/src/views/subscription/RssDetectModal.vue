<script setup lang="ts">
/**
 * RssDetectModal — 自动 RSS 订阅管理
 *
 * 对标旧前端 RssDetectManagerDesktop：
 * - 任务列表（开关启用/禁用、编辑、删除、执行）
 * - 编辑表单（RSS 链接、任务名称、预设、筛选条件、客户端、关键词等）
 * - 测试 RSS 预览功能
 */
import { ref, reactive, watch } from 'vue'
import { subscriptionApi, clientsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'finish'): void
}>()

const { success, error: showError, warning, info: showInfo } = useNotification()
const { confirm } = useConfirm()

const tasks = ref<any[]>([])
const loading = ref(false)
const showEdit = ref(false)
const isNewTask = ref(false)

const templates = ref<any[]>([])
const clients = ref<any[]>([])

// 测试
const testing = ref(false)
const testResult = ref<any>(null)

const form = reactive({
  id: null as number | null,
  name: '',
  rss_url: '',
  enabled: true,
  template_id: null as number | null,
  filter_res: '',
  filter_team: '',
  filter_source: '',
  filter_codec: '',
  filter_audio: '',
  filter_sub: '',
  filter_effect: '',
  filter_platform: '',
  include_keywords: '',
  exclude_keywords: '',
  target_client_id: null as number | null,
  save_path: '',
  category: 'Anime',
  auto_fill: true,
  interval_minutes: 360,
})

watch(() => props.show, (val) => {
  if (val) {
    fetchTasks()
    fetchTemplates()
    fetchClients()
  } else {
    showEdit.value = false
  }
})

async function fetchTasks() {
  loading.value = true
  try {
    const data = await subscriptionApi.getDetectTasks()
    tasks.value = Array.isArray(data) ? data : (data?.items || data?.data || [])
  } catch { tasks.value = [] }
  finally { loading.value = false }
}

async function fetchTemplates() {
  try {
    const data = await subscriptionApi.getTemplates()
    templates.value = data || []
  } catch { /* */ }
}

async function fetchClients() {
  try {
    const data = await clientsApi.getClients()
    clients.value = data || []
  } catch { /* */ }
}

function openAdd() {
  isNewTask.value = true
  testResult.value = null
  Object.assign(form, {
    id: null, name: '', rss_url: '', enabled: true,
    template_id: templates.value.find((t: any) => t.is_default)?.id || null,
    filter_res: '', filter_team: '', filter_source: '', filter_codec: '',
    filter_audio: '', filter_sub: '', filter_effect: '', filter_platform: '',
    include_keywords: '', exclude_keywords: '',
    target_client_id: clients.value.length > 0 ? clients.value[0].id : null,
    save_path: '', category: 'Anime', auto_fill: true, interval_minutes: 360,
  })
  showEdit.value = true
}

function openEdit(task: any) {
  isNewTask.value = false
  testResult.value = null
  Object.assign(form, { ...task })
  showEdit.value = true
}

async function saveTask() {
  if (!form.rss_url.trim()) { warning('请输入 RSS 链接'); return }
  try {
    const payload = { ...form }
    if (!payload.name) {
      payload.name = `RSS探测-${new Date().toLocaleString()}`
    }
    await subscriptionApi.saveDetectTask(payload)
    success('任务保存成功')
    showEdit.value = false
    fetchTasks()
  } catch { showError('保存失败') }
}

async function deleteTask(taskId: string | number) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此探测任务吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.deleteDetectTask(String(taskId))
    success('已删除')
    fetchTasks()
  } catch { showError('删除失败') }
}

async function runTask(taskId: string | number) {
  try {
    const data: any = await subscriptionApi.runDetectTask(String(taskId))
    if (data?.created > 0) {
      success(`成功创建 ${data.created} 个订阅，跳过 ${data.skipped} 个已存在的`)
    } else {
      showInfo(`未发现新番剧需要订阅，跳过 ${data?.skipped || 0} 个已存在的`)
    }
    fetchTasks()
    emit('finish')
  } catch { showError('执行失败') }
}

async function toggleEnabled(task: any) {
  try {
    await subscriptionApi.saveDetectTask({ ...task, enabled: !task.enabled })
    fetchTasks()
  } catch { /* */ }
}

async function testRss() {
  if (!form.rss_url.trim()) { warning('请输入 RSS 链接'); return }
  testing.value = true
  testResult.value = null
  try {
    const config = {
      rss_url: form.rss_url.trim(),
      template_id: form.template_id,
      filter_res: form.filter_res,
      filter_team: form.filter_team,
      filter_source: form.filter_source,
      filter_codec: form.filter_codec,
      filter_audio: form.filter_audio,
      filter_sub: form.filter_sub,
      filter_effect: form.filter_effect,
      filter_platform: form.filter_platform,
    }
    const data = await subscriptionApi.previewDetect(config)
    testResult.value = data
    if (data?.detected_shows?.length > 0) {
      success(`识别到 ${data.detected_shows.length} 个番剧`)
    } else {
      showInfo('未识别到任何番剧')
    }
  } catch (e: any) { showError('测试失败: ' + (e.message || '未知错误')) }
  finally { testing.value = false }
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '未运行'
  try {
    return new Date(dateStr).toLocaleString()
  } catch { return dateStr }
}
</script>

<template>
  <v-dialog :model-value="show" max-width="1100" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="accent">mdi-radar</v-icon>
        {{ showEdit ? (isNewTask ? '添加探测任务' : '编辑探测任务') : '自动 RSS 订阅管理' }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="$emit('update:show', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 列表视图 -->
        <template v-if="!showEdit">
          <div class="d-flex justify-space-between align-center mb-4">
            <div class="text-body-2 text-medium-emphasis">配置 RSS 探测任务，系统会自动识别新番剧并创建订阅</div>
            <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAdd">添加任务</v-btn>
          </div>

          <v-skeleton-loader v-if="loading" type="card@2" />

          <template v-else-if="tasks.length > 0">
            <v-row dense>
              <v-col v-for="task in tasks" :key="task.id" cols="12" sm="6">
                <v-card variant="outlined" class="rounded-xl h-100 d-flex flex-column">
                  <v-card-item class="pb-2">
                    <div class="d-flex align-center ga-2">
                      <v-switch
                        :model-value="task.enabled"
                        density="compact"
                        hide-details
                        color="primary"
                        @update:model-value="toggleEnabled(task)"
                        @click.stop
                      />
                      <v-card-title class="text-subtitle-1 font-weight-bold pa-0 flex-grow-1 text-truncate">
                        {{ task.name || task.rss_url?.slice(0, 40) }}
                      </v-card-title>
                    </div>
                  </v-card-item>
                  <v-card-text class="pt-0 flex-grow-1">
                    <div class="text-caption text-medium-emphasis text-truncate mb-2">
                      <v-icon size="12" class="mr-1">mdi-rss</v-icon>{{ task.rss_url }}
                    </div>
                    <div class="d-flex flex-wrap ga-2">
                      <v-chip size="x-small" variant="tonal" color="primary" label>
                        <v-icon start size="12">mdi-timer-outline</v-icon>{{ task.interval_minutes }}分钟
                      </v-chip>
                      <v-chip size="x-small" variant="tonal" :color="task.enabled ? 'success' : 'grey'" label>
                        {{ task.enabled ? '已启用' : '已禁用' }}
                      </v-chip>
                      <v-chip size="x-small" variant="tonal" color="info" label>
                        <v-icon start size="12">mdi-clock-outline</v-icon>{{ formatDateTime(task.last_run_at) }}
                      </v-chip>
                    </div>
                  </v-card-text>
                  <v-card-actions class="pa-3 pt-0">
                    <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play" @click="runTask(task.id)">执行</v-btn>
                    <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil-outline" @click="openEdit(task)">编辑</v-btn>
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteTask(task.id)">删除</v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
          </template>

          <div v-else class="text-center pa-8">
            <v-icon size="48" color="accent" class="mb-3">mdi-radar</v-icon>
            <div class="text-body-2 text-medium-emphasis">暂无探测任务</div>
            <v-btn color="primary" variant="tonal" class="mt-3" prepend-icon="mdi-plus" @click="openAdd">添加第一个任务</v-btn>
          </div>
        </template>

        <!-- 编辑视图 -->
        <template v-else>
          <v-row dense>
            <v-col cols="12">
              <v-text-field v-model="form.rss_url" label="RSS 链接" variant="outlined" density="compact" class="mb-2" hide-details>
                <template #append-inner>
                  <v-btn color="primary" :loading="testing" size="small" variant="tonal" prepend-icon="mdi-connection" @click="testRss" class="mr-n2">测试</v-btn>
                </template>
              </v-text-field>
            </v-col>
            <v-col cols="6"><v-text-field v-model="form.name" label="任务名称" variant="outlined" density="compact" placeholder="留空自动生成" /></v-col>
            <v-col cols="6" class="d-flex align-center"><v-switch v-model="form.enabled" label="启用状态" color="primary" density="compact" hide-details /></v-col>
          </v-row>

          <v-divider class="my-3" />

          <v-row dense>
            <v-col cols="12">
              <v-select
                v-model="form.template_id"
                label="预设选项"
                :items="[{ title: '自定义筛选', value: null }, ...templates.map((t: any) => ({ title: t.name, value: t.id }))]"
                clearable
                variant="outlined"
                density="compact"
                placeholder="选择预设或自定义筛选"
              />
            </v-col>
          </v-row>

          <template v-if="!form.template_id">
            <v-row dense>
              <v-col cols="6"><v-text-field v-model="form.filter_res" label="分辨率" variant="outlined" density="compact" placeholder="如: 1080P, 4K" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_team" label="制作组" variant="outlined" density="compact" placeholder="如: LoliHouse, VCB-Studio" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_source" label="介质来源" variant="outlined" density="compact" placeholder="如: Blu-ray, WEB-DL" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_codec" label="视频编码" variant="outlined" density="compact" placeholder="如: H.265, H.264" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_audio" label="音频编码" variant="outlined" density="compact" placeholder="如: FLAC, AAC" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_sub" label="字幕语言" variant="outlined" density="compact" placeholder="如: 简体内封, 繁日内嵌" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_effect" label="视频特效" variant="outlined" density="compact" placeholder="如: HDR10, Dolby Vision" /></v-col>
              <v-col cols="6"><v-text-field v-model="form.filter_platform" label="发布平台" variant="outlined" density="compact" placeholder="如: Baha, Netflix" /></v-col>
            </v-row>
          </template>

          <v-divider class="my-3" />

          <v-row dense>
            <v-col cols="6">
              <v-select
                v-model="form.target_client_id"
                label="下载客户端"
                :items="clients.map((c: any) => ({ title: c.name, value: c.id }))"
                clearable
                variant="outlined"
                density="compact"
                placeholder="默认客户端"
              />
            </v-col>
            <v-col cols="6"><v-text-field v-model="form.save_path" label="下载目录" variant="outlined" density="compact" placeholder="留空则使用客户端默认路径" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.category" label="分类/标签" variant="outlined" density="compact" placeholder="例如: Anime" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.interval_minutes" label="执行间隔（分钟）" type="number" variant="outlined" density="compact" /></v-col>
            <v-col cols="12"><v-text-field v-model="form.include_keywords" label="必须包含" variant="outlined" density="compact" placeholder="包含这些关键词才下载" /></v-col>
            <v-col cols="12"><v-text-field v-model="form.exclude_keywords" label="排除关键词" variant="outlined" density="compact" placeholder="包含这些关键词则跳过" /></v-col>
          </v-row>

          <!-- 测试结果 -->
          <template v-if="testResult && testResult.detected_shows?.length > 0">
            <v-divider class="my-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">
              测试结果 — 识别到 {{ testResult.detected_shows.length }} 个番剧
            </div>
            <v-alert type="success" variant="tonal" density="compact" class="mb-3">
              其中 {{ testResult.detected_shows.filter((s: any) => !s.is_subscribed).length }} 个可订阅
            </v-alert>
            <v-table density="compact" class="rounded-lg">
              <thead>
                <tr>
                  <th>番剧名称</th>
                  <th>TMDB ID</th>
                  <th>季度/集数</th>
                  <th>条目数</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="show in testResult.detected_shows" :key="show.tmdb_id">
                  <td>{{ show.title }}</td>
                  <td>{{ show.tmdb_id }}</td>
                  <td>
                    <span class="text-caption">
                      {{ show.total_episodes > 0 ? `S${show.season} E1-${show.total_episodes}` : `S${show.season}` }}
                    </span>
                  </td>
                  <td>{{ show.entry_count }}</td>
                  <td>
                    <v-chip size="x-small" :color="show.is_subscribed ? 'warning' : 'success'" variant="tonal">
                      {{ show.is_subscribed ? '已订阅' : '新发现' }}
                    </v-chip>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <template v-if="showEdit">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-arrow-left" @click="showEdit = false">返回列表</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveTask">保存任务</v-btn>
        </template>
        <template v-else>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<!-- scoped 样式已迁移至 global.css .config-row -->
