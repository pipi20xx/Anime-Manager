<script setup lang="ts">
/**
 * ManualOrganizeModal — 手动整理当前目录弹窗
 *
 * 对标旧前端 ManualOrganizeModalDesktop，功能：
 * - 核心配置 Tab: 重命名规则、目标目录、操作类型、强制元数据 + TMDB搜索
 * - 过滤规则 Tab: 处理间隔、忽略文件/目录正则
 * - 高级选项 Tab: 动漫优先/覆盖模式/联动STRM/清理空目录/忽略历史/重试失败/Emby检查/哈希计算/智能记忆
 * - 启动时弹出确认对话框选择"预览并手动执行"或"后台静默执行"
 */
import { reactive, ref, computed, watch } from 'vue'
import { tmdbApi } from '@/api'
import { useNotification } from '@/composables'
import { useLocalStorage } from '@/composables/useStorage'
import { GlassDialog } from '@/glass'
import FolderBrowserModal from './FolderBrowserModal.vue'

const props = defineProps<{
  modelValue: boolean
  currentPath: string
  availableRules: any[]
  defaultTask: any
  /** 打开时的源类型：本地文件浏览传 local，CD2 文件浏览传 cd2 */
  sourceVia?: 'local' | 'cd2'
  /** 是否提供"预览并手动执行"入口（默认 true） */
  previewEnabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  run: [task: any]
  'run-background': [task: any]
}>()

const { success, error: showError, warning, info } = useNotification()

const activeTab = ref('basic')
const showConfirmDialog = ref(false)

// --- 任务表单 ---
const manualTask = reactive<any>({
  id: '',
  name: '',
  rule_id: '',
  source_dir: '',
  source_via: 'local',
  target_via: 'local',
  target_dir: '',
  action_type: 'move',
  overwrite_mode: false,
  anime_priority: true,
  monitor_mode: 'none',
  monitor_interval: 3600,
  process_interval: 0,
  ignore_file_regex: [] as string[],
  ignore_dir_regex: [] as string[],
  trigger_strm: false,
  clean_empty_dir: false,
  check_emby_exists: false,
  calculate_hash: false,
  series_fingerprint: true,
  forced_tmdb_id: '',
  forced_type: null as string | null,
  forced_season: null as string | null,
  ignore_history: true,
  retry_failed: true,
})

// 正则标签输入
const newFileRegex = ref('')
const newDirRegex = ref('')

function addFileRegex() {
  if (newFileRegex.value.trim() && !manualTask.ignore_file_regex.includes(newFileRegex.value.trim())) {
    manualTask.ignore_file_regex.push(newFileRegex.value.trim())
    newFileRegex.value = ''
  }
}

function removeFileRegex(index: number) {
  manualTask.ignore_file_regex.splice(index, 1)
}

function addDirRegex() {
  if (newDirRegex.value.trim() && !manualTask.ignore_dir_regex.includes(newDirRegex.value.trim())) {
    manualTask.ignore_dir_regex.push(newDirRegex.value.trim())
    newDirRegex.value = ''
  }
}

function removeDirRegex(index: number) {
  manualTask.ignore_dir_regex.splice(index, 1)
}

// --- TMDB 搜索 ---
const manualSearch = reactive({ keyword: '', loading: false, results: [] as any[] })

async function searchTmdb() {
  if (!manualSearch.keyword) return
  manualSearch.loading = true
  try {
    const data = await tmdbApi.search({
      query: manualSearch.keyword,
      type: manualTask.forced_type || 'multi',
    })
    manualSearch.results = data?.results || []
  } catch {
    showError('搜索失败')
  } finally {
    manualSearch.loading = false
  }
}

function selectSearchResult(res: any) {
  manualTask.forced_tmdb_id = String(res.id)
  manualTask.forced_type = res.media_type || manualTask.forced_type
  manualSearch.results = []
}

