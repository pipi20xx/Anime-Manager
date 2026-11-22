<script setup lang="ts">
/**
 * BatchDeleteFilesModal — 批量删除文件弹窗
 *
 * 支持三种模式：
 * - 按扩展名（ext）：删除指定后缀名的文件，留空 = 删除所有文件
 * - 按文件名（name）：按完整文件名匹配（不区分大小写），支持 * ? 通配符
 * - 重复副本（duplicate）：去掉名字末尾的副本标记（(1)、（2）、- 副本、- Copy (2) 等）后，
 *   若同目录确实存在同扩展名的原文件，则把带标记的副本列为待删除，原文件保留
 *
 * 三种模式共同点：
 * - 「不想删除的文件扩展名」优先级最高，命中的文件永不删除
 * - 只删除文件，不会删除任何文件夹
 * - 操作流程：填写规则 → 开始扫描（仅预览）→ 开始批量删除文件
 * - source="local" 走本地文件系统接口，source="cd2" 走 CD2 gRPC 接口
 */
import { ref, watch, computed } from 'vue'
import { organizerApi, cd2Api } from '@/api'
import type { BatchDeleteFilesBody, BatchDeleteMode } from '@/api/organizer'
import { useNotification, useConfirm } from '@/composables'
import { useLocalStorage } from '@/composables/useStorage'
import { GlassDialog } from '@/glass'

const props = withDefaults(defineProps<{
  modelValue: boolean
  currentPath: string
  /** 数据源：local=本地文件浏览，cd2=CD2 云盘文件浏览 */
  source?: 'local' | 'cd2'
}>(), {
  source: 'local',
})

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  deleted: []
}>()

const { success, error: showError, warning, info } = useNotification()
const { confirm } = useConfirm()

/** 扫描结果条目 */
interface ScanItem {
  path: string
  name: string
  size: number
  /** 重复副本模式：该组保留的文件 */
  keep_name?: string
  keep_path?: string
  /** 重复副本模式：该组重复文件数量 */
  group_size?: number
}

// 模式与规则输入（记住上次填写），多项以 ; 分隔
const mode = useLocalStorage<BatchDeleteMode>('apm_batch_delete_mode', 'ext')
const deleteText = useLocalStorage('apm_batch_delete_exts', '')
const namesText = useLocalStorage('apm_batch_delete_names', '')
const excludeText = useLocalStorage('apm_batch_delete_exclude_exts', '')
const recursive = useLocalStorage('apm_batch_delete_recursive', true)
const dupKeepPolicy = useLocalStorage<'original' | 'newest' | 'oldest' | 'largest'>(
  'apm_batch_delete_dup_keep', 'original')
const dupRequireOriginal = useLocalStorage('apm_batch_delete_dup_require_original', true)
const dupSameSizeOnly = useLocalStorage('apm_batch_delete_dup_same_size', true)

const scanning = ref(false)
const deleting = ref(false)
const scanFailed = ref(false)
const hasScanned = ref(false)
const scanItems = ref<ScanItem[]>([])
const scanCount = ref(0)
const scanTotalSize = ref(0)
const scanTruncated = ref(false)
const scanSkippedCount = ref(0)
const scanGroupCount = ref(0)

/** 列表最多渲染的行数，避免上万条时卡顿 */
const RENDER_LIMIT = 300

const scanCountText = computed(() => `${scanCount.value} 个文件`)
const visibleItems = computed(() => scanItems.value.slice(0, RENDER_LIMIT))

/** 拆分多值输入：支持 ; , ， ； 以及换行分隔 */
function parseList(text: string): string[] {
  return text
    .split(/[;,\n，；]/)
    .map((s: string) => s.trim())
    .filter(Boolean)
}

/** 拆分文件名：只按 ; ； 换行分隔（文件名自身可能带逗号） */
function parseNameList(text: string): string[] {
  return text
    .split(/[;\n；]/)
    .map((s: string) => s.trim())
    .filter(Boolean)
}

const deleteExts = computed(() => parseList(deleteText.value || ''))
const deleteNames = computed(() => parseNameList(namesText.value || ''))
const excludeExts = computed(() => parseList(excludeText.value || ''))

