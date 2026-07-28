<script setup lang="ts">
/**
 * StrmView — STRM 生成器
 *
 * 功能:
 * - 卡片网格展示 STRM 任务（与整理任务卡片样式统一）
 * - 新建/编辑/删除/复制任务
 * - 运行任务
 * - 切换实时监控/定时扫描
 * - 完整编辑表单 Modal（Tab 分页，功能对齐全旧前端）
 */
import { ref, reactive, onMounted } from 'vue'
import { strmApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'StrmView' })

const { success, error: showError, info } = useNotification()
const { confirm } = useConfirm()

const tasks = ref<any[]>([])
const loading = ref(false)

// 编辑 Modal
const showModal = ref(false)
const isNewTask = ref(true)
const editingIndex = ref(-1)
const saving = ref(false)
const activeTab = ref('basic')

// 预览
const previewLoading = ref(false)
const previewData = ref<any>(null)

// 默认扩展名
const DEFAULT_VIDEO_EXTENSIONS = '.mp4,.mkv,.ts,.iso,.rmvb,.avi,.mov,.mpeg,.mpg,.wmv,.3gp,.asf,.m4v,.flv,.m2ts,.tp,.f4v'
const DEFAULT_META_EXTENSIONS = '.nfo,.jpg,.jpeg,.png,.svg,.ass,.srt,.sup,.mp3,.flac,.wav,.aac,.webp,.ssa,.sub'

const taskForm = reactive({
  id: '',
  name: '',
  source_path: '',
  target_path: '',
  content_prefix: '',
  content_suffix: '',
  url_encode: false,
  copy_meta: true,
  clean_target: false,
  clean_empty_dirs: true,
  overwrite_strm: true,
  overwrite_meta: false,
  sync_mode: 'local',
  tree_file_path: '',
  process_interval: 0,
  // 监控
  incremental_enabled: false,
  incremental_mode: 'realtime',
  scheduler_enabled: false,
  scheduler_interval: 3600,
  monitor_interval: 10,
  webhook_enabled: true,
  // 扩展名
  target_extensions: DEFAULT_VIDEO_EXTENSIONS,
  meta_extensions: DEFAULT_META_EXTENSIONS,
})

const SYNC_MODE_OPTIONS = [
  { title: '本地文件扫描', value: 'local' },
  { title: '目录树文件', value: 'tree_file' },
]

const MONITOR_MODE_OPTIONS = [
  { title: '实时 (inotify)', value: 'realtime' },
  { title: '轮询扫描', value: 'polling' },
]

const SYNC_MODE_MAP: Record<string, string> = {
  local: '本地文件扫描',
  tree_file: '目录树文件',
}

async function fetchTasks() {
  loading.value = true
  try {
    const data = await strmApi.getTasks()
    tasks.value = data || []
  } catch (e) {
    showError('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(taskForm, {
    id: '',
    name: '',
    source_path: '',
    target_path: '',
    content_prefix: '',
    content_suffix: '',
    url_encode: false,
    copy_meta: true,
    clean_target: false,
    clean_empty_dirs: true,
    overwrite_strm: true,
    overwrite_meta: false,
    sync_mode: 'local',
    tree_file_path: '',
    process_interval: 0,
    incremental_enabled: false,
    incremental_mode: 'realtime',
    scheduler_enabled: false,
    scheduler_interval: 3600,
    monitor_interval: 10,
    webhook_enabled: true,
    target_extensions: DEFAULT_VIDEO_EXTENSIONS,
    meta_extensions: DEFAULT_META_EXTENSIONS,
  })
  previewData.value = null
  activeTab.value = 'basic'
}

function openNew() {
  resetForm()
  isNewTask.value = true
  editingIndex.value = -1
  taskForm.id = 'strm_' + Date.now()
  taskForm.name = '新 STRM 任务'
  showModal.value = true
}

