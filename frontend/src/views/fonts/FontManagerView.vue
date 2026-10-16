<script setup lang="ts">
/**
 * FontManagerView — 字体管家
 *
 * 独立页面，对标后端 /api/font_manager（assfonts 的网页封装）:
 * - 顶部状态条：assfonts 版本/来源、参数帮助（内核 -h）、检查更新、索引状态、字体库路径、库目录警告
 * - 未配置字体库时展示引导卡片（FolderBrowserModal 选目录 → 保存 → 自动重建索引）
 * - 拖拽上传：支持 ASS/SSA 字幕（多选）与整个文件夹（webkitGetAsEntry 递归收集）→ 按模式处理
 * - 工具栏处理模式选择器：选项来自 /status 的 modes，切换即持久化到 /config
 * - 任务列表：状态、模式标签、引用/缺失字体、成品大小、耗时、执行/重试/多交付物下载/删除、批量操作
 * - 字体库面板：索引内字体列表（格式分布 + 搜索 + 格式筛选）+ 上传字体到库（永久入库）
 * - 临时字体卡片：上传/拖拽临时字体，仅作为内核 -f 补充源，不入库，可单删/清空
 * - 设置对话框：字体来源 / 处理模式 / 处理方式 / 内核与网络
 * - 参数帮助对话框：内核 -h 原文 + 内核参数 → 本页位置对照表
 * - 有任务处于 running 时每 1.5s 轮询任务列表
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { fontManagerApi } from '@/api'
import { jobDownloadName } from '@/api/fontManager'
import type {
  FontBinaryHelp,
  FontDownloadKind,
  FontFace,
  FontJob,
  FontJobStatus,
  FontManagerConfig,
  FontManagerStatus,
  FontModeOption,
  FontSubsetSummary,
  FontUpdateInfo,
  TempFontFile,
  TempFontState,
} from '@/api/fontManager'
import { useNotification, useConfirm, useClipboard, formatDbSize } from '@/composables'
import { EmptyState, DialogTitle } from '@/components/common'
import FolderBrowserModal from '@/views/organizer/FolderBrowserModal.vue'

defineOptions({ name: 'FontManagerView' })

const { success, error: showError, warning, info: showInfo } = useNotification()
const { confirm } = useConfirm()
const { copy } = useClipboard()

/** 字体文件后缀（上传字体库 / 临时字体时使用） */
const FONT_ACCEPT = '.ttf,.otf,.ttc,.otc,.woff,.woff2'
const FONT_RE = /\.(ttf|otf|ttc|otc|woff|woff2)$/i

// ── 状态总览 ──────────────────────────────────────────────
const status = ref<FontManagerStatus | null>(null)
const statusLoading = ref(false)

const binary = computed(() => status.value?.binary ?? null)
const indexInfo = computed(() => status.value?.index ?? null)
const libraryInfo = computed(() => status.value?.library ?? null)
const jobCounts = computed(() => status.value?.jobs ?? null)
/** 后端合并后的当前生效选项 */
const runOptions = computed(() => status.value?.options ?? null)
/** 全部字体库目录（主目录 + 额外目录） */
const libraryPaths = computed<string[]>(() => {
  const paths = libraryInfo.value?.paths
  if (paths && paths.length) return paths
  return libraryInfo.value?.path ? [libraryInfo.value.path] : []
})
/** 后端给出的字体库/输出相关警告 */
const libraryWarnings = computed<string[]>(() => libraryInfo.value?.warnings ?? [])

/** 当前生效处理参数的可读摘要（状态条 tooltip） */
const effectiveOptionsText = computed(() => {
  const o = runOptions.value
  if (!o) return ''
  const lines = [
    `模式：${o.mode_label}`,
    `交付物：${o.output_kind === 'zip' ? '字体包 zip' : '字幕 .ass'}`,
    `重命名字体：${o.rename ? '开' : '关'}`,
    `HDR 亮度：${o.hdr_luminance || 0}`,
    `内核线程：${o.threads || 0}`,
    `日志级别：${o.verbose}`,
    `保留子集字体：${o.keep_subset_dir ? '开' : '关'}`,
    `删除源字幕副本：${o.delete_source ? '开' : '关'}`,
  ]
  if (o.extra_font_dir) lines.push(`额外字体目录 (-f)：${o.extra_font_dir}`)
  if (o.output_dir) lines.push(`输出目录 (-o)：${o.output_dir}`)
  if (o.extra_font_dirs.length) lines.push(`本次 -f 字体源：${o.extra_font_dirs.join('、')}`)
  const temp = status.value?.temp_fonts
  if (temp?.active) lines.push(`临时字体：${temp.count} 个（自动作为 -f 补充源）`)
  return lines.join('\n')
})

/** 是否已设置字体库目录 */
const hasLibrary = computed(() => !!libraryInfo.value?.path)
/** 索引是否可用（存在且非空） */
const indexReady = computed(() => !!indexInfo.value?.exists && (indexInfo.value?.count ?? 0) > 0)

// ── 处理模式（数据源为 /status 的 modes，不硬编码） ────────
const modeOptions = computed<FontModeOption[]>(() => status.value?.modes ?? [])
/** 当前选中的处理模式（工具栏与设置对话框共用） */
const selectedMode = ref<string>('')
/** 已持久化到后端的模式（用于判断切换是否真的需要写配置） */
const persistedMode = ref<string>('')
const modeSaving = ref(false)
/** 用户是否手动选过模式（选过后轮询不再回滚选择） */
const modeUserPicked = ref(false)

/** 取模式名（用于提示文案） */
function modeLabel(value: string): string {
  return modeOptions.value.find((m) => m.value === value)?.label || value
}

/** 取模式说明（用于 tooltip） */
function modeDescription(value: string): string {
  return modeOptions.value.find((m) => m.value === value)?.description || ''
}

const currentMode = computed<FontModeOption | null>(
  () => modeOptions.value.find((m) => m.value === selectedMode.value) || null,
)

/** 当前模式说明；合并子集化额外补充批量建议 */
const currentModeDescription = computed(() => {
  const m = currentMode.value
  if (!m) return ''
  const extra =
    m.value === 'combined_subset'
      ? ' 会先把所有待处理字幕的字体合并成一份，再一次处理；建议一次批量处理多个字幕。'
      : ''
  return `${m.description || ''}${extra}`
})

// 后端返回生效模式后同步到选择器（用户手动选择过则以本地为准）
watch(
  () => status.value?.options?.mode,
  (m) => {
    if (!m) return
    persistedMode.value = m
    if (!modeUserPicked.value || !selectedMode.value) selectedMode.value = m
  },
  { immediate: true },
)

/** 切换处理模式：立即持久化到 /config，失败只提示不回滚、不阻断 */
async function onModeChange(value: string | null) {
  const mode = String(value || '')
  // v-model 已先更新 selectedMode，这里与「已持久化的值」比较才知道是否真的变了
  if (!mode || mode === persistedMode.value) return
  const prev = persistedMode.value
  selectedMode.value = mode
  modeUserPicked.value = true
  persistedMode.value = mode
  modeSaving.value = true
  try {
    const res = await fontManagerApi.updateConfig({ mode })
    if (res?.data?.mode) {
      persistedMode.value = res.data.mode
      selectedMode.value = res.data.mode
    }
    await fetchStatus(true)
    success(`处理模式已切换为「${modeLabel(selectedMode.value)}」`)
  } catch (e: any) {
    // 回滚「已持久化」标记，本次操作仍使用所选模式；用户再选一次可重试
    persistedMode.value = prev
    showError(`${e?.message || '保存处理模式失败'}（本次操作仍会使用所选模式）`)
  } finally {
    modeSaving.value = false
  }
}

// ── 任务列表 ──────────────────────────────────────────────
const jobs = ref<FontJob[]>([])
const jobsTotal = ref(0)
const jobsLoading = ref(false)
const jobStatusFilter = ref<string>('')
const jobSearch = ref('')
const busyIds = ref<Record<string, boolean>>({})
/** 引用字体 chips 展开状态（>3 时折叠） */
const fontsExpanded = ref<Record<string, boolean>>({})
const batchRunning = ref(false)
const downloadingAll = ref(false)
const clearingJobs = ref(false)
const clearingAllJobs = ref(false)

const statusFilterItems = [
  { title: '全部状态', value: '' },
  { title: '待处理', value: 'pending' },
  { title: '处理中', value: 'running' },
  { title: '已完成', value: 'success' },
  { title: '缺字体', value: 'missing' },
  { title: '失败', value: 'failed' },
  { title: '已跳过', value: 'skipped' },
]

const STATUS_META: Record<FontJobStatus, { label: string; color: string; icon: string }> = {
  pending: { label: '待处理', color: 'grey', icon: 'mdi-clock-outline' },
  running: { label: '处理中', color: 'info', icon: 'mdi-progress-clock' },
  success: { label: '已完成', color: 'success', icon: 'mdi-check-circle-outline' },
  missing: { label: '缺字体', color: 'warning', icon: 'mdi-alert-outline' },
  failed: { label: '失败', color: 'error', icon: 'mdi-close-circle-outline' },
  skipped: { label: '已跳过', color: 'grey', icon: 'mdi-debug-step-over' },
}

function statusMeta(s: FontJobStatus) {
  return STATUS_META[s] || STATUS_META.failed
}

/** 任务模式标签（任务自带 mode_label，兜底查 modes） */
function jobModeLabel(job: FontJob): string {
  return job.mode_label || modeLabel(job.mode || '')
}

/** 下载按钮文案：按交付物类型区分 */
function downloadLabel(job: FontJob): string {
  return job.output_kind === 'zip' ? '下载字体包' : '下载字幕'
}

/** 主成品之外的附加交付物（子集字体包 / 清理版字幕） */
interface DownloadExtra {
  kind: FontDownloadKind
  title: string
  icon: string
}

/**
 * 可下载的附加交付物：
 * - subset：保留了 _subsetted 目录且主成品不是字体包时才需要（交付物相同的场景不重复列出）
 * - cleaned：附带生成了 x.cleaned.ass 且与主成品不是同一个文件时才列出
 */
function extraDownloads(job: FontJob): DownloadExtra[] {
  if (job.status !== 'success') return []
  const list: DownloadExtra[] = []
  if (job.has_subset_dir && job.output_kind !== 'zip') {
    list.push({ kind: 'subset', title: '下载子集字体包', icon: 'mdi-folder-zip-outline' })
  }
  if (job.cleaned_name && job.cleaned_name !== job.output_name) {
    list.push({ kind: 'cleaned', title: '下载清理版字幕', icon: 'mdi-file-remove-outline' })
  }
  return list
}

function downloadHint(kind: FontDownloadKind): string {
  if (kind === 'subset') return '已开始下载子集字体包'
  if (kind === 'cleaned') return '已开始下载清理版字幕'
  return '已开始下载成品'
}

const MAX_VISIBLE_FONTS = 3