/** 按扩展名模式且两个规则都为空 = 删除所有文件，属于高危操作，界面上强提示 */
const isDeleteAll = computed(() => mode.value === 'ext' && deleteExts.value.length === 0)
const isDangerous = computed(() => isDeleteAll.value && excludeExts.value.length === 0)

const keepPolicyOptions = [
  { title: '原文件（无副本标记，推荐）', value: 'original' },
  { title: '修改时间最新的', value: 'newest' },
  { title: '修改时间最早的', value: 'oldest' },
  { title: '体积最大的', value: 'largest' },
]

/** 当前模式是否已填好可扫描的规则 */
const canScan = computed(() => {
  if (mode.value === 'name') return deleteNames.value.length > 0
  return true
})

/** 当前模式是否有可清空的规则 */
const canReset = computed(() => {
  if (mode.value === 'ext') return !!deleteText.value || !!excludeText.value
  if (mode.value === 'name') return !!namesText.value || !!excludeText.value
  return dupKeepPolicy.value !== 'original' || !dupRequireOriginal.value
    || !dupSameSizeOnly.value || !!excludeText.value
})

/**
 * 归一化两种 API 的响应包装：
 * organizer: {status: 'success', data: {count, items/deleted, ...}}
 * cd2: {success, count, items/deleted, ...} 直接返回结果对象
 */
function extractPayload(res: any): any {
  if (res?.data && typeof res.data === 'object' &&
      ('items' in res.data || 'deleted' in res.data || 'count' in res.data)) {
    return res.data
  }
  return res ?? {}
}