function openEdit(index: number) {
  resetForm()
  isNewTask.value = false
  editingIndex.value = index
  const rawData = JSON.parse(JSON.stringify(tasks.value[index]))

  // 旧版 monitor_mode 字段迁移
  if (rawData.monitor_mode) {
    if (rawData.monitor_mode === 'realtime') {
      rawData.incremental_enabled = true
      rawData.incremental_mode = 'realtime'
    } else if (rawData.monitor_mode === 'polling') {
      rawData.incremental_enabled = true
      rawData.incremental_mode = 'polling'
    } else if (rawData.monitor_mode === 'scheduled') {
      rawData.scheduler_enabled = true
    }
    delete rawData.monitor_mode
  }

  // 确保默认值
  if (rawData.incremental_enabled === undefined) rawData.incremental_enabled = false
  if (rawData.incremental_mode === undefined) rawData.incremental_mode = 'realtime'
  if (rawData.scheduler_enabled === undefined) rawData.scheduler_enabled = false
  if (rawData.scheduler_interval === undefined) rawData.scheduler_interval = 3600
  if (rawData.monitor_interval === undefined) rawData.monitor_interval = 10
  if (rawData.process_interval === undefined) rawData.process_interval = 0
  if (rawData.webhook_enabled === undefined) rawData.webhook_enabled = true
  if (rawData.tree_file_path === undefined) rawData.tree_file_path = ''

  // 字段名映射
  rawData.source_path = rawData.source_path || rawData.source_dir || ''
  rawData.target_path = rawData.target_path || rawData.target_dir || ''

  // 扩展名处理：数组 → 逗号字符串
  rawData.target_extensions = Array.isArray(rawData.target_extensions)
    ? rawData.target_extensions.join(',')
    : (rawData.target_extensions || DEFAULT_VIDEO_EXTENSIONS)
  rawData.meta_extensions = Array.isArray(rawData.meta_extensions)
    ? rawData.meta_extensions.join(',')
    : (rawData.meta_extensions || DEFAULT_META_EXTENSIONS)

  Object.assign(taskForm, rawData)
  showModal.value = true
  updatePreview()
}

