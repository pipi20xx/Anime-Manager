<script setup lang="ts">
/**
 * CleanEmptyDirsModal — 清理空文件夹弹窗
 *
 * - 点击"开始扫描"后递归扫描当前目录子树中"实际为空"的文件夹，预览后确认删除
 * - 内置系统垃圾文件（.DS_Store / Thumbs.db / @eaDir(仅本地) / ._*）始终不算内容
 * - 支持自定义通配符规则（每行一条，如 *.png.zip），规则保存在浏览器 localStorage
 * - 当前目录本身永远不会被删除
 * - source="local" 走本地文件系统接口，source="cd2" 走 CD2 gRPC 接口
 */
import { ref, watch, computed } from 'vue'
import { organizerApi, cd2Api } from '@/api'
import { useNotification } from '@/composables'
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
  cleaned: []
}>()

const { success, error: showError, warning, info } = useNotification()

// 忽略规则（每行一条通配符），记住上次输入
const DEFAULT_PATTERNS = '*.png\n*.zip\n*.7z\n*.jpg'
const patternsText = useLocalStorage('apm_file_browser_clean_patterns', DEFAULT_PATTERNS)

const scanning = ref(false)
const cleaning = ref(false)
const scanFailed = ref(false)
const hasScanned = ref(false)
const scanItems = ref<{ path: string; name: string; junk_files: string[] }[]>([])

const scanCount = computed(() => scanItems.value.length)

function parsePatterns(): string[] {
  return patternsText.value
    .split('\n')
    .map((s: string) => s.trim())
    .filter(Boolean)
}

function resetPatterns() {
  patternsText.value = DEFAULT_PATTERNS
}

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

async function scan() {
  scanning.value = true
  try {
    const body = { path: props.currentPath, ignore_patterns: parsePatterns() }
    const res = props.source === 'cd2'
      ? await cd2Api.scanEmptyDirs(body)
      : await organizerApi.scanEmptyDirs(body)
    const data = extractPayload(res)
    if (data?.success === false) throw new Error(data?.message || '扫描失败')
    scanItems.value = data?.items || []
    scanFailed.value = false
    hasScanned.value = true
  } catch (e: any) {
    scanItems.value = []
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
    scanFailed.value = false
  }
})

// 规则变更后旧结果失效，需要重新扫描
watch(patternsText, () => {
  if (hasScanned.value) {
    hasScanned.value = false
    scanItems.value = []
    scanFailed.value = false
  }
})

async function doClean() {
  if (!hasScanned.value || scanCount.value === 0) return
  cleaning.value = true
  try {
    const body = { path: props.currentPath, ignore_patterns: parsePatterns() }
    const res = props.source === 'cd2'
      ? await cd2Api.cleanEmptyDirs(body)
      : await organizerApi.cleanEmptyDirs(body)
    const data = extractPayload(res)
    if (data?.success === false) throw new Error(data?.message || '清理失败')
    const deleted = data?.count || 0
    const failed = data?.failed || []
    if (deleted > 0 && failed.length > 0) {
      warning(`已删除 ${deleted} 个空文件夹，${failed.length} 个失败被跳过`)
    } else if (deleted > 0) {
      success(`已删除 ${deleted} 个空文件夹`)
    } else {
      info('没有可清理的空文件夹')
    }
    if (deleted > 0) emit('cleaned')
    emit('update:modelValue', false)
  } catch (e: any) {
    showError(e?.message || '清理失败')
  } finally {
    cleaning.value = false
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
    :max-width="640"
    title="清理空文件夹"
    icon="mdi-delete-sweep"
  >
    <v-alert type="info" variant="tonal" density="compact" class="mb-4">
      点击"开始扫描"后，将递归扫描当前目录下的子文件夹，仅删除"实际为空"的文件夹；当前目录本身不会被删除。
      <template v-if="source === 'cd2'">
        云端扫描逐目录请求，子目录多时较慢。
      </template>
    </v-alert>

    <v-textarea
      v-model="patternsText"
      label="自定义忽略规则（每行一条通配符，如 *.png.zip）"
      rows="4"
      auto-grow
      density="compact"
      variant="outlined"
      persistent-hint
      hint="内置规则始终生效：.DS_Store、Thumbs.db、@eaDir、._* 开头的文件；匹配的文件将随所在文件夹一并删除"
      class="mb-3"
    />

    <div class="d-flex align-center ga-2 mb-2">
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
        prepend-icon="mdi-restore"
        :disabled="patternsText === DEFAULT_PATTERNS"
        @click="resetPatterns"
      >
        恢复默认规则
      </v-btn>
      <span v-if="hasScanned && !scanning" class="text-body-2 text-medium-emphasis">
        发现 {{ scanCount }} 个可清理的空文件夹
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
        <v-list density="compact" class="py-0" v-if="scanCount > 0">
          <v-list-item v-for="item in scanItems" :key="item.path">
            <template #prepend>
              <v-icon size="18" color="warning">mdi-folder-remove-outline</v-icon>
            </template>
            <v-list-item-title class="text-body-2 text-wrap">{{ displayPath(item.path) }}</v-list-item-title>
            <v-list-item-subtitle v-if="item.junk_files?.length" class="text-caption text-wrap">
              将一并删除：{{ item.junk_files.join('、') }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
        <div v-else class="text-center text-body-2 text-medium-emphasis pa-4">
          {{ hasScanned ? (scanFailed ? '扫描失败' : '没有发现可清理的空文件夹') : '点击"开始扫描"查看结果' }}
        </div>
      </template>
    </div>

    <template #actions>
      <v-spacer />
      <v-btn
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-sweep"
        :disabled="!hasScanned || scanCount === 0 || scanning"
        :loading="cleaning"
        @click="doClean"
      >
        删除 {{ scanCount }} 个文件夹
      </v-btn>
    </template>
  </GlassDialog>
</template>

<style scoped>
.scan-list {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
}
</style>
