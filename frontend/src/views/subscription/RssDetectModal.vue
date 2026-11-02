<script setup lang="ts">
/**
 * RssDetectModal — 自动 RSS 订阅管理
 *
 * 对标旧前端 RssDetectManagerDesktop：
 * - 任务列表（开关启用/禁用、编辑、删除、执行）
 * - 编辑表单（RSS 链接、任务名称、预设、匹配条件、客户端、关键词等）
 * - 测试 RSS 预览功能
 */
import { ref, reactive, computed, watch } from 'vue'
import { subscriptionApi, clientsApi } from '@/api'
import { api } from '@/api/client'
import { useNotification, useConfirm } from '@/composables'
import { FieldConditionSelect, DialogTitle } from '@/components/common'
import FolderBrowserModal from '@/views/organizer/FolderBrowserModal.vue'

// ---------- 下载目录浏览选择 ----------
const showFolderBrowser = ref(false)
const openFolderBrowser = () => { showFolderBrowser.value = true }
const onFolderSelected = (path: string) => { form.save_path = path }

// 匹配字段: key 为 form 上的 filter_* 属性, field 为规范值选项字段名
const filterFields = [
  { key: 'filter_res', field: 'resolution', label: '分辨率' },
  { key: 'filter_team', field: 'team', label: '制作组' },
  { key: 'filter_source', field: 'source', label: '介质来源' },
  { key: 'filter_codec', field: 'video_encode', label: '视频编码' },
  { key: 'filter_audio', field: 'audio_encode', label: '音频编码' },
  { key: 'filter_sub', field: 'subtitle', label: '字幕语言' },
  { key: 'filter_effect', field: 'video_effect', label: '视频特效' },
  { key: 'filter_platform', field: 'platform', label: '发布平台' },
]

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
const feeds = ref<any[]>([])
const profiles = ref<any[]>([])

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
  quality_profile_id: null as number | null,
  target_client_id: null as number | null,
  save_path: '',
  category: 'Anime',
  target_feeds: [] as string[],
  auto_fill: true,
  interval_minutes: 360,
})