function visibleFonts(job: FontJob): string[] {
  if (fontsExpanded.value[job.job_id]) return job.referenced_fonts
  return job.referenced_fonts.slice(0, MAX_VISIBLE_FONTS)
}

function hiddenFontCount(job: FontJob): number {
  if (fontsExpanded.value[job.job_id]) return 0
  return Math.max(0, job.referenced_fonts.length - MAX_VISIBLE_FONTS)
}

function toggleFonts(jobId: string) {
  fontsExpanded.value = { ...fontsExpanded.value, [jobId]: !fontsExpanded.value[jobId] }
}

// ── 轮询（有任务 running 时每 1.5s 刷新） ─────────────────
let pollTimer: ReturnType<typeof setInterval> | null = null
const runningCount = computed(() => jobs.value.filter((j) => j.status === 'running').length)

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(runningCount, (n) => {
  if (n > 0 && !pollTimer) {
    pollTimer = setInterval(() => {
      fetchJobs(true)
      fetchStatus(true)
    }, 1500)
  } else if (n === 0) {
    stopPolling()
  }
})

// ── 请求 ──────────────────────────────────────────────────
async function fetchStatus(silent = false) {
  if (!silent) statusLoading.value = true
  try {
    status.value = await fontManagerApi.getStatus()
  } catch (e: any) {
    if (!silent) showError(e?.message || '读取字体管家状态失败')
  } finally {
    if (!silent) statusLoading.value = false
  }
}

async function fetchJobs(silent = false) {
  if (!silent) jobsLoading.value = true
  try {
    const res = await fontManagerApi.listJobs({
      status: jobStatusFilter.value || undefined,
      q: jobSearch.value.trim() || undefined,
      limit: 200,
      offset: 0,
    })
    jobs.value = res?.data || []
    jobsTotal.value = res?.total || 0
  } catch (e: any) {
    if (!silent) showError(e?.message || '读取任务列表失败')
  } finally {
    if (!silent) jobsLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([fetchStatus(), fetchJobs()])
  if (fontsPanelOpen.value) await fetchFonts()
}

// ── 上传（拖拽 / 点击选择） ───────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)
const uploading = ref(false)
/** 正在递归收集拖入文件夹中的字幕文件 */
const collecting = ref(false)

const SUBTITLE_RE = /\.(ass|ssa)$/i

function pickFiles() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  if (list.length) handleUpload(list)
  input.value = ''
}

function onDragEnter() {
  dragActive.value = true
}

function onDragLeave(e: DragEvent) {
  const related = e.relatedTarget as Node | null
  const current = e.currentTarget as HTMLElement | null
  if (related && current && current.contains(related)) return
  dragActive.value = false
}

// ── 拖拽（支持文件与文件夹递归收集） ──────────────────────
/** 拖拽项的最小接口（File System 草案，浏览器实现为 webkitGetAsEntry） */
interface DroppedEntryReader {
  readEntries: (cb: (entries: DroppedEntry[]) => void, err?: (error: unknown) => void) => void
}
interface DroppedEntry {
  isFile: boolean
  isDirectory: boolean
  file?: (cb: (file: File) => void, err?: (error: unknown) => void) => void
  createReader?: () => DroppedEntryReader
}
interface DataTransferItemWithEntry {
  webkitGetAsEntry?: () => DroppedEntry | null
}

/** 单次拖拽最多收集的字幕文件数（防御性上限，避免拖入超大目录卡住） */
const MAX_DROP_FILES = 1000

/** 收集结果：文件列表 + 是否遇到过文件夹（用于给出更准确的提示） */
interface DroppedCollectResult {
  files: File[]
  sawDirectory: boolean
  truncated: boolean
}

function entryToFile(entry: DroppedEntry): Promise<File | null> {
  return new Promise((resolve) => {
    if (!entry.file) {
      resolve(null)
      return
    }
    entry.file(
      (file) => resolve(file),
      () => resolve(null),
    )
  })
}

/** readEntries 单次不保证返回全部，需要循环读到空数组为止 */
function readAllEntries(reader: DroppedEntryReader): Promise<DroppedEntry[]> {
  const all: DroppedEntry[] = []
  return new Promise((resolve) => {
    const step = () => {
      reader.readEntries(
        (entries) => {
          if (!entries.length) {
            resolve(all)
            return
          }
          all.push(...entries)
          step()
        },
        () => resolve(all),
      )
    }
    step()
  })
}

async function collectEntry(
  entry: DroppedEntry,
  result: DroppedCollectResult,
  pattern: RegExp,
): Promise<void> {
  if (result.files.length >= MAX_DROP_FILES) {
    result.truncated = true
    return
  }
  if (entry.isFile) {
    const file = await entryToFile(entry)
    if (file && pattern.test(file.name)) result.files.push(file)
    return
  }
  if (entry.isDirectory && entry.createReader) {
    result.sawDirectory = true
    const children = await readAllEntries(entry.createReader())
    for (const child of children) {
      if (result.files.length >= MAX_DROP_FILES) {
        result.truncated = true
        return
      }
      await collectEntry(child, result, pattern)
    }
  }
}

/** 优先用 webkitGetAsEntry 递归收集（支持文件夹），不可用时退回 dataTransfer.files */
async function collectDroppedFiles(
  e: DragEvent,
  pattern: RegExp,
): Promise<DroppedCollectResult | null> {
  const dt = e.dataTransfer
  if (!dt) return null
  const items = Array.from(dt.items || [])
  const entries: DroppedEntry[] = []
  for (const item of items) {
    if (item.kind !== 'file') continue
    const entry = (item as unknown as DataTransferItemWithEntry).webkitGetAsEntry?.()
    if (entry) entries.push(entry)
  }
  if (!entries.length) return null // 交由调用方走 dataTransfer.files 降级

  const result: DroppedCollectResult = { files: [], sawDirectory: false, truncated: false }
  for (const entry of entries) {
    if (result.files.length >= MAX_DROP_FILES) {
      result.truncated = true
      break
    }
    await collectEntry(entry, result, pattern)
  }
  return result
}

async function onDrop(e: DragEvent) {
  dragActive.value = false
  const dt = e.dataTransfer
  if (!dt) return

  collecting.value = true
  try {
    const collected = await collectDroppedFiles(e, SUBTITLE_RE)
    if (!collected) {
      // 降级：部分浏览器/非 HTTPS 环境没有 webkitGetAsEntry，此时无法读取文件夹
      const list = Array.from(dt.files || [])
      if (list.length) await handleUpload(list)
      return
    }
    if (collected.truncated) {
      warning(`拖入的文件过多，仅收集前 ${MAX_DROP_FILES} 个字幕文件`)
    }
    if (!collected.files.length) {
      warning(
        collected.sawDirectory
          ? '该文件夹内没有找到 .ass / .ssa 字幕'
          : '没有找到 .ass / .ssa 字幕文件',
      )
      return
    }
    await handleUpload(collected.files)
  } catch (err: any) {
    showError(err?.message || '读取拖入内容失败')
  } finally {
    collecting.value = false
  }
}