async function handleSave() {
  if (!taskForm.name) {
    showError('请输入任务名称')
    return
  }
  saving.value = true
  try {
    const config = await configApi.getConfig()
    const strmTasks = [...(config.strm_tasks || [])]

    const payload = {
      ...taskForm,
      source_dir: taskForm.source_path,
      target_dir: taskForm.target_path,
      target_extensions: taskForm.target_extensions.split(',').map((s: string) => s.trim()).filter(Boolean),
      meta_extensions: taskForm.meta_extensions.split(',').map((s: string) => s.trim()).filter(Boolean),
    }

    if (isNewTask.value) {
      strmTasks.push(payload)
    } else {
      // 按 id 匹配更新
      const idx = strmTasks.findIndex((t: any) => t.id === taskForm.id)
      if (idx !== -1) {
        strmTasks[idx] = payload
      } else {
        strmTasks[editingIndex.value] = payload
      }
    }

    await configApi.saveConfig({ ...config, strm_tasks: strmTasks })
    success(isNewTask.value ? '任务创建成功' : '任务更新成功')
    showModal.value = false
    fetchTasks()
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(index: number) {
  const task = tasks.value[index]
  const ok = await confirm({
    title: '确认删除任务',
    content: `确定要删除任务「${task.name}」吗？此操作不可撤销。`,
    confirmColor: 'error',
  })
  if (!ok) return

  try {
    const config = await configApi.getConfig()
    const strmTasks = (config.strm_tasks || []).filter((_: any, i: number) => i !== index)
    await configApi.saveConfig({ ...config, strm_tasks: strmTasks })
    success('任务已删除')
    fetchTasks()
  } catch (e) {
    showError('删除失败')
  }
}

async function handleDuplicate(index: number) {
  try {
    const config = await configApi.getConfig()
    const strmTasks = [...(config.strm_tasks || [])]
    const copy = { ...strmTasks[index], id: 'strm_' + Date.now(), name: strmTasks[index].name + ' (副本)' }
    strmTasks.splice(index + 1, 0, copy)
    await configApi.saveConfig({ ...config, strm_tasks: strmTasks })
    success('任务已复制')
    fetchTasks()
  } catch (e) {
    showError('复制失败')
  }
}

async function handleRun(taskId: string) {
  try {
    const data = await strmApi.runTask(taskId)
    if (data?.status === 'success') {
      success('任务已启动，请观察任务历史查看进度')
    } else {
      showError('启动失败: ' + (data?.message || '未知错误'))
    }
  } catch (e: any) {
    showError(e?.message || '运行失败')
  }
}

async function toggleTaskMonitor(task: any, type: 'incremental' | 'scheduler') {
  const index = tasks.value.findIndex((t: any) => t.id === task.id)
  if (index === -1) return

  // 创建新对象确保 Vue 响应式追踪
  const updated = { ...task }

  // 旧版 monitor_mode 迁移
  if (updated.monitor_mode) {
    if (updated.monitor_mode === 'realtime' || updated.monitor_mode === 'polling') {
      updated.incremental_enabled = true
      updated.incremental_mode = updated.monitor_mode
    } else if (updated.monitor_mode === 'scheduled') {
      updated.scheduler_enabled = true
    }
    delete updated.monitor_mode
  }

  if (type === 'incremental') {
    updated.incremental_enabled = !updated.incremental_enabled
    if (updated.incremental_enabled && !updated.incremental_mode) updated.incremental_mode = 'realtime'
    info(`${updated.name} 实时监控已${updated.incremental_enabled ? '开启' : '关闭'}`)
  } else {
    updated.scheduler_enabled = !updated.scheduler_enabled
    if (updated.scheduler_enabled && !updated.scheduler_interval) updated.scheduler_interval = 3600
    info(`${updated.name} 定时扫描已${updated.scheduler_enabled ? '开启' : '关闭'}`)
  }

  // 用数组替换方式触发 Vue 响应式更新
  const newTasks = [...tasks.value]
  newTasks[index] = updated
  tasks.value = newTasks

  // 直接调 API 保存，不触发全量 reload
  try {
    const config = await configApi.getConfig()
    const strmTasks = [...(config.strm_tasks || [])]
    const idx = strmTasks.findIndex((t: any) => t.id === task.id)
    if (idx !== -1) {
      strmTasks[idx] = { ...updated }
      await configApi.saveConfig({ ...config, strm_tasks: strmTasks })
    }
  } catch (e) {
    showError('保存状态失败')
  }
}

// --- 预览 ---
let previewTimer: ReturnType<typeof setTimeout> | null = null
function updatePreview() {
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    if (!taskForm.source_path || !showModal.value) return
    previewLoading.value = true
    try {
      const data = await strmApi.preview({
        source_path: taskForm.source_path,
        target_path: taskForm.target_path,
        content_prefix: taskForm.content_prefix,
        content_suffix: taskForm.content_suffix,
        url_encode: taskForm.url_encode,
        sync_mode: taskForm.sync_mode,
      })
      previewData.value = data
    } catch (e) {
      previewData.value = null
    } finally {
      previewLoading.value = false
    }
  }, 500)
}