watch(() => props.show, (val) => {
  if (val) {
    fetchTasks()
    fetchTemplates()
    fetchClients()
    fetchFeeds()
    fetchProfiles()
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

async function fetchFeeds() {
  try { feeds.value = (await subscriptionApi.getFeeds()) || [] } catch { /* */ }
}

async function fetchProfiles() {
  try { profiles.value = (await api.get<any[]>('/api/priority/profiles')) || [] } catch { /* */ }
}

// ---------- 订阅预设（仅作为“填充模板”，套用后即与预设脱钩） ----------
const presetItems = computed(() =>
  templates.value.map((t: any) => ({ title: t.name, value: t.id }))
)

/** 最近一次套用的预设名（仅用于界面提示，不参与保存） */
const appliedPresetName = ref('')

/**
 * 套用预设：把预设里的匹配条件 + 关键词 + 洗版策略 + 下载设置整体写入表单，
 * 之后就按表单里的值执行，可任意修改，不再回读预设。
 */
function applyPreset(id: number | null | undefined) {
  if (!id) return
  const t: any = templates.value.find((x: any) => x.id === id)
  if (!t) return
  for (const f of filterFields) (form as any)[f.key] = t[f.key] || ''
  form.include_keywords = t.include_keywords || ''
  form.exclude_keywords = t.exclude_keywords || ''
  form.quality_profile_id = t.quality_profile_id ?? null
  form.target_client_id = t.target_client_id ?? null
  form.save_path = t.save_path || ''
  form.category = t.category || 'Anime'
  form.target_feeds = t.target_feeds ? String(t.target_feeds).split(',').filter(Boolean) : []
  form.auto_fill = t.auto_fill !== false
  appliedPresetName.value = t.name
  success(`已套用预设「${t.name}」，下方参数可继续修改`)
}

function openAdd() {
  isNewTask.value = true
  testResult.value = null
  appliedPresetName.value = ''
  Object.assign(form, {
    id: null, name: '', rss_url: '', enabled: true,
    // 任务不再引用预设：参数全部落在表单里，保存的就是最终生效值
    template_id: null,
    filter_res: '', filter_team: '', filter_source: '', filter_codec: '',
    filter_audio: '', filter_sub: '', filter_effect: '', filter_platform: '',
    include_keywords: '', exclude_keywords: '',
    quality_profile_id: null,
    target_client_id: clients.value.length > 0 ? clients.value[0].id : null,
    save_path: '', category: 'Anime',
    target_feeds: [], auto_fill: true, interval_minutes: 360,
  })
  showEdit.value = true
}

function openEdit(task: any) {
  isNewTask.value = false
  testResult.value = null
  appliedPresetName.value = ''
  Object.assign(form, { ...task })
  // target_feeds 在库里是逗号串，表单里用数组
  form.target_feeds = typeof task?.target_feeds === 'string' && task.target_feeds
    ? task.target_feeds.split(',').filter(Boolean)
    : (Array.isArray(task?.target_feeds) ? task.target_feeds.map(String) : [])
  // 老任务若仍引用预设：把预设内容并入表单（任务自身已填的字段优先），
  // 保存后任务即自带全部参数，不再依赖预设。
  const tid = task?.template_id
  if (tid) {
    const t: any = templates.value.find((x: any) => x.id === tid)
    if (t) {
      for (const f of filterFields) {
        if (!(form as any)[f.key]) (form as any)[f.key] = t[f.key] || ''
      }
      if (!form.include_keywords) form.include_keywords = t.include_keywords || ''
      if (!form.exclude_keywords) form.exclude_keywords = t.exclude_keywords || ''
      if (!form.quality_profile_id) form.quality_profile_id = t.quality_profile_id ?? null
      if (!form.target_client_id) form.target_client_id = t.target_client_id ?? null
      if (!form.save_path) form.save_path = t.save_path || ''
      if (!form.category) form.category = t.category || 'Anime'
      if (!form.target_feeds.length && t.target_feeds) {
        form.target_feeds = String(t.target_feeds).split(',').filter(Boolean)
      }
      appliedPresetName.value = t.name
      form.template_id = null
    }
  }
  showEdit.value = true
}

async function saveTask() {
  if (!form.rss_url.trim()) { warning('请输入 RSS 链接'); return }
  try {
    const payload: any = { ...form }
    if (!payload.name) {
      payload.name = `RSS探测任务-${new Date().toLocaleString()}`
    }
    // 监控订阅源入库为逗号串
    if (Array.isArray(payload.target_feeds)) payload.target_feeds = payload.target_feeds.join(',')
    await subscriptionApi.saveDetectTask(payload)
    success('探测任务已保存')
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
      include_keywords: form.include_keywords,
      exclude_keywords: form.exclude_keywords,
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

const subscribingId = ref<string | null>(null)

/**
 * 从该番剧的预览条目明细中提取出现最多的规格，作为订阅的下载匹配条件。
 * 只提取非空且多数条目一致的值，避免混合规格把下载卡死。
 */
function deriveSpecs(showTmdbId: string): Record<string, string> {
  const fields = ['resolution', 'team', 'source', 'video_encode', 'audio_encode', 'subtitle', 'video_effect', 'platform']
  const entries = (testResult.value?.entries || []).filter(
    (e: any) => e.recognized && String(e.tmdb_id) === String(showTmdbId)
  )
  const out: Record<string, string> = {}
  if (!entries.length) return out
  for (const f of fields) {
    const counts = new Map<string, number>()
    for (const e of entries) {
      const v = e[f]
      if (v) counts.set(v, (counts.get(v) || 0) + 1)
    }
    if (!counts.size) continue
    const [best, n] = [...counts.entries()].sort((a: any, b: any) => b[1] - a[1])[0]
    if (n >= Math.ceil(entries.length / 2)) out[f] = best
  }
  return out
}

async function subscribeShow(show: any) {
  if (show.is_subscribed) return
  subscribingId.value = show.tmdb_id
  try {
    const specs = deriveSpecs(show.tmdb_id)
    // 规格优先取预览条目里实测出现最多的值，缺项回退到表单里当前可见的匹配条件
    const pick = (specKey: string, formKey: string) => specs[specKey] || (form as any)[formKey] || null
    await subscriptionApi.subscribeDetectShow({
      tmdb_id: show.tmdb_id,
      title: show.title,
      media_type: show.media_type || 'tv',
      season: show.season || 1,
      poster_path: show.poster_path || null,
      year: show.year || null,
      filter_res: pick('resolution', 'filter_res'),
      filter_team: pick('team', 'filter_team'),
      filter_source: pick('source', 'filter_source'),
      filter_codec: pick('video_encode', 'filter_codec'),
      filter_audio: pick('audio_encode', 'filter_audio'),
      filter_sub: pick('subtitle', 'filter_sub'),
      filter_effect: pick('video_effect', 'filter_effect'),
      filter_platform: pick('platform', 'filter_platform'),
      target_client_id: form.target_client_id,
      save_path: form.save_path || null,
      category: form.category || 'Anime',
      auto_fill: form.auto_fill,
      target_feeds: form.target_feeds.length ? form.target_feeds.join(',') : null,
      quality_profile_id: form.quality_profile_id,
    })
    show.is_subscribed = true
    success(`已订阅《${show.title}》`)
    emit('finish')
  } catch (e: any) {
    showError('订阅失败: ' + (e.message || '未知错误'))
  } finally {
    subscribingId.value = null
  }
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
      <DialogTitle icon="mdi-radar" icon-color="accent" :title="showEdit ? (isNewTask ? '添加探测任务' : '编辑探测任务') : '自动 RSS 订阅管理'" @close="$emit('update:show', false)" />
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 列表视图 -->
        <template v-if="!showEdit">
          <div class="d-flex justify-space-between align-center mb-4">
            <div class="text-body-2 text-medium-emphasis">配置 RSS 探测任务，系统会自动识别新番剧并创建订阅</div>
            <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-plus" @click="openAdd">添加探测任务</v-btn>
          </div>

          <v-skeleton-loader v-if="loading" type="card@2" />

          <template v-else-if="tasks.length > 0">
            <v-row density="compact">
              <v-col v-for="task in tasks" :key="task.id" cols="12" sm="6">
                <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEdit(task)">
                  <!-- 标题行 -->
                  <div class="manage-card__header">
                    <div class="d-flex align-center ga-2 flex-grow-1 min-width-0">
                      <v-switch
                        :model-value="task.enabled"
                        density="compact"
                        hide-details
                        color="primary"
                        @update:model-value="toggleEnabled(task)"
                        @click.stop
                      />
                      <div class="manage-card__title">{{ task.name || task.rss_url?.slice(0, 40) }}</div>
                    </div>
                    <v-chip size="x-small" variant="tonal" :color="task.enabled ? 'success' : 'grey'" class="manage-card__badge">
                      {{ task.enabled ? '已启用' : '已禁用' }}
                    </v-chip>
                  </div>

                  <!-- 信息区 -->
                  <div class="manage-card__body">
                    <div class="manage-card__info">
                      <span class="manage-card__info-label">地址</span>
                      <span class="manage-card__info-value" :title="task.rss_url">{{ task.rss_url }}</span>
                    </div>
                    <div class="manage-card__tags">
                      <v-chip size="x-small" variant="tonal" color="primary" label>
                        <v-icon start size="12">mdi-timer-outline</v-icon>{{ task.interval_minutes }}分钟
                      </v-chip>
                      <v-chip size="x-small" variant="tonal" color="info" label>
                        <v-icon start size="12">mdi-clock-outline</v-icon>{{ formatDateTime(task.last_run_at) }}
                      </v-chip>
                    </div>
                  </div>

                  <v-divider />
                  <v-card-actions class="manage-card__actions">
                    <v-spacer />
                    <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play" @click.stop="runTask(task.id)">立即执行</v-btn>
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteTask(task.id)">删除</v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
          </template>

          <div v-else class="text-center pa-8">
            <v-icon size="48" color="accent" class="mb-3">mdi-radar</v-icon>
            <div class="text-body-2 text-medium-emphasis">暂无探测任务</div>
            <v-btn color="primary" variant="tonal" class="mt-3" prepend-icon="mdi-plus" @click="openAdd">添加第一个探测任务</v-btn>
          </div>
        </template>

        <!-- 编辑视图 -->
        <template v-else>
          <!-- ① 任务信息 -->
          <div class="text-subtitle-2 font-weight-medium mb-2">任务信息</div>
          <v-row density="compact">
            <v-col cols="12">
              <v-text-field v-model="form.rss_url" label="RSS 链接" variant="outlined" density="compact" class="mb-2" hide-details>
                <template #append-inner>
                  <v-btn color="primary" :loading="testing" size="small" variant="tonal" prepend-icon="mdi-connection" @click="testRss" class="mr-n2">测试</v-btn>
                </template>
              </v-text-field>
            </v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="form.name" label="任务名称" variant="outlined" density="compact" placeholder="留空自动生成" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="form.interval_minutes" label="执行间隔（分钟）" type="number" variant="outlined" density="compact" placeholder="例如 360" /></v-col>
          </v-row>

          <!-- 启用状态开关单独一行 -->
          <div class="d-flex align-center ga-3 py-1">
            <v-switch v-model="form.enabled" label="启用任务" color="primary" density="compact" hide-details />
            <span class="text-caption text-medium-emphasis">{{ form.enabled ? '任务将按执行间隔自动运行' : '任务已暂停，不会自动执行' }}</span>
          </div>

          <v-divider class="my-3" />

          <!-- 套用预设：只做一次性填充，填完可自由修改 -->
          <div class="d-flex align-center ga-2 flex-wrap mb-3">
            <v-select
              :model-value="null"
              label="套用预设"
              :items="presetItems"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 260px"
              placeholder="选择预设，一键填入下方参数"
              @update:model-value="applyPreset"
            />
            <v-chip v-if="appliedPresetName" size="small" variant="tonal" color="accent" label>
              <v-icon start size="14">mdi-check</v-icon>已套用 {{ appliedPresetName }}
            </v-chip>
            <span class="text-caption text-medium-emphasis">
              仅把预设的匹配条件、洗版策略与下载设置填进下面的表单，之后按表单里的值执行，可任意修改；预设本身在「订阅预设管理」中维护。
            </span>
          </div>

          <!-- ② 匹配条件 -->
          <div class="text-subtitle-2 font-weight-medium mb-2">匹配条件</div>
          <v-row density="compact">
            <v-col v-for="f in filterFields" :key="f.key" cols="6">
              <FieldConditionSelect v-model="(form as any)[f.key]" :field="f.field" :label="f.label" />
            </v-col>
          </v-row>

          <v-row density="compact">
            <v-col cols="12"><v-text-field v-model="form.include_keywords" label="必须包含" variant="outlined" density="compact" placeholder="包含这些关键词才下载" /></v-col>
            <v-col cols="12"><v-text-field v-model="form.exclude_keywords" label="排除关键词" variant="outlined" density="compact" placeholder="包含这些关键词则跳过" /></v-col>
          </v-row>

          <v-divider class="my-3" />

          <!-- ③ 下载设置（任务自动创建的订阅会沿用这里的设置） -->
          <div class="text-subtitle-2 font-weight-medium mb-2">下载设置</div>
          <v-row density="compact">
            <v-col cols="6">
              <v-select
                v-model="form.target_client_id"
                label="下载客户端"
                :items="clients.map((c: any) => ({ title: c.name, value: c.id }))"
                clearable
                variant="outlined"
                density="compact"
                placeholder="留空则使用默认客户端"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.save_path"
                label="下载目录"
                variant="outlined"
                density="compact"
                placeholder="留空则使用客户端默认路径"
                append-inner-icon="mdi-folder-open-outline"
                @click:append-inner="openFolderBrowser"
              />
            </v-col>
            <v-col cols="6"><v-text-field v-model="form.category" label="分类/标签" variant="outlined" density="compact" placeholder="例如: Anime" /></v-col>
            <v-col cols="12">
              <v-select
                v-model="form.target_feeds"
                label="监控订阅源"
                :items="feeds.map((f: any) => ({ title: f.title || f.url, value: String(f.id) }))"
                multiple chips clearable
                variant="outlined"
                density="compact"
                placeholder="留空则监控所有"
              />
            </v-col>
            <v-col cols="12"><v-switch v-model="form.auto_fill" color="primary" density="compact" hide-details label="定时补全" /></v-col>
          </v-row>
          <div class="text-caption text-medium-emphasis">任务自动创建的订阅会沿用这里的客户端 / 目录 / 分类 / 监控源与定时补全。</div>

          <v-divider class="my-3" />

          <!-- ④ 洗版设置 -->
          <div class="text-subtitle-2 font-weight-medium mb-2">洗版设置</div>
          <v-row density="compact">
            <v-col cols="12">
              <v-select
                v-model="form.quality_profile_id"
                label="洗版策略"
                :items="profiles.map((p: any) => ({ title: p.name, value: p.id }))"
                clearable
                variant="outlined"
                density="compact"
                placeholder="留空则不洗版"
                :no-data-text="'还没有洗版策略，可在「洗版规则管理」中创建'"
              />
            </v-col>
          </v-row>
          <div class="text-caption text-medium-emphasis">与「洗版规则管理」里的策略联动：决定高分版本是否替换已下载版本。</div>

          <!-- 测试结果 -->
          <template v-if="testResult">
            <v-divider class="my-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">测试结果</div>
            <div class="d-flex flex-wrap ga-2 mb-3">
              <v-chip size="small" variant="tonal" label>总条目 {{ testResult.total_entries ?? 0 }}</v-chip>
              <v-chip size="small" variant="tonal" color="info" label>识别成功 {{ testResult.recognized_count ?? 0 }}</v-chip>
              <v-chip size="small" variant="tonal" color="error" label>识别失败 {{ testResult.failed_count ?? 0 }}</v-chip>
              <v-chip size="small" variant="tonal" color="success" label title="通过当前匹配条件的条目数（含预设）">
                匹配条件通过 {{ testResult.filter_passed_count ?? 0 }}
              </v-chip>
            </div>

            <template v-if="testResult.detected_shows?.length > 0">
              <div class="text-caption text-medium-emphasis mb-1">识别到的番剧（{{ testResult.detected_shows.length }} 个）</div>
              <v-table density="compact" class="rounded-lg">
                <thead>
                  <tr>
                    <th>番剧名称</th>
                    <th>TMDB ID</th>
                    <th>季度/集数</th>
                    <th title="通过匹配条件的条目 / 识别到的条目">命中/条目</th>
                    <th class="text-right">操作</th>
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
                    <td>
                      <span class="text-caption" :class="(show.matched_entry_count ?? 0) > 0 ? 'text-success' : 'text-medium-emphasis'">
                        {{ show.matched_entry_count ?? 0 }} / {{ show.entry_count }}
                      </span>
                    </td>
                    <td class="text-right">
                      <v-btn
                        v-if="!show.is_subscribed"
                        size="x-small"
                        variant="tonal"
                        color="primary"
                        prepend-icon="mdi-plus"
                        :loading="subscribingId === show.tmdb_id"
                        @click="subscribeShow(show)"
                      >订阅</v-btn>
                      <v-chip v-else size="x-small" color="success" variant="tonal">
                        <v-icon start size="12">mdi-check</v-icon>已订阅
                      </v-chip>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </template>

            <template v-if="testResult.entries?.length > 0">
              <div class="text-caption text-medium-emphasis mt-4 mb-1">条目明细</div>
              <div class="rounded-lg" style="max-height: 320px; overflow-y: auto; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity))">
                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>原始标题</th>
                      <th>识别结果</th>
                      <th>规格</th>
                      <th>筛选</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(en, idx) in testResult.entries" :key="idx">
                      <td style="max-width: 380px"><div class="text-truncate" :title="en.title">{{ en.title }}</div></td>
                      <td>
                        <template v-if="en.recognized">
                          <div class="text-truncate" style="max-width: 220px">{{ en.tmdb_title }}</div>
                          <span class="text-caption text-medium-emphasis">S{{ en.season }}{{ en.episode ? ` E${en.episode}` : '' }}</span>
                        </template>
                        <v-chip v-else size="x-small" color="error" variant="tonal">未识别</v-chip>
                      </td>
                      <td>
                        <span class="text-caption">{{ [en.resolution, en.team, en.source].filter(Boolean).join(' · ') || '-' }}</span>
                      </td>
                      <td>
                        <v-chip
                          v-if="en.recognized"
                          size="x-small"
                          variant="tonal"
                          :color="en.filter_passed ? 'success' : 'warning'"
                          :title="en.filter_reason || ''"
                        >{{ en.filter_passed ? '命中' : '被过滤' }}</v-chip>
                        <span v-else class="text-caption text-medium-emphasis">-</span>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </div>
            </template>
          </template>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <template v-if="showEdit">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-arrow-left" @click="showEdit = false">返回列表</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="saveTask">保存探测任务</v-btn>
        </template>
        <template v-else>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 下载目录浏览选择 -->
  <FolderBrowserModal
    v-model="showFolderBrowser"
    via="local"
    title="选择下载目录"
    @select="onFolderSelected"
  />
</template>

<!-- .config-row 定义在 styles/utilities.css -->
