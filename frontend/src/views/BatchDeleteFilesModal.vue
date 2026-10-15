<script setup lang="ts">
/**
 * BatchDeleteFilesModal — 批量删除文件（按扩展名）弹窗
 *
 * 使用说明（与需求一致）：
 * - 本功能仅用于批量删除文件夹中指定后缀名的文件
 * - 「要删除的文件扩展名」留空 = 删除所有文件；「不想删除的文件扩展名」留空 = 不排除任何文件
 * - 两者一般情况下只需要填一个，也可同时使用
 * - 优先级：不想删除的文件扩展名 > 要删除的文件扩展名
 *   即同时指定了某个扩展名时，包含该扩展名的文件不会被删除
 * - 操作流程：填写规则 → 开始扫描（仅预览）→ 开始批量删除文件
 *
 * - 只删除文件，不会删除任何文件夹
 * - source="local" 走本地文件系统接口，source="cd2" 走 CD2 gRPC 接口
 */
import { ref, watch, computed } from 'vue'
import { organizerApi, cd2Api } from '@/api'
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

// 规则输入（记住上次填写），多项以 ; 分隔
const deleteText = useLocalStorage('apm_batch_delete_exts', '')
const excludeText = useLocalStorage('apm_batch_delete_exclude_exts', '')
const recursive = useLocalStorage('apm_batch_delete_recursive', true)

const scanning = ref(false)
const deleting = ref(false)
const scanFailed = ref(false)
const hasScanned = ref(false)
const scanItems = ref<{ path: string; name: string; size: number }[]>([])
const scanCount = ref(0)
const scanTotalSize = ref(0)
const scanTruncated = ref(false)

/** 列表最多渲染的行数，避免上万条时卡顿 */
const RENDER_LIMIT = 300

const scanCountText = computed(() => `${scanCount.value} 个文件`)
const visibleItems = computed(() => scanItems.value.slice(0, RENDER_LIMIT))

/** 拆分扩展名：支持 ; , ， ； 以及换行分隔 */
function parseExtensions(text: string): string[] {
  return text
    .split(/[;,\n，；]/)
    .map((s: string) => s.trim())
    .filter(Boolean)
}

const deleteExts = computed(() => parseExtensions(deleteText.value || ''))
const excludeExts = computed(() => parseExtensions(excludeText.value || ''))

/** 两个规则都为空 = 删除所有文件，属于高危操作，界面上强提示 */
const isDeleteAll = computed(() => deleteExts.value.length === 0)
const isDangerous = computed(() => isDeleteAll.value && excludeExts.value.length === 0)

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

function buildBody() {
  return {
    path: props.currentPath,
    delete_extensions: deleteExts.value,
    exclude_extensions: excludeExts.value,
    recursive: recursive.value,
  }
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
  deleteText.value = ''
  excludeText.value = ''
}

async function scan() {
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
    scanFailed.value = false
    hasScanned.value = true
  } catch (e: any) {
    scanItems.value = []
    scanCount.value = 0
    scanTotalSize.value = 0
    scanTruncated.value = false
    scanFailed.value = true
    hasScanned.value = true
    showError(e?.message || '扫描失败')
  } finally {
    scanning.value = false
  }
}

// 每次打开弹窗都重置上次结果，由用户手动点击"开始扫描"
watch(() => props.modelValue, (open) => {
  if (open) {
    hasScanned.value = false
    scanItems.value = []
    scanCount.value = 0
    scanTotalSize.value = 0
    scanTruncated.value = false
    scanFailed.value = false
  }
})

// 规则或范围变更后旧结果失效，需要重新扫描
watch([deleteText, excludeText, recursive], () => {
  if (hasScanned.value) {
    hasScanned.value = false
    scanItems.value = []
    scanCount.value = 0
    scanTotalSize.value = 0
    scanTruncated.value = false
    scanFailed.value = false
  }
})

async function doDelete() {
  if (!hasScanned.value || scanCount.value === 0) return

  const ruleText = isDeleteAll.value
    ? (excludeExts.value.length
        ? `删除所有文件，但排除：${excludeExts.value.join('、')}`
        : '删除所有文件（未填写任何扩展名，且未排除任何文件）')
    : `删除扩展名：${deleteExts.value.join('、')}`
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
</script>

<template>
  <GlassDialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :max-width="720"
    title="批量删除文件"
    icon="mdi-file-remove-outline"
  >
    <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
      <div class="font-weight-medium mb-1">使用说明</div>
      <div class="text-body-2">本功能仅用于批量删除文件夹中指定后缀名的文件（只删文件，不会删除文件夹）。</div>
      <div class="text-body-2">要删除的文件扩展名和不想删除的文件扩展名一般情况下只需要填一个，也可以同时使用。</div>
      <div class="text-body-2">
        优先级：<b>不想删除的文件扩展名 &gt; 要删除的文件扩展名</b>——同时指定了某个扩展名时，包含该扩展名的文件不会被删除。
      </div>
    </v-alert>

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

    <v-text-field
      v-model="excludeText"
      label="不想删除的文件扩展名（优先级最高）"
      placeholder=".mkv;.mp4"
      density="compact"
      variant="outlined"
      clearable
      persistent-hint
      hint="以 ; 隔开，如 .mkv;.mp4；指定扩展名的文件不会被删除，留空则不排除任何文件"
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
        @click="scan"
      >
        {{ hasScanned ? '重新扫描' : '开始扫描' }}
      </v-btn>
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-eraser"
        :disabled="!deleteText && !excludeText"
        @click="resetRules"
      >
        清空规则
      </v-btn>
      <span v-if="hasScanned && !scanning" class="text-body-2 text-medium-emphasis">
        待删除 {{ scanCountText }}，合计 {{ formatSize(scanTotalSize) }}
      </span>
      <span v-else-if="!scanning" class="text-body-2 text-medium-emphasis">
        尚未扫描
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
            <v-list-item-subtitle class="text-caption">{{ formatSize(item.size) }}</v-list-item-subtitle>
          </v-list-item>
        </v-list>
        <div v-else class="text-center text-body-2 text-medium-emphasis pa-4">
          {{ hasScanned ? (scanFailed ? '扫描失败' : '没有匹配的文件') : '填写扩展名后点击"开始扫描"查看结果' }}
        </div>
        <div v-if="scanCount > visibleItems.length" class="text-caption text-medium-emphasis pa-3 text-center">
          仅显示前 {{ visibleItems.length }} 个{{ scanTruncated ? `（预览上限 ${scanItems.length} 条）` : '' }}，实际将删除 {{ scanCountText }}
        </div>
      </template>
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