function buildBody(): BatchDeleteFilesBody {
  const body: BatchDeleteFilesBody = {
    path: props.currentPath,
    mode: mode.value,
    exclude_extensions: excludeExts.value,
    recursive: recursive.value,
  }
  if (mode.value === 'name') {
    body.delete_names = deleteNames.value
  } else if (mode.value === 'duplicate') {
    body.duplicate_options = {
      keep_policy: dupKeepPolicy.value,
      require_original: dupRequireOriginal.value,
      same_size_only: dupSameSizeOnly.value,
    }
  } else {
    body.delete_extensions = deleteExts.value
  }
  return body
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function resetRules() {
  if (mode.value === 'ext') {
    deleteText.value = ''
  } else if (mode.value === 'name') {
    namesText.value = ''
  } else {
    dupKeepPolicy.value = 'original'
    dupRequireOriginal.value = true
    dupSameSizeOnly.value = true
  }
  excludeText.value = ''
}

function clearScan() {
  hasScanned.value = false
  scanItems.value = []
  scanCount.value = 0
  scanTotalSize.value = 0
  scanTruncated.value = false
  scanSkippedCount.value = 0
  scanGroupCount.value = 0
  scanFailed.value = false
}

async function scan() {
  if (!canScan.value) {
    warning('请先填写要删除的文件名')
    return
  }
  scanning.value = true
  try {
    const body = buildBody()
    const res = props.source === 'cd2'
      ? await cd2Api.scanFilesByExt(body)
      : await organizerApi.scanFilesByExt(body)
    const data = extractPayload(res)
    if (data?.success === false) throw new Error(data?.message || '扫描失败')
    scanItems.value = data?.items || []
    scanCount.value = data?.count ?? scanItems.value.length
    scanTotalSize.value = data?.total_size || 0
    scanTruncated.value = !!data?.truncated
    scanSkippedCount.value = data?.skipped_count || 0
    scanGroupCount.value = data?.group_count || 0
    scanFailed.value = false
    hasScanned.value = true
  } catch (e: any) {
    scanItems.value = []
    scanCount.value = 0
    scanTotalSize.value = 0
    scanTruncated.value = false
    scanSkippedCount.value = 0
    scanGroupCount.value = 0
    scanFailed.value = true
    hasScanned.value = true
    showError(e?.message || '扫描失败')
  } finally {
    scanning.value = false
  }
}

// 每次打开弹窗都重置上次结果，由用户手动点击"开始扫描"
watch(() => props.modelValue, (open) => {
  if (open) clearScan()
})

// 规则或范围变更后旧结果失效，需要重新扫描
watch([mode, deleteText, namesText, excludeText, recursive,
  dupKeepPolicy, dupRequireOriginal, dupSameSizeOnly], () => {
  if (hasScanned.value) clearScan()
})

/** 确认弹窗里的规则说明 */
function describeRule(): string {
  if (mode.value === 'name') {
    return `删除文件名：${deleteNames.value.join('、')}`
  }
  if (mode.value === 'duplicate') {
    const parts = [
      dupRequireOriginal.value
        ? '保留原文件'
        : `保留：${keepPolicyOptions.find(o => o.value === dupKeepPolicy.value)?.title || '最早的文件'}`,
    ]
    if (dupRequireOriginal.value) parts.push('仅存在原文件时')
    if (dupSameSizeOnly.value) parts.push('仅大小一致')
    return `清理重复副本（${parts.join('，')}）`
  }
  return isDeleteAll.value
    ? '删除所有文件（未填写任何扩展名）'
    : `删除扩展名：${deleteExts.value.join('、')}`
}

async function doDelete() {
  if (!hasScanned.value || scanCount.value === 0) return

  const ruleText = describeRule()
    + (excludeExts.value.length ? `，但排除：${excludeExts.value.join('、')}` : '')

  const ok = await confirm({
    title: '确认批量删除',
    content: `目录 ${props.currentPath}${recursive.value ? '（含子文件夹）' : '（仅当前目录）'}；`
      + `${ruleText}；共 ${scanCountText.value}，合计 ${formatSize(scanTotalSize.value)}。`
      + '此操作不可撤销，是否继续？',
    confirmText: '开始批量删除文件',
    confirmColor: 'error',
  })
  if (!ok) return

  deleting.value = true
  try {
    const body = buildBody()
    const res = props.source === 'cd2'
      ? await cd2Api.deleteFilesByExt(body)
      : await organizerApi.deleteFilesByExt(body)
    const data = extractPayload(res)
    if (data?.success === false) throw new Error(data?.message || '批量删除失败')
    const deleted = data?.count || 0
    const failed = data?.failed || []
    if (deleted > 0 && failed.length > 0) {
      warning(`已删除 ${deleted} 个文件，${failed.length} 个失败被跳过`)
    } else if (deleted > 0) {
      success(`已删除 ${deleted} 个文件，释放 ${formatSize(data?.freed_bytes || 0)}`)
    } else {
      info('没有可删除的文件')
    }
    if (deleted > 0) emit('deleted')
    emit('update:modelValue', false)
  } catch (e: any) {
    showError(e?.message || '批量删除失败')
  } finally {
    deleting.value = false
  }
}

/** 展示用相对路径 */
function displayPath(p: string) {
  const root = props.currentPath
  if (root && root !== '/' && p.startsWith(root.endsWith('/') ? root : root + '/')) {
    return p.slice(root.length)
  }
  return p
}

/** 扫描结果条目的副标题 */
function itemSubtitle(item: ScanItem): string {
  if (mode.value === 'duplicate') {
    const keep = item.keep_name ? `保留 ${item.keep_name} · ` : ''
    const group = item.group_size ? `同组 ${item.group_size} 个 · ` : ''
    return `${keep}${group}${formatSize(item.size)}`
  }
  return formatSize(item.size)
}
</script>

<template>
  <GlassDialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :max-width="760"
    title="批量删除文件"
    icon="mdi-file-remove-outline"
  >
    <v-btn-toggle
      v-model="mode"
      mandatory
      divided
      density="compact"
      color="primary"
      variant="outlined"
      class="mb-4"
    >
      <v-btn value="ext" prepend-icon="mdi-file-extension-outline">按扩展名</v-btn>
      <v-btn value="name" prepend-icon="mdi-file-search-outline">按文件名</v-btn>
      <v-btn value="duplicate" prepend-icon="mdi-content-duplicate">重复副本</v-btn>
    </v-btn-toggle>

    <v-alert type="info" variant="tonal" density="compact" class="mb-4">
      <template v-if="mode === 'ext'">
        <div class="text-body-2">按后缀名删除文件（只删文件，不会删除文件夹）。</div>
        <div class="text-body-2">「要删除的文件扩展名」留空 = 删除所有文件；「不想删除的文件扩展名」优先级最高。</div>
      </template>
      <template v-else-if="mode === 'name'">
        <div class="text-body-2">按完整文件名删除（不区分大小写），支持 <b>*</b> 与 <b>?</b> 通配符，如 <code>*.nfo</code>、<code>sample*</code>。</div>
        <div class="text-body-2">只写名字不带扩展名（如 <code>sample</code>）时，会删除该名字所有扩展名的文件；多个文件名用 ; 隔开；方括号 [ ] 按普通字符处理。</div>
      </template>
      <template v-else>
        <div class="text-body-2">
          去掉文件名末尾的副本标记（<code>(1)</code>、<code>（2）</code>、<code>- 副本</code>、<code>- Copy (2)</code> 等）后，
          若同一文件夹里还有同扩展名的<b>原文件</b>，就认为这些带标记的文件是重复副本，全部列入待删除，<b>原文件始终保留</b>。
        </div>
        <div class="text-body-2">
          为了安全，默认只在「确实存在原文件」且「文件大小与原文件一致」时才删除；没有原文件的
          <code>(01)</code> 这类分集文件名不会被误删。
        </div>
      </template>
    </v-alert>

    <!-- 按扩展名 -->
    <template v-if="mode === 'ext'">
      <v-text-field
        v-model="deleteText"
        label="要删除的文件扩展名"
        placeholder=".jpg;.png"
        density="compact"
        variant="outlined"
        clearable
        persistent-hint
        hint="以 ; 隔开，如 .jpg;.png；留空则删除所有文件"
        prepend-inner-icon="mdi-delete-outline"
        class="mb-3"
      />
    </template>

    <!-- 按文件名 -->
    <template v-else-if="mode === 'name'">
      <v-text-field
        v-model="namesText"
        label="要删除的文件名"
        placeholder="example.nfo;*.tmp"
        density="compact"
        variant="outlined"
        clearable
        persistent-hint
        hint="以 ; 隔开；完整文件名匹配（不区分大小写），支持 * ? 通配符；只写名字不带扩展名时，删除该名字所有扩展名的文件"
        prepend-inner-icon="mdi-file-search-outline"
        class="mb-3"
      />
    </template>

    <!-- 重复副本 -->
    <template v-else>
      <div class="d-flex align-center flex-wrap ga-4 mb-3">
        <v-select
          v-model="dupKeepPolicy"
          :items="keepPolicyOptions"
          label="无原文件时保留哪个副本"
          density="compact"
          variant="outlined"
          :disabled="dupRequireOriginal"
          :hint="dupRequireOriginal ? '存在原文件时始终保留原文件' : '没有原文件时按此策略保留一个'"
          persistent-hint
          style="max-width: 300px"
        />
        <v-chip size="small" variant="tonal" color="primary" prepend-icon="mdi-content-duplicate">
          按文件夹分组比对
        </v-chip>
      </div>
      <v-switch
        v-model="dupRequireOriginal"
        color="primary"
        density="compact"
        hide-details
        class="mb-2"
        label="仅清理存在原文件的副本（推荐；关闭后无原文件时只保留一个）"
      />
      <v-switch
        v-model="dupSameSizeOnly"
        color="primary"
        density="compact"
        hide-details
        class="mb-3"
        label="仅删除与原文件大小一致的副本（推荐；大小不同可能是不同内容）"
      />
    </template>

    <v-text-field
      v-model="excludeText"
      label="不想删除的文件扩展名（优先级最高）"
      placeholder=".mkv;.mp4"
      density="compact"
      variant="outlined"
      clearable
      persistent-hint
      hint="以 ; 隔开，如 .mkv;.mp4；指定扩展名的文件不会被删除，留空则不排除任何文件（三种模式都生效）"
      prepend-inner-icon="mdi-shield-check-outline"
      class="mb-3"
    />

    <div class="d-flex align-center flex-wrap ga-4 mb-3">
      <v-switch
        v-model="recursive"
        color="primary"
        density="compact"
        hide-details
        :label="recursive ? '包含子文件夹（递归）' : '仅当前文件夹'"
      />
      <v-chip v-if="isDeleteAll" size="small" color="error" variant="tonal" prepend-icon="mdi-alert">
        未填写「要删除的扩展名」→ 将删除所有文件
      </v-chip>
    </div>

    <v-alert v-if="isDangerous" type="error" variant="tonal" density="compact" class="mb-3">
      当前规则会删除该目录下（{{ recursive ? '含子文件夹' : '不含子文件夹' }}）<b>所有文件</b>且不排除任何文件，请务必先扫描确认。
    </v-alert>

    <div class="d-flex align-center flex-wrap ga-2 mb-2">
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        :prepend-icon="hasScanned ? 'mdi-refresh' : 'mdi-magnify'"
        :loading="scanning"
        :disabled="!canScan"
        @click="scan"
      >
        {{ hasScanned ? '重新扫描' : '开始扫描' }}
      </v-btn>
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-eraser"
        :disabled="!canReset"
        @click="resetRules"
      >
        清空规则
      </v-btn>
      <span v-if="hasScanned && !scanning" class="text-body-2 text-medium-emphasis">
        待删除 {{ scanCountText }}，合计 {{ formatSize(scanTotalSize) }}
        <template v-if="mode === 'duplicate' && scanGroupCount > 0">
          （{{ scanGroupCount }} 组重复）
        </template>
      </span>
      <span v-else-if="!scanning" class="text-body-2 text-medium-emphasis">
        {{ mode === 'name' && !deleteNames.length ? '填写要删除的文件名后开始扫描' : '尚未扫描' }}
      </span>
    </div>

    <!-- 扫描结果列表 -->
    <div class="scan-list">
      <div v-if="scanning" class="pa-4">
        <v-skeleton-loader v-for="i in 3" :key="i" type="list-item" class="mb-1" />
      </div>
      <template v-else>
        <v-list v-if="scanCount > 0" density="compact" class="py-0">
          <v-list-item v-for="item in visibleItems" :key="item.path">
            <template #prepend>
              <v-icon size="18" color="error">mdi-file-remove-outline</v-icon>
            </template>
            <v-list-item-title class="text-body-2 text-wrap">{{ displayPath(item.path) }}</v-list-item-title>
            <v-list-item-subtitle class="text-caption">{{ itemSubtitle(item) }}</v-list-item-subtitle>
          </v-list-item>
        </v-list>
        <div v-else class="text-center text-body-2 text-medium-emphasis pa-4">
          {{ hasScanned ? (scanFailed ? '扫描失败' : '没有匹配的文件') : '填写规则后点击"开始扫描"查看结果' }}
        </div>
        <div v-if="scanCount > visibleItems.length" class="text-caption text-medium-emphasis pa-3 text-center">
          仅显示前 {{ visibleItems.length }} 个{{ scanTruncated ? `（预览上限 ${scanItems.length} 条）` : '' }}，实际将删除 {{ scanCountText }}
        </div>
      </template>
    </div>

    <div v-if="mode === 'duplicate' && scanSkippedCount > 0" class="text-caption text-medium-emphasis mt-2">
      另有 {{ scanSkippedCount }} 个副本未删除：大小与原文件不一致，或同目录找不到原文件（已跳过，不会删除）。
    </div>

    <template #actions>
      <v-spacer />
      <v-btn
        color="error"
        variant="tonal"
        prepend-icon="mdi-file-remove-outline"
        :disabled="!hasScanned || scanCount === 0 || scanning"
        :loading="deleting"
        @click="doDelete"
      >
        开始批量删除文件（{{ scanCount }}）
      </v-btn>
    </template>
  </GlassDialog>
</template>

<style scoped>
.scan-list {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  max-height: 320px;
  overflow-y: auto;
}
</style>