async function handleUpload(files: File[]) {
  const valid = files.filter((f) => SUBTITLE_RE.test(f.name))
  const ignored = files.length - valid.length
  if (ignored > 0) showError(`已忽略 ${ignored} 个非字幕文件（仅支持 .ass / .ssa）`)
  if (!valid.length) return

  uploading.value = true
  try {
    const res = await fontManagerApi.upload(valid)
    const created = res?.data || []
    const skipped = res?.skipped || []
    if (skipped.length) {
      showError(`跳过 ${skipped.length} 个文件：${skipped.map((s) => `${s.filename}（${s.reason}）`).join('；')}`)
    }
    if (created.length) {
      success(`已上传 ${created.length} 个字幕，可点击「执行」或「全部子集化」开始子集化`)
    }
    await Promise.all([fetchJobs(), fetchStatus()])
  } catch (e: any) {
    showError(e?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

// ── 页面级拖拽兜底 ────────────────────────────────────────
// 原先只有「虚线上传卡片」是有效放置目标：拖到卡片以外的任何位置都毫无反应，
// 很容易被误认为"拖拽坏了"。这里把整页都变成可放置区域，并在页面上给出明确指引。
function onPageDragEnter(e: DragEvent) {
  const types = Array.from(e.dataTransfer?.types || [])
  if (types.includes('Files')) dragActive.value = true
}

function onPageDragLeave(e: DragEvent) {
  const related = e.relatedTarget as Node | null
  const current = e.currentTarget as HTMLElement | null
  if (related && current && current.contains(related)) return
  dragActive.value = false
}

async function onPageDrop(e: DragEvent) {
  dragActive.value = false
  // 上传卡片 / 临时字体卡片已经处理过（它们调用过 preventDefault），此处不重复处理
  if (e.defaultPrevented) return
  if (!hasLibrary.value) {
    warning('请先选择字体库文件夹，之后才能拖入字幕处理')
    return
  }
  const dt = e.dataTransfer
  if (!dt) return
  collecting.value = true
  try {
    const collected = await collectDroppedFiles(e, SUBTITLE_RE)
    const files = collected ? collected.files : Array.from(dt.files || [])
    const subtitleFiles = files.filter((f) => SUBTITLE_RE.test(f.name))
    if (subtitleFiles.length) {
      await handleUpload(subtitleFiles)
      return
    }
    const fontFiles = files.filter((f) => FONT_RE.test(f.name))
    if (fontFiles.length) {
      warning(
        `检测到 ${fontFiles.length} 个字体文件：请拖到下方「临时字体」卡片，` +
          '或用字体库面板的「上传字体到库 / 选择文件夹」按钮',
      )
      return
    }
    warning('没有找到 .ass / .ssa 字幕文件')
  } catch (err: any) {
    showError(err?.message || '读取拖入内容失败')
  } finally {
    collecting.value = false
  }
}

// ── 任务操作 ──────────────────────────────────────────────
async function runJob(job: FontJob) {
  busyIds.value = { ...busyIds.value, [job.job_id]: true }
  try {
    const res = await fontManagerApi.runJob(job.job_id, selectedMode.value || undefined)
    const updated = res?.data
    if (updated?.status === 'skipped') {
      warning(`「${job.filename}」已跳过：${updated.error || '该字幕无需处理'}`)
    }
    await Promise.all([fetchJobs(true), fetchStatus(true)])
  } catch (e: any) {
    showError(e?.message || '处理失败')
    await fetchJobs(true)
  } finally {
    busyIds.value = { ...busyIds.value, [job.job_id]: false }
  }
}

async function runAll() {
  const targets =
    (jobCounts.value?.pending || 0) + (jobCounts.value?.missing || 0) + (jobCounts.value?.failed || 0)
  const mode = selectedMode.value || undefined
  const ok = await confirm({
    title: '全部子集化',
    content: `将按「${modeLabel(selectedMode.value)}」依次执行全部待处理、缺字体与失败的任务（约 ${targets} 个），期间会占用 CPU 且可能耗时较久。是否继续？`,
    confirmColor: 'primary',
  })
  if (!ok) return
  batchRunning.value = true
  try {
    const res = await fontManagerApi.runAll(true, mode)
    const s: FontSubsetSummary = res?.summary || { total: 0, success: 0, missing: 0, failed: 0, skipped: 0 }
    if (!s.total) {
      showInfo(res?.message || '没有待处理的任务')
    } else {
      const parts = [`成功 ${s.success}`, `缺字体 ${s.missing}`, `失败 ${s.failed}`]
      if (s.skipped) parts.push(`跳过 ${s.skipped}`)
      success(`全部子集化完成（${res?.mode_label || modeLabel(selectedMode.value)}）：${parts.join(' / ')}`)
    }
    await Promise.all([fetchJobs(), fetchStatus()])
  } catch (e: any) {
    showError(e?.message || '批量执行失败')
    await fetchJobs()
  } finally {
    batchRunning.value = false
  }
}

async function downloadJob(job: FontJob, kind: FontDownloadKind = 'main') {
  busyIds.value = { ...busyIds.value, [job.job_id]: true }
  try {
    await fontManagerApi.downloadJob(job, kind)
    success(downloadHint(kind))
  } catch (e: any) {
    showError(e?.message || '下载失败')
  } finally {
    busyIds.value = { ...busyIds.value, [job.job_id]: false }
  }
}

async function downloadAll() {
  if (!jobCounts.value?.success) {
    warning('暂无可下载的成品')
    return
  }
  downloadingAll.value = true
  try {
    await fontManagerApi.downloadAllJobs()
    success('已开始打包下载全部成品')
  } catch (e: any) {
    showError(e?.message || '打包下载失败')
  } finally {
    downloadingAll.value = false
  }
}

async function removeJob(job: FontJob) {
  const ok = await confirm({
    title: '删除任务',
    content: `将删除「${job.filename}」的任务记录及其工作目录（含已生成的成品）。是否继续？`,
    confirmText: '删除',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await fontManagerApi.deleteJob(job.job_id)
    success('任务已删除')
    await Promise.all([fetchJobs(), fetchStatus()])
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

/** 清理「已完成」：只清 success + skipped，保留缺字体 / 失败 / 待处理 */
async function clearJobs() {
  const ok = await confirm({
    title: '清理已完成',
    content:
      '将删除全部已完成（success）与已跳过（skipped）的任务记录与工作目录；待处理、缺字体、失败的任务会保留。是否继续？',
    confirmText: '清理',
    confirmColor: 'warning',
  })
  if (!ok) return
  clearingJobs.value = true
  try {
    const res = await fontManagerApi.clearJobs({ keepFailed: true, includePending: false })
    success(`已清理 ${res?.removed ?? 0} 个已完成任务`)
    await Promise.all([fetchJobs(), fetchStatus()])
  } catch (e: any) {
    showError(e?.message || '清理失败')
  } finally {
    clearingJobs.value = false
  }
}

/** 清空全部：连同待处理 / 缺字体 / 失败一起清除（running 不会被清） */
async function clearAllJobs() {
  const total = jobCounts.value?.total ?? 0
  const ok = await confirm({
    title: '清空全部任务',
    content: `将清除全部 ${total} 条任务记录，成品文件也会一并删除，且不可恢复。正在处理中的任务不会被清除。是否继续？`,
    confirmText: '清空全部',
    confirmColor: 'error',
  })
  if (!ok) return
  clearingAllJobs.value = true
  try {
    const res = await fontManagerApi.clearJobs({ keepFailed: false, includePending: true })
    success(`已清空 ${res?.removed ?? 0} 条任务记录`)
    await Promise.all([fetchJobs(), fetchStatus()])
  } catch (e: any) {
    showError(e?.message || '清空任务失败')
  } finally {
    clearingAllJobs.value = false
  }
}

// ── 索引重建 ──────────────────────────────────────────────
const rebuilding = ref(false)

async function rebuildIndex() {
  rebuilding.value = true
  try {
    const res = await fontManagerApi.rebuildIndex()
    success(res?.message || '字体索引已重建')
    await fetchStatus()
    if (fontsPanelOpen.value) await fetchFonts()
  } catch (e: any) {
    showError(e?.message || '索引重建失败')
  } finally {
    rebuilding.value = false
  }
}

// ── 目录选择（复用 FolderBrowserModal，含多个目标） ───────
type FolderTarget =
  | { type: 'library' }
  | { type: 'settings-library' }
  | { type: 'extra-library'; index: number }
  | { type: 'extra-font' }
  | { type: 'output' }

const showFolderBrowser = ref(false)
const folderTarget = ref<FolderTarget>({ type: 'library' })
const librarySaving = ref(false)

const folderTitle = computed(() => {
  switch (folderTarget.value.type) {
    case 'settings-library':
      return '选择字体库目录'
    case 'extra-library':
      return '选择额外字体库目录'
    case 'extra-font':
      return '选择额外字体目录 (-f)'
    case 'output':
      return '选择输出目录 (-o)'
    default:
      return '选择字体库文件夹'
  }
})

const folderInitial = computed(() => {
  const target = folderTarget.value
  switch (target.type) {
    case 'library':
      return libraryInfo.value?.path || '/'
    case 'settings-library':
      return configForm.value.library_dir || '/'
    case 'extra-library':
      return configForm.value.extra_library_dirs[target.index] || configForm.value.library_dir || '/'
    case 'extra-font':
      return configForm.value.extra_font_dir || configForm.value.library_dir || '/'
    case 'output':
      return configForm.value.output_dir || configForm.value.workspace_dir || '/'
    default:
      return '/'
  }
})

function openFolderPicker(target: FolderTarget) {
  folderTarget.value = target
  showFolderBrowser.value = true
}

async function onFolderSelected(path: string) {
  const target = folderTarget.value
  if (target.type === 'settings-library') {
    configForm.value.library_dir = path
    return
  }
  if (target.type === 'extra-library') {
    const list = [...configForm.value.extra_library_dirs]
    list[target.index] = path
    configForm.value.extra_library_dirs = list
    return
  }
  if (target.type === 'extra-font') {
    configForm.value.extra_font_dir = path
    return
  }
  if (target.type === 'output') {
    configForm.value.output_dir = path
    return
  }
  // 引导流程：保存字体库 → 自动重建索引 → 刷新
  librarySaving.value = true
  try {
    await fontManagerApi.updateConfig({ library_dir: path })
    success('字体库已设置，正在重建索引…')
    await fetchStatus()
    await rebuildIndex()
  } catch (e: any) {
    showError(e?.message || '设置字体库失败')
  } finally {
    librarySaving.value = false
  }
}

// ── 额外字体库目录列表编辑 ────────────────────────────────
function addExtraLibraryDir() {
  configForm.value.extra_library_dirs = [...configForm.value.extra_library_dirs, '']
}

function removeExtraLibraryDir(index: number) {
  const list = [...configForm.value.extra_library_dirs]
  list.splice(index, 1)
  configForm.value.extra_library_dirs = list
}

function setExtraLibraryDir(index: number, value: string | number | null) {
  const list = [...configForm.value.extra_library_dirs]
  list[index] = value === null || value === undefined ? '' : String(value)
  configForm.value.extra_library_dirs = list
}

// ── 设置对话框 ────────────────────────────────────────────
function defaultConfigForm(): FontManagerConfig {
  return {
    // 字体来源
    library_dir: '',
    extra_library_dirs: [],
    index_dir: '',
    workspace_dir: '',
    // 处理模式与方式
    mode: '',
    extra_font_dir: '',
    output_dir: '',
    rename_fonts: false,
    hdr_luminance: 0,
    internal_threads: 0,
    verbose_level: 3,
    keep_subset_dir: true,
    delete_source: false,
    // 内核
    binary_path: '',
    proxy_for_update: false,
  }
}

const showSettings = ref(false)
const configLoading = ref(false)
const savingConfig = ref(false)
const configForm = ref<FontManagerConfig>(defaultConfigForm())

/** 设置对话框里所选模式的说明（与工具栏共用同一份 modes 数据） */
const configModeDescription = computed(() => {
  const m = modeOptions.value.find((x) => x.value === configForm.value.mode)
  return m?.description || ''
})

/** HDR 亮度：开关 + 数字组合，0 表示关闭 */
const hdrEnabled = computed<boolean>({
  get: () => Number(configForm.value.hdr_luminance) > 0,
  set: (val: boolean) => {
    const cur = Number(configForm.value.hdr_luminance) || 0
    configForm.value.hdr_luminance = val ? (cur > 0 ? cur : 203) : 0
  },
})

/** 内核日志级别：低于 2 时内核不再输出缺字体提示 */
const verboseItems = [
  { title: '3 · 调试输出（默认）', value: 3 },
  { title: '2 · 信息输出', value: 2 },
  { title: '1 · 仅警告', value: 1 },
  { title: '0 · 仅错误', value: 0 },
]

async function openSettings() {
  showSettings.value = true
  configLoading.value = true
  try {
    const res = await fontManagerApi.getConfig()
    const data: Partial<FontManagerConfig> = res?.data || {}
    configForm.value = {
      ...defaultConfigForm(),
      ...data,
      extra_library_dirs: Array.isArray(data.extra_library_dirs) ? [...data.extra_library_dirs] : [],
    }
  } catch (e: any) {
    showError(e?.message || '读取配置失败')
  } finally {
    configLoading.value = false
  }
}

async function saveSettings() {
  savingConfig.value = true
  try {
    const form = configForm.value
    const hdr = Number(form.hdr_luminance) || 0
    const threads = Number(form.internal_threads) || 0
    const verbose = Number(form.verbose_level)
    const payload: Partial<FontManagerConfig> = {
      library_dir: form.library_dir.trim(),
      extra_library_dirs: form.extra_library_dirs.map((d) => d.trim()).filter(Boolean),
      mode: form.mode,
      extra_font_dir: form.extra_font_dir.trim(),
      output_dir: form.output_dir.trim(),
      rename_fonts: form.rename_fonts,
      hdr_luminance: Math.max(0, Math.min(1000, hdr)),
      internal_threads: Math.max(0, Math.min(128, threads)),
      verbose_level: Number.isFinite(verbose) ? Math.max(0, Math.min(3, verbose)) : 3,
      keep_subset_dir: form.keep_subset_dir,
      delete_source: form.delete_source,
      binary_path: form.binary_path.trim(),
      proxy_for_update: form.proxy_for_update,
    }
    const res = await fontManagerApi.updateConfig(payload)
    const data: Partial<FontManagerConfig> = res?.data || {}
    configForm.value = {
      ...defaultConfigForm(),
      ...data,
      extra_library_dirs: Array.isArray(data.extra_library_dirs) ? [...data.extra_library_dirs] : [],
    }
    // 设置里的模式与工具栏选择器保持同步
    if (data.mode) {
      modeUserPicked.value = true
      selectedMode.value = data.mode
      persistedMode.value = data.mode
    }
    success('设置已保存')
    showSettings.value = false
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

// ── 内核更新 ──────────────────────────────────────────────
const checkingUpdate = ref(false)
const applyingUpdate = ref(false)
const updateInfo = ref<FontUpdateInfo | null>(null)

async function checkUpdate() {
  checkingUpdate.value = true
  try {
    const res = await fontManagerApi.checkUpdate()
    const info = res?.data || null
    updateInfo.value = info
    if (info?.error) {
      showError(info.error)
      return
    }
    if (info?.has_update) {
      showInfo(`发现新版本 v${info.latest}，可点击「立即更新」升级内核`)
    } else {
      success(`已是最新版本${info?.current ? ` v${info.current}` : ''}`)
    }
  } catch (e: any) {
    showError(e?.message || '检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

async function applyUpdate() {
  const ok = await confirm({
    title: '更新 assfonts 内核',
    content: `将从 GitHub 下载并替换内置 assfonts${
      updateInfo.value?.latest ? `（最新 v${updateInfo.value.latest}）` : ''
    }，下载期间请勿关闭页面。是否继续？`,
    confirmText: '立即更新',
    confirmColor: 'primary',
  })
  if (!ok) return
  applyingUpdate.value = true
  try {
    const res = await fontManagerApi.applyUpdate({})
    const data = res?.data
    if (data && data.success === false) {
      showError(data.message || '更新失败')
      return
    }
    success(data?.message || 'assfonts 内核已更新')
    updateInfo.value = null
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '更新失败')
  } finally {
    applyingUpdate.value = false
  }
}

// ── 内核参数帮助（-h 原文 + 参数对照表） ──────────────────
const showHelpDialog = ref(false)
const helpLoading = ref(false)
const helpError = ref('')
const binaryHelp = ref<FontBinaryHelp | null>(null)

/** 对话框标题里的内核版本/来源（帮助尚未加载时退回状态条数据） */
const helpVersionText = computed(
  () => binaryHelp.value?.version || binary.value?.version || '未知',
)
const helpSourceText = computed(
  () => binaryHelp.value?.source_label || binary.value?.source_label || '未知来源',
)

/** 静态对照表：内核参数 → 本页位置 */
interface KernelArgMapRow {
  arg: string
  desc: string
  where: string
}

const KERNEL_ARG_MAP: KernelArgMapRow[] = [
  { arg: '-i, --input', desc: '输入字幕', where: '拖拽 / 选择文件上传' },
  { arg: '-o, --output', desc: '输出目录', where: '设置 → 处理方式 → 输出目录' },
  { arg: '-f, --fontpath', desc: '字体目录', where: '设置 → 字体来源（主库 / 额外库）+ 处理方式 → 额外字体目录' },
  { arg: '-b, --build', desc: '建立字体索引', where: '顶部「重建索引」' },
  { arg: '-d, --dbpath', desc: '索引存放目录', where: '设置 → 字体来源 → 索引目录' },
  { arg: '-s, --subset-only', desc: '仅子集化字体', where: '处理模式 → 仅子集化字体' },
  { arg: '-e, --embed-only', desc: '仅嵌入字体', where: '处理模式 → 仅内嵌字体' },
  { arg: '-r, --rename', desc: '重命名子集化字体', where: '设置 → 处理方式 → 重命名字体' },
  { arg: '-l, --luminance', desc: 'HDR 亮度', where: '设置 → 处理方式 → HDR 亮度' },
  { arg: '-m, --multi-thread', desc: '内部线程数', where: '设置 → 处理方式 → 内核内部线程数' },
  { arg: '-c, --font-combined', desc: '合并同名字体', where: '处理模式 → 合并子集化（两阶段）' },
  { arg: '-v, --verbose', desc: '日志级别', where: '设置 → 处理方式 → 内核日志级别' },
  { arg: '-h, --help', desc: '帮助信息', where: '本对话框' },
]

async function openBinaryHelp() {
  showHelpDialog.value = true
  helpLoading.value = true
  helpError.value = ''
  try {
    binaryHelp.value = await fontManagerApi.getBinaryHelp()
  } catch (e: any) {
    binaryHelp.value = null
    helpError.value = e?.message || '读取内核帮助失败'
  } finally {
    helpLoading.value = false
  }
}

async function copyBinaryHelp() {
  await copy(binaryHelp.value?.help || '', '已复制内核帮助原文')
}

// ── 字体库面板 ────────────────────────────────────────────
const fontsPanelOpen = ref(false)
const fonts = ref<FontFace[]>([])
const fontsTotal = ref(0)
const fontsFormats = ref<Record<string, number>>({})
const fontsLoading = ref(false)
const fontsQuery = ref('')
const fontsFormat = ref<string>('')
/** 每次拉取的条数与当前上限（后端 limit 最大 2000） */
const FONTS_PAGE = 500
const FONTS_LIMIT_MAX = 2000
const fontsLimit = ref(FONTS_PAGE)

/** 面板标题上的字体数：直接取索引里的字体库数量，折叠状态下也正确 */
const libraryFontCount = computed(() => indexInfo.value?.library_count ?? 0)

const formatFilterItems = computed(() => {
  const keys = Object.keys(fontsFormats.value).sort()
  return [
    { title: '全部格式', value: '' },
    ...keys.map((k) => ({ title: `${k.toUpperCase()} (${fontsFormats.value[k]})`, value: k })),
  ]
})

async function fetchFonts() {
  fontsLoading.value = true
  try {
    const res = await fontManagerApi.listFonts({
      q: fontsQuery.value.trim() || undefined,
      fmt: fontsFormat.value || undefined,
      scope: 'library',
      limit: fontsLimit.value,
      offset: 0,
    })
    fonts.value = res?.data || []
    fontsTotal.value = res?.total || 0
    fontsFormats.value = res?.formats || {}
  } catch (e: any) {
    showError(e?.message || '读取字体列表失败')
  } finally {
    fontsLoading.value = false
  }
}

/** 加载更多：全量重取（offset=0），上限 2000 */
async function loadMoreFonts() {
  if (fontsLimit.value >= FONTS_LIMIT_MAX) return
  fontsLimit.value = Math.min(FONTS_LIMIT_MAX, fontsLimit.value + FONTS_PAGE)
  await fetchFonts()
}

/** 搜索/筛选变化时把条数上限复位，避免越搜越慢 */
function resetFontsLimit() {
  fontsLimit.value = FONTS_PAGE
}

function toggleFontsPanel() {
  fontsPanelOpen.value = !fontsPanelOpen.value
  // 展开时重新拉取（首屏已预取过，所以不会先闪空表，也不会看到过期数据）
  if (fontsPanelOpen.value) fetchFonts()
}

// ── 上传字体到字体库（永久入库） ──────────────────────────
const libraryFontInput = ref<HTMLInputElement | null>(null)
const libraryFolderInput = ref<HTMLInputElement | null>(null)
const libraryUploading = ref(false)

function pickLibraryFonts() {
  libraryFontInput.value?.click()
}

/** 选择文件夹（webkitdirectory 会连同子目录一起列出文件） */
function pickLibraryFolder() {
  libraryFolderInput.value?.click()
}

function onLibraryFontChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  input.value = ''
  if (list.length) handleLibraryFontUpload(list)
}

function onLibraryFolderChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  // 必须复位，否则再次选择同一个文件夹不会再触发 change
  input.value = ''
  if (list.length) handleLibraryFontUpload(list, '该文件夹内没有找到字体文件')
}

async function handleLibraryFontUpload(
  files: File[],
  emptyHint = `没有可用的字体文件（仅支持 ${FONT_ACCEPT}）`,
) {
  const valid = files.filter((f) => FONT_RE.test(f.name))
  const ignored = files.length - valid.length
  if (ignored > 0) warning(`已忽略 ${ignored} 个非字体文件（仅支持 ${FONT_ACCEPT}）`)
  if (!valid.length) {
    warning(emptyHint)
    return
  }

  libraryUploading.value = true
  try {
    const res = await fontManagerApi.uploadFonts(valid)
    const rows = res?.data || []
    const added = rows.filter((r) => r.action === 'added' || r.action === 'renamed')
    const renamed = rows.filter((r) => r.action === 'renamed')
    const duplicates = rows.filter((r) => r.action === 'duplicate')
    const skipped = res?.skipped || []

    const addedCount = res?.added ?? added.length
    if (addedCount > 0) {
      success(
        `已入库 ${addedCount} 个字体` +
          (renamed.length ? `（其中 ${renamed.length} 个同名另存，未覆盖原文件）` : ''),
      )
    }
    if (res?.index?.message) showInfo(res.index.message)
    if (duplicates.length) showInfo(`${duplicates.length} 个字体已存在（内容相同），已跳过`)
    if (skipped.length) {
      showError(`跳过 ${skipped.length} 个文件：${skipped.map((s) => `${s.filename}（${s.reason}）`).join('；')}`)
    }
    // 索引状态可能已变化，同步刷新任务列表与 /status
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '上传字体到字体库失败')
  } finally {
    libraryUploading.value = false
  }
}

// ── 临时字体池（仅作为内核 -f 补充源，不入库） ─────────────
const tempFontInput = ref<HTMLInputElement | null>(null)
const tempUploading = ref(false)
const tempDragActive = ref(false)
const tempDeleting = ref('')
const clearingTemp = ref(false)

const tempFonts = computed<TempFontState | null>(() => status.value?.temp_fonts ?? null)
const tempFontFiles = computed<TempFontFile[]>(() => tempFonts.value?.files ?? [])
const tempFontActive = computed(() => !!tempFonts.value?.active)

function pickTempFonts() {
  tempFontInput.value?.click()
}

function onTempFontChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  input.value = ''
  if (list.length) handleTempFontUpload(list)
}

function onTempDragEnter() {
  tempDragActive.value = true
}

function onTempDragLeave(e: DragEvent) {
  const related = e.relatedTarget as Node | null
  const current = e.currentTarget as HTMLElement | null
  if (related && current && current.contains(related)) return
  tempDragActive.value = false
}

function onTempDrop(e: DragEvent) {
  tempDragActive.value = false
  void handleTempDrop(e)
}

/** 临时字体拖拽：支持字体文件与整个文件夹（递归收集），只接受字体后缀 */
async function handleTempDrop(e: DragEvent) {
  const dt = e.dataTransfer
  if (!dt) return
  collecting.value = true
  try {
    const collected = await collectDroppedFiles(e, FONT_RE)
    if (!collected) {
      // 降级：没有 webkitGetAsEntry 时无法读取文件夹，只能用 dataTransfer.files
      const list = Array.from(dt.files || [])
      if (list.length) await handleTempFontUpload(list)
      return
    }
    if (collected.truncated) warning(`拖入的文件过多，仅收集前 ${MAX_DROP_FILES} 个字体文件`)
    if (!collected.files.length) {
      warning(collected.sawDirectory ? '该文件夹内没有找到字体文件' : '没有找到字体文件')
      return
    }
    await handleTempFontUpload(collected.files)
  } catch (err: any) {
    showError(err?.message || '读取拖入内容失败')
  } finally {
    collecting.value = false
  }
}

async function handleTempFontUpload(
  files: File[],
  emptyHint = '没有可用的字体文件',
) {
  const valid = files.filter((f) => FONT_RE.test(f.name))
  const ignored = files.length - valid.length
  if (ignored > 0) warning(`已忽略 ${ignored} 个非字体文件（临时字体仅支持 ${FONT_ACCEPT}）`)
  if (!valid.length) {
    warning(emptyHint)
    return
  }

  tempUploading.value = true
  try {
    const res = await fontManagerApi.uploadTempFonts(valid)
    const rows = res?.data || []
    const stored = rows.filter((r) => r.action !== 'duplicate').length || rows.length
    success(`已加入临时字体池 ${stored} 个字体，本次处理会自动作为补充字体源`)
    const skipped = res?.skipped || []
    if (skipped.length) {
      showError(`跳过 ${skipped.length} 个文件：${skipped.map((s) => `${s.filename}（${s.reason}）`).join('；')}`)
    }
    if (res?.temp?.index?.error) showError(`临时字体索引构建失败：${res.temp.index.error}`)
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '上传临时字体失败')
  } finally {
    tempUploading.value = false
  }
}

async function removeTempFont(file: TempFontFile) {
  tempDeleting.value = file.filename
  try {
    await fontManagerApi.deleteTempFont(file.filename)
    success(`已删除临时字体「${file.filename}」`)
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '删除临时字体失败')
  } finally {
    tempDeleting.value = ''
  }
}

async function clearTempFonts() {
  const ok = await confirm({
    title: '清空临时字体',
    content: `将删除临时字体池中的全部 ${tempFontFiles.value.length} 个字体。它们没有写入字体库，清空后缺字体预检与处理会重新缺少这些字体。是否继续？`,
    confirmText: '清空',
    confirmColor: 'warning',
  })
  if (!ok) return
  clearingTemp.value = true
  try {
    const res = await fontManagerApi.deleteTempFont()
    success(`已清空 ${res?.removed?.length ?? 0} 个临时字体`)
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '清空临时字体失败')
  } finally {
    clearingTemp.value = false
  }
}

// ── 格式化 ────────────────────────────────────────────────
function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(1)} ${units[i]}`
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function formatDateTime(value: string | undefined): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ── 筛选与防抖搜索 ────────────────────────────────────────
let jobSearchDebounce: ReturnType<typeof setTimeout> | null = null
watch(jobSearch, () => {
  if (jobSearchDebounce) clearTimeout(jobSearchDebounce)
  jobSearchDebounce = setTimeout(() => fetchJobs(), 400)
})

let fontsSearchDebounce: ReturnType<typeof setTimeout> | null = null
watch(fontsQuery, () => {
  if (fontsSearchDebounce) clearTimeout(fontsSearchDebounce)
  fontsSearchDebounce = setTimeout(() => {
    resetFontsLimit()
    fetchFonts()
  }, 400)
})

watch(jobStatusFilter, () => fetchJobs())
watch(fontsFormat, () => {
  if (fontsPanelOpen.value) {
    resetFontsLimit()
    fetchFonts()
  }
})

// ── 生命周期 ──────────────────────────────────────────────
onMounted(async () => {
  await refreshAll()
  // 预取字体明细，展开面板时不会先闪一下空表；
  // 面板列表本身由 v-if 守卫，折叠时不会把上千行渲染进 DOM
  await fetchFonts()
})

onUnmounted(() => {
  stopPolling()
  if (jobSearchDebounce) clearTimeout(jobSearchDebounce)
  if (fontsSearchDebounce) clearTimeout(fontsSearchDebounce)
})
</script>

<template>
  <v-container
    fluid
    class="pa-4 pa-md-6"
    @dragenter.prevent="onPageDragEnter"
    @dragover.prevent
    @dragleave="onPageDragLeave"
    @drop.prevent="onPageDrop"
  >
    <!-- ══ 顶部状态条 ══ -->
    <v-card class="glass-card mb-4" variant="flat">
      <v-card-text class="pa-4">
        <div class="d-flex align-center flex-wrap ga-3">
          <v-icon color="primary" size="28">mdi-format-font</v-icon>
          <span class="text-h6 font-weight-medium">字体管家</span>

          <v-chip size="small" variant="tonal" :color="binary?.ready ? 'primary' : 'error'">
            <v-progress-circular v-if="statusLoading && !status" indeterminate size="12" width="2" class="mr-1" />
            {{ binary?.ready ? `assfonts v${binary.version || '未知'}` : 'assfonts 不可用' }}
          </v-chip>
          <v-chip v-if="binary?.source_label" size="small" variant="flat" color="grey">
            {{ binary.source_label }}
          </v-chip>

          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-help-circle-outline"
            title="查看当前内核的 -h 帮助，并对照本页覆盖了哪些参数"
            @click="openBinaryHelp"
          >
            参数帮助
          </v-btn>

          <v-chip
            v-if="tempFontActive"
            size="small"
            variant="tonal"
            color="success"
            prepend-icon="mdi-clock-outline"
            title="临时字体池已启用：当前处理会自动把它们作为补充字体源（-f）带上"
          >
            临时字体 {{ tempFonts?.count || 0 }}
          </v-chip>

          <v-btn
            size="small"
            variant="tonal"
            color="info"
            prepend-icon="mdi-cloud-download-outline"
            :loading="checkingUpdate"
            @click="checkUpdate"
          >
            检查更新
          </v-btn>
          <template v-if="updateInfo?.has_update">
            <v-chip size="small" variant="flat" color="success">最新 v{{ updateInfo.latest }}</v-chip>
            <v-btn
              size="small"
              variant="flat"
              color="primary"
              prepend-icon="mdi-download"
              :loading="applyingUpdate"
              @click="applyUpdate"
            >
              立即更新
            </v-btn>
          </template>

          <v-spacer />
          <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="statusLoading" @click="refreshAll">刷新</v-btn>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-cog-outline" @click="openSettings">设置</v-btn>
        </div>

        <v-alert
          v-if="applyingUpdate"
          type="info"
          variant="tonal"
          density="compact"
          class="mt-3"
          icon="mdi-progress-download"
        >
          正在下载更新…
        </v-alert>

        <!-- 索引 / 字体库 摘要行 -->
        <div class="d-flex align-center flex-wrap ga-4 mt-3 text-body-2">
          <span class="d-flex align-center ga-1">
            <v-icon size="16" :color="indexReady ? 'success' : 'warning'">mdi-database-outline</v-icon>
            <template v-if="indexReady">
              索引 {{ indexInfo?.count }} 个字体（{{ indexInfo?.built_at || '未知时间' }}）
            </template>
            <template v-else>尚未构建字体索引</template>
          </span>
          <span class="d-flex align-center ga-1" style="min-width: 0">
            <v-icon size="16" :color="hasLibrary ? 'success' : 'error'">mdi-folder-outline</v-icon>
            <span class="text-truncate" :title="libraryPaths.join('\n')">
              字体库：{{ libraryInfo?.path || '未设置' }}
            </span>
            <v-chip
              v-if="libraryPaths.length > 1"
              size="x-small"
              variant="tonal"
              :title="libraryPaths.join('\n')"
            >
              +{{ libraryPaths.length - 1 }} 个额外目录
            </v-chip>
          </span>
          <v-btn
            v-if="hasLibrary"
            size="x-small"
            :color="indexReady ? undefined : 'warning'"
            :variant="indexReady ? 'text' : 'flat'"
            prepend-icon="mdi-refresh"
            :loading="rebuilding"
            @click="rebuildIndex"
          >
            重建索引
          </v-btn>
          <v-chip
            v-if="runOptions"
            size="x-small"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-tune"
            :title="effectiveOptionsText"
          >
            生效：{{ runOptions.mode_label }}
          </v-chip>
        </div>

        <!-- 红条：未设置字体库 -->
        <v-alert
          v-if="!hasLibrary"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          icon="mdi-folder-alert-outline"
        >
          {{ libraryInfo?.message || '尚未选择字体库文件夹，无法进行字体子集化。' }}
          <template #append>
            <v-btn size="small" color="error" variant="flat" :loading="librarySaving" @click="openFolderPicker({ type: 'library' })">
              选择文件夹
            </v-btn>
          </template>
        </v-alert>
        <!-- 黄条：索引未构建 -->
        <v-alert
          v-else-if="!indexReady"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-3"
          icon="mdi-alert-outline"
        >
          字体索引尚未构建（或索引为空），子集化前需要先建立索引。
          <template #append>
            <v-btn size="small" color="warning" variant="flat" :loading="rebuilding" @click="rebuildIndex">重建索引</v-btn>
          </template>
        </v-alert>

        <v-alert
          v-if="binary && !binary.ready"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          icon="mdi-alert-circle-outline"
        >
          {{ binary.message || 'assfonts 二进制不可用，请检查设置或尝试一键更新' }}
        </v-alert>
        <div v-if="indexInfo?.error" class="text-caption text-error mt-2">{{ indexInfo.error }}</div>

        <!-- 字体库 / 输出目录等警告 -->
        <v-alert
          v-for="(w, i) in libraryWarnings"
          :key="`lib-warn-${i}`"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-3"
          icon="mdi-alert-outline"
        >
          {{ w }}
        </v-alert>

        <!-- 任务统计 -->
        <div class="d-flex flex-wrap ga-2 mt-3">
          <v-chip size="x-small" variant="tonal">共 {{ jobCounts?.total || 0 }}</v-chip>
          <v-chip size="x-small" variant="flat" color="grey">待处理 {{ jobCounts?.pending || 0 }}</v-chip>
          <v-chip size="x-small" variant="flat" color="info">处理中 {{ jobCounts?.running || 0 }}</v-chip>
          <v-chip size="x-small" variant="flat" color="success">已完成 {{ jobCounts?.success || 0 }}</v-chip>
          <v-chip size="x-small" variant="flat" color="warning">缺字体 {{ jobCounts?.missing || 0 }}</v-chip>
          <v-chip size="x-small" variant="flat" color="error">失败 {{ jobCounts?.failed || 0 }}</v-chip>
          <v-chip v-if="jobCounts?.skipped" size="x-small" variant="flat" color="grey">已跳过 {{ jobCounts.skipped }}</v-chip>
        </div>
      </v-card-text>
    </v-card>

    <!-- ══ 未配置字体库：引导卡片 ══ -->
    <v-card v-if="!hasLibrary" class="glass-card" variant="flat">
      <EmptyState
        icon="mdi-folder-search-outline"
        pad="large"
        title="先选择字体库文件夹"
        description="字体管家会用 assfonts 扫描该目录下的字体并建立索引，子集化时只把字幕真正引用到的字体嵌入成品。"
      >
        <template #actions>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-folder-open-outline"
            :loading="librarySaving"
            @click="openFolderPicker({ type: 'library' })"
          >
            选择字体库文件夹
          </v-btn>
        </template>
      </EmptyState>
    </v-card>

    <template v-else>
      <!-- ══ 拖拽上传区 ══ -->
      <v-card
        class="glass-card upload-zone mb-4"
        :class="{ 'upload-zone--active': dragActive, 'upload-zone--busy': uploading || collecting }"
        variant="flat"
        @click="pickFiles"
        @dragenter.prevent="onDragEnter"
        @dragover.prevent="onDragEnter"
        @dragleave.prevent="onDragLeave"
        @drop.prevent="onDrop"
      >
        <v-card-text class="text-center pa-8">
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".ass,.ssa"
            class="d-none"
            @click.stop
            @change="onFileChange"
          />
          <v-progress-circular v-if="uploading || collecting" indeterminate color="primary" size="40" class="mb-2" />
          <v-icon v-else size="52" :color="dragActive ? 'primary' : 'grey-lighten-1'">
            {{ dragActive ? 'mdi-download-circle-outline' : 'mdi-cloud-upload-outline' }}
          </v-icon>
          <div class="text-subtitle-1 mt-2">
            {{ collecting ? '正在收集文件…' : uploading ? '正在上传…' : '拖拽 ASS / SSA 字幕（或整个文件夹）到此处' }}
          </div>
          <div class="text-body-2 text-medium-emphasis mt-1">
            或点击选择文件（支持多选）· 拖入文件夹会递归收集其中的 .ass / .ssa
          </div>
          <div class="text-body-2 text-medium-emphasis mt-1">
            上传后选好处理模式，再点「执行」或「全部子集化」
          </div>
        </v-card-text>
      </v-card>

      <!-- ══ 任务工具条 ══ -->
      <div class="list-toolbar">
        <!-- 第一行：处理模式。带 label 的 v-select 与纯 placeholder 的输入框在
             Vuetify 里视觉基准不同，挤在同一行很难真正对齐，因此单独占一行。 -->
        <div class="mode-row">
          <div class="mode-picker">
            <v-select
              v-model="selectedMode"
              :items="modeOptions"
              item-title="label"
              item-value="value"
              label="处理模式"
              density="compact"
              variant="outlined"
              hide-details
              prepend-inner-icon="mdi-cog-play-outline"
              :menu-props="{ maxWidth: 420 }"
              :loading="modeSaving"
              @update:model-value="onModeChange"
            />
          </div>
          <div
            v-if="currentModeDescription"
            class="mode-hint text-caption text-medium-emphasis"
            :title="currentModeDescription"
          >
            <v-icon size="12" class="mr-1">mdi-information-outline</v-icon>{{ currentModeDescription }}
          </div>
          <div v-else-if="!modeOptions.length" class="mode-hint text-caption text-medium-emphasis">
            模式列表读取中…
          </div>
        </div>

        <!-- 第二行：搜索 / 状态筛选 / 计数 -->
        <div class="list-toolbar__filters">
          <v-text-field
            v-model="jobSearch"
            placeholder="搜索字幕文件名…"
            density="compact"
            variant="outlined"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            class="search-field"
            style="max-width: 280px"
            @click:clear="jobSearch = ''; fetchJobs()"
          />
          <v-select
            v-model="jobStatusFilter"
            :items="statusFilterItems"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 160px"
          />
          <span class="list-toolbar__total">共 {{ jobsTotal }} 个任务</span>
        </div>
        <div class="list-toolbar__actions flex-wrap">
          <v-btn
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-play-circle-outline"
            :loading="batchRunning"
            :title="`按「${modeLabel(selectedMode)}」批量处理`"
            @click="runAll"
          >
            全部子集化
          </v-btn>
          <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-download-multiple-outline" :loading="downloadingAll" @click="downloadAll">
            全部下载
          </v-btn>
          <v-btn
            size="small"
            variant="tonal"
            color="warning"
            prepend-icon="mdi-broom"
            :loading="clearingJobs"
            @click="clearJobs"
          >
            清理已完成
          </v-btn>
          <v-menu location="bottom end">
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                size="small"
                variant="tonal"
                color="warning"
                icon="mdi-chevron-down"
                :disabled="clearingJobs || clearingAllJobs"
                title="更多清理方式"
              />
            </template>
            <v-list density="compact">
              <v-list-item
                prepend-icon="mdi-broom"
                title="清理已完成"
                subtitle="清除成功 / 已跳过的任务，保留缺字体与待处理"
                @click="clearJobs"
              />
              <v-list-item
                prepend-icon="mdi-delete-sweep-outline"
                title="清空全部"
                subtitle="连同待处理、缺字体、失败的任务一起清除"
                base-color="error"
                @click="clearAllJobs"
              />
            </v-list>
          </v-menu>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="jobsLoading" @click="refreshAll">刷新</v-btn>
        </div>
      </div>

      <!-- ══ 任务列表 ══ -->
      <div v-if="jobsLoading && !jobs.length" class="d-flex justify-center pa-8">
        <v-progress-circular indeterminate color="primary" />
      </div>

      <template v-else-if="jobs.length">
        <v-card v-for="job in jobs" :key="job.job_id" class="glass-card mb-3" variant="flat">
          <v-card-text class="pa-4">
            <div class="d-flex align-center flex-wrap ga-2">
              <v-icon :color="statusMeta(job.status).color" size="20">{{ statusMeta(job.status).icon }}</v-icon>
              <span class="text-body-1 font-weight-medium text-truncate" style="max-width: 46%" :title="job.filename">
                {{ job.filename }}
              </span>
              <v-chip size="x-small" variant="flat" :color="statusMeta(job.status).color">
                <v-progress-circular v-if="job.status === 'running'" indeterminate size="10" width="2" class="mr-1" />
                {{ statusMeta(job.status).label }}
              </v-chip>
              <v-chip size="small" variant="tonal" :title="modeDescription(job.mode)">
                {{ jobModeLabel(job) }}
              </v-chip>
              <v-chip v-if="job.has_embedded" size="x-small" variant="tonal" color="info" prepend-icon="mdi-paperclip">
                已内嵌字体
              </v-chip>
              <v-chip
                v-if="job.has_subset_dir"
                size="x-small"
                variant="tonal"
                color="grey"
                prepend-icon="mdi-folder-multiple-outline"
                title="任务目录中保留了 _subsetted 子集字体文件夹"
              >
                已留子集字体
              </v-chip>

              <v-spacer />

              <span v-if="job.output_size" class="text-caption text-medium-emphasis">
                成品 {{ formatFileSize(job.output_size) }}
              </span>
              <span v-if="job.duration_ms" class="text-caption text-medium-emphasis">
                耗时 {{ formatDuration(job.duration_ms) }}
              </span>
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-play"
                :loading="!!busyIds[job.job_id]"
                @click="runJob(job)"
              >
                {{ job.status === 'pending' ? '执行' : '重试' }}
              </v-btn>
              <v-btn
                v-if="job.status === 'success'"
                size="small"
                variant="tonal"
                color="info"
                prepend-icon="mdi-download"
                :disabled="!!busyIds[job.job_id]"
                @click="downloadJob(job)"
              >
                {{ downloadLabel(job) }}
              </v-btn>
              <v-menu v-if="extraDownloads(job).length" location="bottom end">
                <template #activator="{ props: menuProps }">
                  <v-btn
                    v-bind="menuProps"
                    size="small"
                    variant="tonal"
                    color="info"
                    icon="mdi-chevron-down"
                    :disabled="!!busyIds[job.job_id]"
                    title="其它交付物"
                  />
                </template>
                <v-list density="compact">
                  <v-list-item
                    v-for="extra in extraDownloads(job)"
                    :key="extra.kind"
                    :prepend-icon="extra.icon"
                    :title="extra.title"
                    :subtitle="jobDownloadName(job, extra.kind)"
                    @click="downloadJob(job, extra.kind)"
                  />
                </v-list>
              </v-menu>
              <v-btn
                size="small"
                variant="text"
                color="error"
                icon="mdi-delete-outline"
                title="删除任务"
                @click="removeJob(job)"
              />
            </div>

            <!-- 引用字体 / 缺失字体 chips -->
            <div v-if="job.referenced_fonts.length || job.missing_fonts.length" class="d-flex flex-wrap ga-1 mt-3">
              <v-chip v-for="f in visibleFonts(job)" :key="`ref-${f}`" size="x-small" variant="tonal" :title="f">
                {{ f }}
              </v-chip>
              <v-chip
                v-if="hiddenFontCount(job) > 0"
                size="x-small"
                variant="flat"
                color="grey"
                title="展开全部引用字体"
                @click="toggleFonts(job.job_id)"
              >
                +{{ hiddenFontCount(job) }}
              </v-chip>
              <v-chip
                v-else-if="fontsExpanded[job.job_id] && job.referenced_fonts.length > 3"
                size="x-small"
                variant="text"
                title="收起"
                @click="toggleFonts(job.job_id)"
              >
                收起
              </v-chip>

              <v-chip
                v-for="f in job.missing_fonts"
                :key="`miss-${f}`"
                size="x-small"
                variant="flat"
                color="error"
                prepend-icon="mdi-alert-circle-outline"
                :title="`字体库中缺少：${f}`"
              >
                {{ f }}
              </v-chip>
            </div>

            <div
              v-if="job.error"
              class="text-caption mt-2"
              :class="job.status === 'skipped' ? 'text-medium-emphasis' : 'text-error'"
            >
              <v-icon size="12" class="mr-1">{{ job.status === 'skipped' ? 'mdi-debug-step-over' : 'mdi-alert-circle-outline' }}</v-icon>
              {{ job.status === 'skipped' ? `已跳过：${job.error}` : job.error }}
            </div>
            <div class="text-caption text-medium-emphasis mt-2">
              <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>{{ formatDateTime(job.created_at) }}
              <span v-if="job.output_name" class="ml-3">
                <v-icon size="12" class="mr-1">mdi-file-outline</v-icon>{{ job.output_name }}
              </span>
              <span v-if="job.cleaned_name" class="ml-3" :title="`另存文件：${job.cleaned_name}`">
                <v-icon size="12" class="mr-1">mdi-file-remove-outline</v-icon>另存 {{ job.cleaned_name }}
              </span>
            </div>
          </v-card-text>
        </v-card>
      </template>

      <EmptyState
        v-else
        icon="mdi-subtitles-outline"
        title="暂无字幕任务"
        description="拖拽 ASS / SSA 字幕到上方区域，或点击上传区选择文件"
      />

      <!-- ══ 字体库面板（可折叠） ══ -->
      <v-card class="glass-card mt-4" variant="flat">
        <v-card-title class="pa-4 d-flex align-center" style="cursor: pointer" @click="toggleFontsPanel">
          <v-icon start color="primary">mdi-format-list-bulleted-type</v-icon>
          <span class="text-body-1 font-weight-medium">字体库</span>
          <v-chip
            size="x-small"
            variant="tonal"
            class="ml-2"
            title="来自字体索引（点开面板可查看明细）"
          >
            {{ libraryFontCount }} 个字体
          </v-chip>
          <v-spacer />
          <input
            ref="libraryFontInput"
            type="file"
            multiple
            :accept="FONT_ACCEPT"
            class="d-none"
            @click.stop
            @change="onLibraryFontChange"
          />
          <input
            ref="libraryFolderInput"
            type="file"
            webkitdirectory
            multiple
            class="d-none"
            @click.stop
            @change="onLibraryFolderChange"
          />
          <v-btn
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-upload"
            :loading="libraryUploading"
            :disabled="libraryUploading"
            class="mr-2"
            title="把字体永久写入字体库目录，并按设置自动重建索引（不会覆盖同名文件）"
            @click.stop="pickLibraryFonts"
          >
            上传字体到库
          </v-btn>
          <v-btn
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-folder-open-outline"
            :loading="libraryUploading"
            :disabled="libraryUploading"
            class="mr-2"
            title="选择整个文件夹（含子目录）入库，只挑其中的字体文件"
            @click.stop="pickLibraryFolder"
          >
            选择文件夹
          </v-btn>
          <v-icon>{{ fontsPanelOpen ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </v-card-title>

        <template v-if="fontsPanelOpen">
          <v-divider />
          <v-card-text class="pa-4">
            <!-- 格式分布 -->
            <div class="d-flex flex-wrap align-center ga-2 mb-3">
              <v-chip v-for="(cnt, fmt) in fontsFormats" :key="fmt" size="x-small" variant="flat" color="primary">
                {{ String(fmt).toUpperCase() }} · {{ cnt }}
              </v-chip>
              <v-chip size="x-small" variant="tonal">共 {{ fontsTotal }} 个字体面</v-chip>
              <v-chip v-if="indexInfo?.built_at" size="x-small" variant="text">
                索引构建于 {{ indexInfo.built_at }}
              </v-chip>
            </div>

            <!-- 搜索 + 格式筛选 -->
            <div class="d-flex flex-wrap align-center ga-2 mb-3">
              <v-text-field
                v-model="fontsQuery"
                placeholder="搜索字体名 / 文件名…"
                density="compact"
                variant="outlined"
                prepend-inner-icon="mdi-magnify"
                clearable
                hide-details
                class="search-field"
                style="max-width: 300px"
                @click:clear="fontsQuery = ''; resetFontsLimit(); fetchFonts()"
              />
              <v-select
                v-model="fontsFormat"
                :items="formatFilterItems"
                density="compact"
                variant="outlined"
                hide-details
                style="max-width: 180px"
              />
              <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :loading="fontsLoading" @click="fetchFonts">
                刷新列表
              </v-btn>
            </div>

            <v-progress-linear v-if="fontsLoading" indeterminate color="primary" class="mb-3" />

            <v-table v-if="fonts.length" density="compact" class="fonts-table">
              <thead>
                <tr>
                  <th class="text-left">字体名 (family)</th>
                  <th class="text-left">文件名</th>
                  <th class="text-left">格式</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(f, i) in fonts" :key="`${f.filename}-${i}`">
                  <td class="text-body-2">{{ f.family || (f.families && f.families[0]) || '-' }}</td>
                  <td class="text-body-2 font-mono text-truncate" style="max-width: 380px" :title="f.filename">
                    {{ f.filename }}
                  </td>
                  <td>
                    <v-chip size="x-small" variant="tonal">{{ (f.format || 'unknown').toUpperCase() }}</v-chip>
                  </td>
                </tr>
              </tbody>
            </v-table>

            <EmptyState
              v-else-if="!fontsLoading"
              icon="mdi-format-font"
              title="字体库中暂无字体"
              description="确认字体库目录下有 .ttf/.otf/.ttc 字体文件后，点击上方「重建索引」"
            />

            <!-- 条数上限提示 + 加载更多 -->
            <div
              v-if="fontsTotal > fonts.length"
              class="d-flex align-center flex-wrap ga-2 mt-3"
            >
              <span class="text-caption text-medium-emphasis">
                已显示前 {{ fonts.length }} / 共 {{ fontsTotal }} 个字体面（可用上方搜索框按名称查找）
              </span>
              <v-btn
                v-if="fontsLimit < FONTS_LIMIT_MAX"
                size="small"
                variant="text"
                :loading="fontsLoading"
                @click="loadMoreFonts"
              >
                加载更多
              </v-btn>
              <span v-else class="text-caption text-medium-emphasis">
                已达单次上限 {{ FONTS_LIMIT_MAX }} 条，请用搜索缩小范围
              </span>
            </div>
          </v-card-text>
        </template>
      </v-card>

      <!-- ══ 临时字体池（仅处理时作为 -f 补充源，不入库） ══ -->
      <v-card
        class="glass-card mt-4 temp-font-card"
        :class="{ 'temp-font-card--active': tempDragActive, 'temp-font-card--busy': tempUploading || collecting }"
        variant="flat"
        @dragenter.prevent="onTempDragEnter"
        @dragover.prevent="onTempDragEnter"
        @dragleave.prevent="onTempDragLeave"
        @drop.prevent="onTempDrop"
      >
        <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
          <v-icon color="primary">mdi-clock-outline</v-icon>
          <span class="text-body-1 font-weight-medium">临时字体</span>
          <v-chip
            size="x-small"
            variant="flat"
            :color="tempFontActive ? 'success' : 'grey'"
            :title="tempFontActive ? '处理时会作为补充字体源（-f）自动参与' : '临时字体池为空'"
          >
            {{ tempFontActive ? `${tempFonts?.count || 0} 个已启用` : '未使用' }}
          </v-chip>
          <v-spacer />
          <v-btn
            v-if="tempFontFiles.length"
            size="small"
            variant="tonal"
            color="error"
            prepend-icon="mdi-delete-sweep-outline"
            :loading="clearingTemp"
            @click="clearTempFonts"
          >
            清空全部
          </v-btn>
          <input
            ref="tempFontInput"
            type="file"
            multiple
            :accept="FONT_ACCEPT"
            class="d-none"
            @change="onTempFontChange"
          />
          <v-btn
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-upload"
            :loading="tempUploading"
            :disabled="tempUploading"
            title="上传临时字体：只在内核处理时作为 -f 补充源，不会写入字体库"
            @click="pickTempFonts"
          >
            上传临时字体
          </v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <div class="text-caption text-medium-emphasis mb-3" style="line-height: 1.45">
            临时字体只在内核处理时作为补充字体源（<code>-f</code>）使用，<strong>不会写入字体库</strong>；
            上传后立即参与「执行 / 全部子集化」与缺字体预检；不用了可一键清空。
            也可以直接把<strong>字体文件或整个文件夹</strong>拖到本卡片（只接受字体后缀，其它文件会被忽略）。
            字体库入库刻意只保留按钮，避免拖拽误把字体永久写进库里。
          </div>

          <div v-if="collecting" class="d-flex align-center ga-2 text-body-2 mb-2">
            <v-progress-circular indeterminate size="16" width="2" color="primary" />
            正在收集文件…
          </div>

          <div v-if="tempUploading" class="d-flex align-center ga-2 text-body-2 mb-2">
            <v-progress-circular indeterminate size="16" width="2" color="primary" />
            正在上传临时字体…
          </div>

          <v-table v-if="tempFontFiles.length" density="compact" class="temp-fonts-table">
            <thead>
              <tr>
                <th class="text-left">文件名</th>
                <th class="text-left" style="width: 120px">大小</th>
                <th class="text-left" style="width: 90px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in tempFontFiles" :key="f.filename">
                <td class="text-body-2 font-mono text-truncate" style="max-width: 460px" :title="f.filename">
                  {{ f.filename }}
                </td>
                <td class="text-body-2">{{ formatDbSize(f.size) }}</td>
                <td>
                  <v-btn
                    size="x-small"
                    variant="text"
                    color="error"
                    icon="mdi-delete"
                    title="删除该临时字体"
                    :loading="tempDeleting === f.filename"
                    @click="removeTempFont(f)"
                  />
                </td>
              </tr>
            </tbody>
          </v-table>
          <div v-else-if="!tempUploading && !collecting" class="text-caption text-medium-emphasis">暂无临时字体</div>

          <div v-if="tempFonts?.index?.exists" class="text-caption text-medium-emphasis mt-2">
            <v-icon size="12" class="mr-1">mdi-database-outline</v-icon>
            临时字体索引：{{ tempFonts.index.count }} 个 face
            <span v-if="tempFonts.dir" class="ml-2" :title="tempFonts.dir">目录：{{ tempFonts.dir }}</span>
          </div>
          <div v-else-if="tempFonts?.index?.error" class="text-caption text-error mt-2">
            {{ tempFonts.index.error }}
          </div>
        </v-card-text>
      </v-card>
    </template>

    <!-- ══ 设置对话框 ══ -->
    <v-dialog v-model="showSettings" max-width="680" scrollable>
      <v-card class="glass-card">
        <DialogTitle icon="mdi-cog-outline" icon-color="primary" title="字体管家设置" @close="showSettings = false" />
        <v-divider />

        <v-card-text class="pa-4 dialog-scroll-body">
          <v-skeleton-loader v-if="configLoading" type="list-item@6" />

          <template v-else>
            <!-- ── 字体来源 ── -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-folder-outline</v-icon>
              字体来源
            </div>
            <div class="d-flex align-center ga-2 mb-3">
              <v-text-field
                v-model="configForm.library_dir"
                label="字体库目录 (library_dir)"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="存放字体的文件夹，如 /vol1/fonts"
              />
              <v-btn
                variant="tonal"
                color="info"
                prepend-icon="mdi-folder-search-outline"
                @click="openFolderPicker({ type: 'settings-library' })"
              >
                浏览
              </v-btn>
            </div>

            <!-- 额外字体库目录（可增删） -->
            <div class="text-caption text-medium-emphasis mb-1">
              额外字体库目录 (extra_library_dirs)：与主目录一起建立索引、参与缺字体判定
            </div>
            <div
              v-for="(dir, i) in configForm.extra_library_dirs"
              :key="`extra-lib-${i}`"
              class="d-flex align-center ga-2 mb-2"
            >
              <v-text-field
                :model-value="dir"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="额外字体库目录，如 /vol2/fonts"
                @update:model-value="(v: string) => setExtraLibraryDir(i, v)"
              />
              <v-btn
                size="small"
                variant="tonal"
                color="info"
                icon="mdi-folder-search-outline"
                title="选择目录"
                @click="openFolderPicker({ type: 'extra-library', index: i })"
              />
              <v-btn
                size="small"
                variant="text"
                color="error"
                icon="mdi-delete-outline"
                title="删除该目录"
                @click="removeExtraLibraryDir(i)"
              />
            </div>
            <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" class="mb-3" @click="addExtraLibraryDir">
              添加目录
            </v-btn>

            <v-row density="compact" class="mb-1">
              <v-col cols="12" sm="6">
                <v-text-field
                  :model-value="configForm.index_dir"
                  label="索引目录 (index_dir)"
                  variant="outlined"
                  density="compact"
                  hide-details
                  readonly
                  placeholder="由后端自动管理"
                />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model="configForm.workspace_dir"
                  label="任务工作目录 (workspace_dir)"
                  variant="outlined"
                  density="compact"
                  hide-details
                />
              </v-col>
            </v-row>

            <v-divider class="my-3" />
            <!-- ── 处理模式 ── -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-cog-play-outline</v-icon>
              处理模式
            </div>
            <v-select
              v-model="configForm.mode"
              :items="modeOptions"
              item-title="label"
              item-value="value"
              label="默认处理模式 (mode)"
              variant="outlined"
              density="compact"
              hide-details
              class="mb-1"
            />
            <div class="text-caption text-medium-emphasis mb-3" style="line-height: 1.4">
              {{ configModeDescription || '模式列表读取中…' }}
            </div>

            <v-divider class="my-3" />
            <!-- ── 处理方式 ── -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-tune</v-icon>
              处理方式
            </div>

            <div class="d-flex align-center ga-2 mb-1">
              <v-text-field
                v-model="configForm.extra_font_dir"
                label="额外字体目录 (-f)"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="留空 = 仅使用字体库"
              />
              <v-btn
                variant="tonal"
                color="info"
                prepend-icon="mdi-folder-search-outline"
                @click="openFolderPicker({ type: 'extra-font' })"
              >
                浏览
              </v-btn>
              <v-btn
                v-if="configForm.extra_font_dir"
                variant="text"
                color="warning"
                icon="mdi-close"
                title="清空"
                @click="configForm.extra_font_dir = ''"
              />
            </div>
            <div class="text-caption text-medium-emphasis mb-3">
              本次处理额外加载的字体目录，用于「仅内嵌」等需要指定字体来源的场景
            </div>

            <div class="d-flex align-center ga-2 mb-1">
              <v-text-field
                v-model="configForm.output_dir"
                label="输出目录 (-o)"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="留空 = 输出到任务工作目录"
              />
              <v-btn
                variant="tonal"
                color="info"
                prepend-icon="mdi-folder-search-outline"
                @click="openFolderPicker({ type: 'output' })"
              >
                浏览
              </v-btn>
              <v-btn
                v-if="configForm.output_dir"
                variant="text"
                color="warning"
                icon="mdi-close"
                title="清空"
                @click="configForm.output_dir = ''"
              />
            </div>
            <div class="text-caption text-medium-emphasis mb-3">
              留空则输出到任务工作目录；开启后所有成品都放这里
            </div>

            <div class="switch-row mb-2">
              <v-switch v-model="configForm.rename_fonts" color="primary" hide-details density="compact" />
              <div>
                <div class="switch-label">重命名字体 (rename_fonts)</div>
                <div class="text-caption text-medium-emphasis">对应 assfonts -r，避免与系统字体冲突</div>
              </div>
            </div>

            <div class="d-flex align-center flex-wrap ga-3 mb-1">
              <div class="switch-row" style="min-width: 240px">
                <v-switch v-model="hdrEnabled" color="primary" hide-details density="compact" />
                <div>
                  <div class="switch-label">HDR 亮度压暗 (hdr_luminance)</div>
                  <div class="text-caption text-medium-emphasis">关闭 = 0（不处理）</div>
                </div>
              </div>
              <v-text-field
                v-model.number="configForm.hdr_luminance"
                type="number"
                min="0"
                max="1000"
                :disabled="!hdrEnabled"
                variant="outlined"
                density="compact"
                hide-details
                style="max-width: 140px"
              />
            </div>
            <div class="text-caption text-medium-emphasis mb-3">
              对应 assfonts -l，范围 0-1000；开启后默认 203，会给成品名加上 .hdr 后缀
            </div>

            <div class="d-flex align-center flex-wrap ga-3 mb-1">
              <v-text-field
                v-model.number="configForm.internal_threads"
                label="内核内部线程数 (-m)"
                type="number"
                min="0"
                max="128"
                variant="outlined"
                density="compact"
                hide-details
                style="max-width: 220px"
              />
              <div class="text-caption text-medium-emphasis">0 = 内核默认，范围 0-128</div>
            </div>
            <div class="text-caption text-medium-emphasis mb-3">
              过大反而会因上下文切换变慢，一般保持 0 即可
            </div>

            <v-select
              v-model="configForm.verbose_level"
              :items="verboseItems"
              label="内核日志级别 (-v)"
              variant="outlined"
              density="compact"
              hide-details
              class="mb-1"
              style="max-width: 340px"
            />
            <div class="text-caption text-medium-emphasis mb-3" style="line-height: 1.4">
              ⚠️ 低于 2 时内核不再输出缺字体提示，系统会自动改用索引比对兜底判定缺失字体
            </div>

            <div class="switch-row mb-2">
              <v-switch v-model="configForm.keep_subset_dir" color="primary" hide-details density="compact" />
              <div>
                <div class="switch-label">保留子集字体文件夹 (keep_subset_dir)</div>
                <div class="text-caption text-medium-emphasis">保留 _subsetted 目录，便于排查缺失字形</div>
              </div>
            </div>

            <div class="switch-row mb-3">
              <v-switch v-model="configForm.delete_source" color="warning" hide-details density="compact" />
              <div>
                <div class="switch-label">成功后删除上传的源字幕副本 (delete_source)</div>
                <div class="text-caption text-medium-emphasis">⚠️ 删除后无法再次重试该任务</div>
              </div>
            </div>

            <v-divider class="my-3" />
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-cube-outline</v-icon>
              内核与网络
            </div>
            <v-text-field
              v-model="configForm.binary_path"
              label="assfonts 二进制路径 (binary_path)"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="留空 = 自动（data/bin > 镜像内置）"
              class="mb-3"
            />
            <div class="switch-row">
              <v-switch v-model="configForm.proxy_for_update" color="primary" hide-details density="compact" />
              <div>
                <div class="switch-label">更新时走系统代理 (proxy_for_update)</div>
                <div class="text-caption text-medium-emphasis">检查/下载 assfonts 更新时使用系统代理设置</div>
              </div>
            </div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showSettings = false">取消</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-content-save-outline"
            :loading="savingConfig"
            :disabled="configLoading"
            @click="saveSettings"
          >
            保存设置
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ══ 内核参数帮助 ══ -->
    <v-dialog v-model="showHelpDialog" max-width="760" scrollable>
      <v-card class="glass-card">
        <DialogTitle
          icon="mdi-console"
          icon-color="primary"
          :title="`内核参数帮助 · assfonts v${helpVersionText}（${helpSourceText}）`"
          @close="showHelpDialog = false"
        />
        <v-divider />

        <v-card-text class="pa-4">
          <!-- ① 内核原始帮助 -->
          <div class="d-flex justify-center pa-6" v-if="helpLoading">
            <v-progress-circular indeterminate color="primary" />
          </div>

          <v-alert v-else-if="helpError" type="error" variant="tonal" density="compact" icon="mdi-alert-circle-outline">
            {{ helpError }}
          </v-alert>

          <template v-else-if="binaryHelp">
            <pre class="kernel-help">{{ binaryHelp.help || '（内核没有输出帮助内容）' }}</pre>
            <div class="text-caption text-medium-emphasis mt-2" style="line-height: 1.4">
              以上内容直接来自当前内核的 <code>-h</code> 输出 —— 更新内核后会自动同步。
              <span v-if="binaryHelp.path" class="ml-2">内核路径：{{ binaryHelp.path }}</span>
            </div>
          </template>
        </v-card-text>

        <v-divider />

        <!-- ② 内核参数 → 本页位置 对照表 -->
        <v-card-text class="pa-4 pt-3">
          <div class="section-title mb-2">
            <v-icon size="16" color="primary">mdi-table-arrow-down</v-icon>
            内核参数 → 本页位置
          </div>
          <v-table density="compact" class="kernel-args-table">
            <thead>
              <tr>
                <th class="text-left" style="width: 180px">参数</th>
                <th class="text-left" style="width: 130px">作用</th>
                <th class="text-left">在本页的位置</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in KERNEL_ARG_MAP" :key="row.arg">
                <td class="text-body-2 font-mono">{{ row.arg }}</td>
                <td class="text-body-2">{{ row.desc }}</td>
                <td class="text-body-2">{{ row.where }}</td>
              </tr>
            </tbody>
          </v-table>
          <div class="text-caption text-medium-emphasis mt-2" style="line-height: 1.4">
            内核报错退出码恒为 0，本页以「产物是否生成 + 日志文本 + 索引比对」判定成败；
            <code>-v</code> 低于 2 时内核不再输出缺字体提示，本页会自动改用索引比对。
          </div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-content-copy"
            :disabled="!binaryHelp?.help"
            @click="copyBinaryHelp"
          >
            复制帮助原文
          </v-btn>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showHelpDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ══ 目录选择（复用组织器目录浏览弹窗） ══ -->
    <FolderBrowserModal
      v-model="showFolderBrowser"
      via="local"
      mode="dir"
      :title="folderTitle"
      :initial-path="folderInitial"
      @select="onFolderSelected"
    />
  </v-container>
</template>

<style scoped>
/* 拖拽上传区：悬停高亮 + 可点击 */
.upload-zone {
  cursor: pointer;
  border: 2px dashed rgba(var(--v-theme-on-surface), 0.18);
  transition: border-color 0.18s ease, background-color 0.18s ease;
}
.upload-zone:hover {
  border-color: rgba(var(--v-theme-primary), 0.6);
}
.upload-zone--active {
  border-color: rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.08);
}
.upload-zone--busy {
  cursor: progress;
}
/* 处理模式单独一行（.mode-row），下一行才是搜索/状态筛选。
   带 label 的 v-select 和纯 placeholder 的输入框视觉基准不同，同行很难真正对齐。 */
.mode-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.mode-picker {
  width: 280px;
  flex: 0 0 auto;
}
/* 模式说明：占右侧剩余空间，最多两行，悬停看全文 */
.mode-hint {
  flex: 1 1 240px;
  min-width: 0;
  line-height: 1.35;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
@media (max-width: 600px) {
  .mode-picker {
    width: 100%;
  }
}
.fonts-table {
  background: transparent;
}
/* 内核 -h 原文：等宽 + 保留缩进 + 横向滚动 */
.kernel-help {
  margin: 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.45);
  border: var(--am-content-border, 1px solid rgba(var(--v-theme-on-surface), 0.12));
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre;
  tab-size: 4;
  overflow: auto;
  max-height: 42vh;
}
.kernel-args-table {
  background: transparent;
}
/* 临时字体卡片：拖拽高亮（outline 不影响布局） */
.temp-font-card {
  transition: background-color 0.18s ease;
}
.temp-font-card--active {
  outline: 2px dashed rgb(var(--v-theme-primary));
  outline-offset: -6px;
  background-color: rgba(var(--v-theme-primary), 0.06);
}
.temp-font-card--busy {
  cursor: progress;
}
.temp-fonts-table {
  background: transparent;
}
</style>