onMounted(() => {
  fetchTasks()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between">
      <div>
        <h1 class="text-h5 font-weight-bold">STRM 生成</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">虚拟 STRM 文件生成与管理</div>
      </div>
      <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openNew">
        新建任务
      </v-btn>
    </div>

    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <v-row>
        <v-col v-for="i in 4" :key="i" cols="12" sm="6" md="4">
          <v-skeleton-loader type="card" />
        </v-col>
      </v-row>
    </template>

    <!-- 任务卡片网格 -->
    <template v-else-if="tasks.length > 0">
      <v-row>
        <v-col v-for="(task, index) in tasks" :key="task.id" cols="12" sm="6" md="4">
          <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEdit(index)">
            <!-- 标题行 -->
            <div class="manage-card__header">
              <div class="d-flex align-center ga-2 manage-card__title">
                <v-icon start color="primary" size="20">mdi-link-variant</v-icon>
                <span class="text-truncate">{{ task.name }}</span>
              </div>
              <v-chip size="small" variant="tonal" color="info" class="manage-card__badge">
                {{ SYNC_MODE_MAP[task.sync_mode] || '本地文件扫描' }}
              </v-chip>
            </div>

            <!-- 信息区 -->
            <div class="manage-card__body">
              <div class="manage-card__info">
                <v-icon size="14" class="mr-1">mdi-folder-outline</v-icon>
                <span class="manage-card__info-label">源</span>
                <span class="manage-card__info-value" :title="task.source_path || task.source_dir">{{ task.source_path || task.source_dir || '-' }}</span>
              </div>
              <div class="manage-card__info">
                <v-icon size="14" class="mr-1">mdi-folder-arrow-right-outline</v-icon>
                <span class="manage-card__info-label">目标</span>
                <span class="manage-card__info-value" :title="task.target_path || task.target_dir">{{ task.target_path || task.target_dir || '-' }}</span>
              </div>

              <!-- 状态标签 -->
              <div class="manage-card__tags">
                <v-chip
                  size="small"
                  :color="task.incremental_enabled ? 'info' : 'default'"
                  variant="tonal"
                  class="cursor-pointer"
                  @click.stop="toggleTaskMonitor(task, 'incremental')"
                >
                  <v-icon start size="14">{{ task.incremental_enabled ? 'mdi-eye-outline' : 'mdi-eye-off-outline' }}</v-icon>
                  实时监控
                </v-chip>
                <v-chip
                  size="small"
                  :color="task.scheduler_enabled ? 'info' : 'default'"
                  variant="tonal"
                  class="cursor-pointer"
                  @click.stop="toggleTaskMonitor(task, 'scheduler')"
                >
                  <v-icon start size="14">mdi-clock-outline</v-icon>
                  定时扫描
                </v-chip>
              </div>
            </div>

            <v-divider />
            <v-card-actions class="manage-card__actions" @click.stop>
              <v-spacer />
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play-outline" @click="handleRun(task.id)">执行</v-btn>
              <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil-outline" @click="openEdit(index)">编辑</v-btn>
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-content-copy" @click="handleDuplicate(index)">复制</v-btn>
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="handleDelete(index)">删除</v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
    </template>

    <!-- 空状态 -->
    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-link-variant</v-icon>
      <div class="text-h6 font-weight-medium">暂无 STRM 任务</div>
      <div class="text-body-2 text-medium-emphasis mt-2">点击「新建任务」创建你的第一个 STRM 生成任务</div>
      <v-btn color="primary" variant="tonal" class="mt-4" prepend-icon="mdi-plus" @click="openNew">
        新建任务
      </v-btn>
    </div>

    <!-- 编辑 Modal — Tab 分页，功能对齐全旧前端 -->
    <v-dialog v-model="showModal" max-width="800" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start>mdi-link-variant</v-icon>
          {{ isNewTask ? '新建 STRM 任务' : '编辑 STRM 任务' }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-0">
          <v-tabs v-model="activeTab" density="compact" color="primary">
            <v-tab value="basic">核心设置</v-tab>
            <v-tab value="automation">自动化与预览</v-tab>
            <v-tab value="filters">过滤规则</v-tab>
            <v-tab value="advanced">高级设置</v-tab>
          </v-tabs>
          <v-divider />

          <div class="pa-4">
            <!-- === 核心设置 === -->
            <div v-show="activeTab === 'basic'">
              <v-row>
                <v-col cols="12">
                  <v-text-field v-model="taskForm.name" label="任务名称" density="compact" placeholder="例如: 百度网盘电影库" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="taskForm.sync_mode" label="同步模式" :items="SYNC_MODE_OPTIONS" density="compact" />
                </v-col>
                <v-col v-if="taskForm.sync_mode === 'tree_file'" cols="12" sm="6">
                  <v-text-field v-model="taskForm.tree_file_path" label="目录树文件路径" density="compact" placeholder="例如: /root/tree.txt" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="taskForm.source_path" label="源目录" density="compact" placeholder="待扫描的本地媒体文件夹" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="taskForm.target_path" label="目标目录" density="compact" placeholder="STRM 文件存放位置" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="taskForm.content_prefix" label="链接前缀" density="compact" placeholder="http://ip:port/..." />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="taskForm.content_suffix" label="链接后缀" density="compact" placeholder="（可选）" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model.number="taskForm.process_interval" label="限流间隔" type="number" density="compact" placeholder="0" hint="秒/文件 (建议: 0.5 - 1.0)" persistent-hint />
                </v-col>
              </v-row>

              <v-alert v-if="taskForm.sync_mode === 'tree_file'" type="warning" density="compact" variant="tonal" class="mt-2">
                目录树模式将解析您提供的文本文件内容来同步 STRM。
              </v-alert>
            </div>

            <!-- === 自动化与预览 === -->
            <div v-show="activeTab === 'automation'">
              <v-row class="mb-4">
                <v-col cols="12">
                  <div class="d-flex align-center ga-3">
                    <v-switch v-model="taskForm.incremental_enabled" label="实时监控" density="compact" hide-details color="primary" />
                    <v-select
                      v-model="taskForm.incremental_mode"
                      label="监控模式"
                      :items="MONITOR_MODE_OPTIONS"
                      density="compact"
                      hide-details
                      style="max-width: 180px"
                    />
                    <v-text-field
                      v-if="taskForm.incremental_mode === 'polling'"
                      v-model.number="taskForm.monitor_interval"
                      label="轮询间隔(秒)"
                      type="number"
                      density="compact"
                      hide-details
                      style="max-width: 160px"
                    />
                    <span v-else class="text-caption text-medium-emphasis">实时监听文件系统事件 (Inotify)</span>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-3">
                    <v-switch v-model="taskForm.scheduler_enabled" label="定时扫描" density="compact" hide-details color="warning" />
                    <v-text-field
                      v-model.number="taskForm.scheduler_interval"
                      label="扫描间隔(秒)"
                      type="number"
                      density="compact"
                      hide-details
                      style="max-width: 160px"
                    />
                  </div>
                </v-col>
              </v-row>

              <v-divider class="my-4" />

              <div class="d-flex align-center justify-space-between mb-2">
                <span class="text-subtitle-2 font-weight-medium">实时 URL 预览</span>
                <v-switch v-model="taskForm.url_encode" label="路径 URL 编码" density="compact" hide-details color="primary" class="mr-2" @update:model-value="updatePreview" />
              </div>
              <div class="preview-box">
                <v-progress-circular v-if="previewLoading" indeterminate size="24" color="primary" />
                <template v-else-if="previewData">
                  <code class="preview-content">{{ previewData.preview_content }}</code>
                  <div class="preview-sub text-caption text-medium-emphasis mt-1">基于文件: {{ previewData.sample_file }}</div>
                </template>
                <div v-else class="text-caption text-medium-emphasis">配置源目录以查看预览</div>
              </div>
            </div>

            <!-- === 过滤规则 === -->
            <div v-show="activeTab === 'filters'">
              <v-textarea
                v-model="taskForm.target_extensions"
                label="视频扩展名"
                auto-grow
                rows="3"
                density="compact"
                hint="逗号分隔，如 .mp4,.mkv,.ts"
                persistent-hint
              />
              <v-textarea
                v-model="taskForm.meta_extensions"
                label="元数据扩展名"
                auto-grow
                rows="3"
                density="compact"
                hint="逗号分隔，如 .nfo,.jpg,.ass"
                persistent-hint
                class="mt-4"
              />
            </div>

            <!-- === 高级设置 === -->
            <div v-show="activeTab === 'advanced'">
              <div class="d-flex flex-column ga-4">
                <div class="switch-row">
                  <v-switch v-model="taskForm.copy_meta" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">同步元数据文件</div>
                    <div class="switch-desc">将 nfo、海报等元数据文件一起同步到目标目录</div>
                  </div>
                </div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.clean_target" density="compact" hide-details color="error" />
                  <div>
                    <div class="switch-label">生成前清理目标</div>
                    <div class="switch-desc">生成 STRM 前清空目标目录已有内容</div>
                  </div>
                </div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.overwrite_strm" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">覆盖已有 STRM</div>
                    <div class="switch-desc">目标目录存在同名 STRM 时覆盖</div>
                  </div>
                </div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.overwrite_meta" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">覆盖已有元数据</div>
                    <div class="switch-desc">目标目录存在同名元数据时覆盖</div>
                  </div>
                </div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.clean_empty_dirs" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">生成后清理空目录</div>
                    <div class="switch-desc">同步完成后删除目标目录中的空文件夹</div>
                  </div>
                </div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.webhook_enabled" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">实时联动策略</div>
                    <div class="switch-desc">响应 CD2 Webhook 推送并自动同步（建议开启以获得实时入库体验）</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" :loading="saving" @click="handleSave">保存任务</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>