// --- 图片 URL ---
function getImg(path: string): string {
  if (!path) return ''
  if (path.includes('/api/system/img')) return path
  if (path.startsWith('http')) return path
  return `/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
}

// --- 浏览器记忆：记住上次手动整理的配置（首次使用整理任务的第一个作为默认） ---
const MANUAL_ORGANIZE_STORAGE_KEY = 'apm_manual_organize_settings'
const manualOrganizeMemory = useLocalStorage<Record<string, any>>(MANUAL_ORGANIZE_STORAGE_KEY, {})

// 不需要记忆的字段：身份/入口相关 + 每次单独选择的强制参数
const MANUAL_MEMORY_EXCLUDED_KEYS = [
  'id', 'name', 'source_dir', 'source_via',
  'forced_tmdb_id', 'forced_type', 'forced_season',
]

function snapshotManualSettings() {
  const snap: Record<string, any> = {}
  for (const [k, v] of Object.entries(manualTask)) {
    if (!MANUAL_MEMORY_EXCLUDED_KEYS.includes(k)) snap[k] = v
  }
  manualOrganizeMemory.value = snap
}

// --- 弹窗打开时，合并默认配置 ---
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    // 优先使用浏览器记忆的上次配置；首次使用时取整理任务的第一个作为默认
    const saved = manualOrganizeMemory.value
    if (saved && Object.keys(saved).length > 0) {
      Object.assign(manualTask, saved)
    } else if (props.defaultTask) {
      Object.assign(manualTask, JSON.parse(JSON.stringify(props.defaultTask)))
    }
    manualTask.name = `手动整理 (${props.currentPath})`
    manualTask.source_via = props.sourceVia || 'local'
    manualTask.source_dir = props.currentPath
    if (!manualTask.rule_id && props.availableRules.length > 0) {
      manualTask.rule_id = props.availableRules[0].id
    }
    manualSearch.results = []
    manualSearch.keyword = ''
    activeTab.value = 'basic'
  }
})

// --- 源/目标类型与操作类型联动 ---
const actionTypeOptions = computed(() => {
  const options = [
    { title: '物理移动', value: 'move' },
    { title: '完整复制', value: 'copy' },
    { title: '建立硬链', value: 'link' },
    { title: 'CD2 移动', value: 'cd2_move' },
    { title: 'CD2 复制', value: 'cd2_copy' },
    { title: '仅记录哈希', value: 'hash_only' },
  ]
  if (manualTask.source_via === 'cd2' || manualTask.target_via === 'cd2') {
    return options.filter((o) => ['cd2_move', 'cd2_copy', 'hash_only'].includes(o.value))
  }
  return options
})

watch(() => [manualTask.source_via, manualTask.target_via], () => {
  if (!actionTypeOptions.value.some((o) => o.value === manualTask.action_type)) {
    manualTask.action_type = 'cd2_move'
  }
})

// 切换源类型时同步源目录：本地跟随当前浏览目录，云盘保留已填内容
watch(() => manualTask.source_via, (via) => {
  if (via === 'local') manualTask.source_dir = props.currentPath
})

// --- 目录浏览选择 ---
const showFolderBrowser = ref(false)
const browsingField = ref<'source_dir' | 'target_dir'>('target_dir')
const browsingVia = computed(() =>
  browsingField.value === 'source_dir' ? manualTask.source_via : manualTask.target_via
)

const openFolderBrowser = (field: 'source_dir' | 'target_dir') => {
  browsingField.value = field
  showFolderBrowser.value = true
}

const onFolderSelected = (path: string) => {
  manualTask[browsingField.value] = path
}

// --- 启动确认 ---
function handleConfirm() {
  showConfirmDialog.value = true
}

function handleRun() {
  snapshotManualSettings()
  showConfirmDialog.value = false
  emit('run', { ...manualTask })
}

function handleRunBackground() {
  snapshotManualSettings()
  showConfirmDialog.value = false
  emit('run-background', { ...manualTask })
}
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="750" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-folder-sync-outline</v-icon>
        手动整理当前目录 (临时任务)
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="emit('update:modelValue', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-0" style="max-height: 70vh">
        <v-tabs v-model="activeTab">
          <v-tab value="basic">核心配置</v-tab>
          <v-tab value="filters">过滤规则</v-tab>
          <v-tab value="advanced">高级选项</v-tab>
        </v-tabs>

        <v-divider />

        <div class="pa-4">
          <!-- 核心配置 -->
          <div v-if="activeTab === 'basic'">
            <v-select
              v-model="manualTask.rule_id"
              label="重命名规则"
              :items="availableRules.map((r: any) => ({ title: r.name, value: r.id }))"
              density="compact"
              variant="outlined"
              clearable
              class="mb-3"
              hide-details
            />

            <div class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">源目录类型</div>
              <v-btn-toggle v-model="manualTask.source_via" mandatory density="compact">
                <v-btn value="local" prepend-icon="mdi-harddisk">本地路径</v-btn>
                <v-btn value="cd2" prepend-icon="mdi-cloud-outline">CD2 云盘</v-btn>
              </v-btn-toggle>
            </div>
            <v-text-field
              v-if="manualTask.source_via === 'cd2'"
              v-model="manualTask.source_dir"
              label="源目录 (CD2 路径)"
              placeholder="/115open/downloads"
              variant="outlined"
              clearable
              class="mb-3"
              hide-details
              append-inner-icon="mdi-folder-open-outline"
              @click:append-inner="openFolderBrowser('source_dir')"
            />
            <div v-else class="text-body-2 mb-3">
              整理针对目录: {{ manualTask.source_dir || currentPath }}
            </div>

            <div class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">目标目录类型</div>
              <v-btn-toggle v-model="manualTask.target_via" mandatory density="compact">
                <v-btn value="local" prepend-icon="mdi-harddisk">本地路径</v-btn>
                <v-btn value="cd2" prepend-icon="mdi-cloud-outline">CD2 云盘</v-btn>
              </v-btn-toggle>
            </div>
            <v-text-field
              v-model="manualTask.target_dir"
              :label="manualTask.target_via === 'cd2' ? '目标目录 (CD2 路径，如 /115open/media)' : '目标目录'"
              :placeholder="manualTask.target_via === 'cd2' ? '/115open/media' : '媒体库绝对路径 (如: /vol1/1000/Media)'"
              density="compact"
              variant="outlined"
              class="mb-3"
              hide-details
              append-inner-icon="mdi-folder-open-outline"
              @click:append-inner="openFolderBrowser('target_dir')"
            />

            <v-select
              v-model="manualTask.action_type"
              label="操作类型"
              :items="actionTypeOptions"
              density="compact"
              variant="outlined"
              class="mb-3"
              hide-details
            />

            <!-- 强制元数据 -->
            <div class="config-section mb-4">
              <div class="section-title mb-3">
                <v-icon size="16" color="info">mdi-tune-variant</v-icon>
                强制元数据 (可选)
              </div>
              <v-row density="compact" class="mb-2">
                <v-col cols="4">
                  <v-text-field v-model="manualTask.forced_tmdb_id" label="TMDB ID" placeholder="TMDB ID" density="compact" hide-details variant="outlined" />
                </v-col>
                <v-col cols="4">
                  <v-select
                    v-model="manualTask.forced_type"
                    label="类型"
                    :items="[{ title: '自动', value: null }, { title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]"
                    density="compact" hide-details variant="outlined" clearable
                  />
                </v-col>
                <v-col cols="4">
                  <v-text-field v-model="manualTask.forced_season" label="季号" placeholder="自动" type="number" density="compact" hide-details variant="outlined" />
                </v-col>
              </v-row>

              <!-- TMDB搜索 -->
              <div class="d-flex ga-2 mb-2">
                <v-text-field
                  v-model="manualSearch.keyword"
                  placeholder="搜索剧名自动填入 ID 和类型..."
                  density="compact" hide-details variant="outlined"
                  prepend-inner-icon="mdi-magnify"
                  @keydown.enter="searchTmdb"
                />
                <v-btn color="primary" variant="tonal" :loading="manualSearch.loading" @click="searchTmdb" size="small" style="align-self: center">
                  搜索
                </v-btn>
              </div>

              <div v-if="manualSearch.results.length > 0" class="search-results-list">
                <div
                  v-for="res in manualSearch.results"
                  :key="res.id"
                  class="search-result-item"
                  @click="selectSearchResult(res)"
                >
                  <v-img v-if="res.poster_path" :src="getImg(res.poster_path)" width="50" height="75" cover class="rounded" />
                  <div v-else class="poster-placeholder-sm">无</div>
                  <div class="search-result-info">
                    <div class="search-result-title">{{ res.title }} ({{ res.year }})</div>
                    <div class="search-result-sub">ID: {{ res.id }} · {{ res.category }} · {{ res.original_title || '-' }}</div>
                    <div v-if="res.genres?.length" class="search-result-sub">流派：{{ res.genres.join(' / ') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 过滤规则 -->
          <div v-if="activeTab === 'filters'">
            <v-text-field
              v-model.number="manualTask.process_interval"
              label="处理间隔(s)"
              type="number"
              min="0"
              density="compact"
              variant="outlined"
              class="mb-4"
              hide-details
            />

            <!-- 忽略文件正则 -->
            <div class="mb-4">
              <div class="text-subtitle-2 font-weight-bold mb-2">忽略文件正则</div>
              <div class="d-flex ga-2 mb-2">
                <v-text-field
                  v-model="newFileRegex"
                  placeholder="输入正则后添加"
                  density="compact" variant="outlined" hide-details
                  @keydown.enter="addFileRegex"
                />
                <v-btn size="small" variant="tonal" @click="addFileRegex">添加</v-btn>
              </div>
              <div class="d-flex flex-wrap ga-2">
                <v-chip
                  v-for="(regex, i) in manualTask.ignore_file_regex"
                  :key="'file-' + i"
                  size="small"
                  closable
                  @click:close="removeFileRegex(i as number)"
                >
                  {{ regex }}
                </v-chip>
              </div>
            </div>

            <!-- 忽略目录正则 -->
            <div>
              <div class="text-subtitle-2 font-weight-bold mb-2">忽略目录正则</div>
              <div class="d-flex ga-2 mb-2">
                <v-text-field
                  v-model="newDirRegex"
                  placeholder="输入正则后添加"
                  density="compact" variant="outlined" hide-details
                  @keydown.enter="addDirRegex"
                />
                <v-btn size="small" variant="tonal" @click="addDirRegex">添加</v-btn>
              </div>
              <div class="d-flex flex-wrap ga-2">
                <v-chip
                  v-for="(regex, i) in manualTask.ignore_dir_regex"
                  :key="'dir-' + i"
                  size="small"
                  closable
                  @click:close="removeDirRegex(i as number)"
                >
                  {{ regex }}
                </v-chip>
              </div>
            </div>
          </div>

          <!-- 高级选项 -->
          <div v-if="activeTab === 'advanced'">
            <div class="d-flex flex-column ga-4">
              <div class="switch-row">
                <v-switch v-model="manualTask.anime_priority" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">动漫优先</div>
                  <div class="switch-desc">优先使用动漫专用识别策略，提高动漫识别准确率</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.overwrite_mode" :disabled="manualTask.action_type === 'hash_only'" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">覆盖模式</div>
                  <div class="switch-desc">目标路径已存在文件时允许覆盖<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.trigger_strm" :disabled="manualTask.action_type === 'hash_only'" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">联动 STRM</div>
                  <div class="switch-desc">整理完成后自动生成/更新 STRM 文件<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.clean_empty_dir" :disabled="manualTask.action_type === 'hash_only'" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">清理空目录</div>
                  <div class="switch-desc">整理后删除源目录中的空文件夹<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.ignore_history" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">忽略历史</div>
                  <div class="switch-desc">跳过已成功整理或已跳过的历史记录，不重新处理</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.retry_failed" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">重试失败项</div>
                  <div class="switch-desc">重新尝试之前识别失败的文件（TMDB 数据可能已更新）</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.check_emby_exists" :disabled="manualTask.action_type === 'hash_only'" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">Emby 检查</div>
                  <div class="switch-desc">检测 Emby 库是否存在，存在则跳过处理<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></div>
                </div>
              </div>

              <div class="switch-row" style="align-items: flex-start;">
                <v-switch v-model="manualTask.calculate_hash" :disabled="manualTask.action_type === 'hash_only'" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">哈希计算</div>
                  <div class="switch-desc">整理时计算 SHA1 和 ED2K 哈希值并记录<span v-if="manualTask.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下强制启用）</span></div>
                  <div v-if="manualTask.action_type !== 'hash_only'" class="hash-warning-inline">
                    ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                  </div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="manualTask.series_fingerprint" density="compact" color="primary" hide-details />
                <div>
                  <div class="switch-label">智能记忆</div>
                  <div class="switch-desc">自动记住系列特征，后续文件实现秒级识别</div>
                </div>
              </div>
            </div>

            <v-alert type="warning" variant="tonal" density="compact" class="mt-4">
              提示：模拟预览不会修改任何文件。正式执行将按照上述配置物理处理文件。
            </v-alert>
          </div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-play" @click="handleConfirm">
          启动整理任务
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 启动确认对话框 -->
  <GlassDialog
    v-model="showConfirmDialog"
    :max-width="420"
    :scrollable="false"
    title="启动整理任务"
    icon="mdi-play"
  >
    <div class="text-body-1 mb-4">您希望如何运行此临时整理任务？</div>
    <v-alert type="info" variant="tonal" density="compact">
      模拟预览不会修改任何文件，正式执行将物理处理文件。
    </v-alert>
    <template #actions>
      <v-btn color="info" variant="tonal" prepend-icon="mdi-rocket-launch" @click="handleRunBackground">
        后台静默执行
      </v-btn>
      <v-btn v-if="previewEnabled !== false" color="primary" variant="tonal" prepend-icon="mdi-eye-outline" @click="handleRun">
        预览并手动执行
      </v-btn>
    </template>
  </GlassDialog>

  <!-- 目录浏览选择 -->
  <FolderBrowserModal
    v-model="showFolderBrowser"
    :via="browsingVia"
    :title="browsingField === 'source_dir' ? '选择源目录' : '选择目标目录'"
    @select="onFolderSelected"
  />
</template>

<!-- scoped 样式已迁移至 global.css .config-row / .inactive-hint / .hash-warning-inline -->
