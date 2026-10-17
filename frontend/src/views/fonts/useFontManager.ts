/**
 * useFontManager — 字体管家共享状态层
 *
 * 拆分 FontManagerView 时抽出：三个 Tab 子组件（JobsTab / LibraryTab / TempFontsTab）
 * 与主视图共用同一份 status / 配置读写 / 拖拽收集工具 / 通知，全部从这里取。
 * 状态只在这一处创建（主视图调用一次后 provide），避免多组件重复请求。
 */
import { ref, computed, provide, inject, watch, onUnmounted, InjectionKey } from 'vue'
import { fontManagerApi } from '@/api'
import type {
  FontManagerConfig,
  FontFace,
  FontJob,
  FontManagerStatus,
  FontModeOption,
  TempFontFile,
  TempFontState,
} from '@/api/fontManager'
import { useNotification, useConfirm } from '@/composables'

/** 字体文件后缀（上传字体库 / 临时字体时使用） */
export const FONT_ACCEPT = '.ttf,.otf,.ttc,.otc,.woff,.woff2'
export const FONT_RE = /\.(ttf|otf|ttc|otc|woff|woff2)$/i
/** 字幕后缀（上传任务用） */
export const SUBTITLE_RE = /\.(ass|ssa)$/i
/** 单次拖拽最多收集的文件数（防御性上限，避免拖入超大目录卡住） */
export const MAX_DROP_FILES = 1000

// ── 拖拽递归收集（任务上传与临时字体上传共用） ──────────────
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

/** 收集结果：文件列表 + 是否遇到过文件夹（用于给出更准确的提示） */
export interface DroppedCollectResult {
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
export async function collectDroppedFiles(
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

// ── 格式化工具 ─────────────────────────────────────────────
export function formatFileSize(bytes: number | undefined): string {
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

export function formatDuration(ms: number | undefined): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export function formatDateTime(value: string | undefined): string {
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

// ── 主状态工厂 ─────────────────────────────────────────────
function createFontManagerStore() {
  const { success, error: showError, warning, info: showInfo } = useNotification()
  const { confirm } = useConfirm()

  // ── 状态总览 ──
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

  /** 是否已设置字体库目录 */
  const hasLibrary = computed(() => !!libraryInfo.value?.path)
  /** 索引是否可用（存在且非空） */
  const indexReady = computed(() => !!indexInfo.value?.exists && (indexInfo.value?.count ?? 0) > 0)

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

  // ── 处理模式 ──
  const modeOptions = computed<FontModeOption[]>(() => status.value?.modes ?? [])
  const selectedMode = ref<string>('')
  const persistedMode = ref<string>('')
  const modeSaving = ref(false)
  const modeUserPicked = ref(false)

  function modeLabel(value: string): string {
    return modeOptions.value.find((m) => m.value === value)?.label || value
  }

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

  watch(
    () => status.value?.options?.mode,
    (m) => {
      if (!m) return
      persistedMode.value = m
      if (!modeUserPicked.value || !selectedMode.value) selectedMode.value = m
    },
    { immediate: true },
  )

  async function onModeChange(value: string | null) {
    const mode = String(value || '')
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
      persistedMode.value = prev
      showError(`${e?.message || '保存处理模式失败'}（本次操作仍会使用所选模式）`)
    } finally {
      modeSaving.value = false
    }
  }

  // ── 任务列表 ──
  const jobs = ref<FontJob[]>([])
  const jobsTotal = ref(0)
  const jobsLoading = ref(false)
  const jobStatusFilter = ref<string>('')
  const jobSearch = ref('')
  const busyIds = ref<Record<string, boolean>>({})
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

  // ── 请求 ──
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
    if (activeTab.value === 'library') await fetchFonts()
  }

  // ── 轮询（有任务 running 时每 1.5s 刷新） ──
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

  onUnmounted(stopPolling)

  // ── 字体库面板 ──
  const fonts = ref<FontFace[]>([])
  const fontsTotal = ref(0)
  const fontsFormats = ref<Record<string, number>>({})
  const fontsLoading = ref(false)
  const fontsQuery = ref('')
  const fontsFormat = ref<string>('')
  /** 每页条数（增量分页：每次只拉新的一页，追加到列表尾部） */
  const FONTS_PAGE = 100
  const fontsLimit = ref(FONTS_PAGE)

  /** 索引里的字体库数量（Tab 徽标 / 面板标题） */
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
        limit: FONTS_PAGE,
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

  /** 增量分页：只拉取下一页并追加，避免重复加载已有数据 */
  async function loadMoreFonts() {
    if (fontsLoading.value) return
    if (fonts.value.length >= fontsTotal.value) return
    fontsLoading.value = true
    try {
      const res = await fontManagerApi.listFonts({
        q: fontsQuery.value.trim() || undefined,
        fmt: fontsFormat.value || undefined,
        scope: 'library',
        limit: FONTS_PAGE,
        offset: fonts.value.length,
      })
      const page = res?.data || []
      fonts.value = fonts.value.concat(page)
      fontsTotal.value = res?.total || fontsTotal.value
      fontsFormats.value = res?.formats || fontsFormats.value
    } catch (e: any) {
      showError(e?.message || '读取字体列表失败')
    } finally {
      fontsLoading.value = false
    }
  }

  function resetFontsLimit() {
    fontsLimit.value = FONTS_PAGE
  }

  // ── 临时字体池 ──
  const tempFonts = computed<TempFontState | null>(() => status.value?.temp_fonts ?? null)
  const tempFontFiles = computed<TempFontFile[]>(() => tempFonts.value?.files ?? [])
  const tempFontActive = computed(() => !!tempFonts.value?.active)
  /** 临时字体池内全部字体名（文件名去后缀 + 常见分隔符归一），用于前端兜底判断"缺的字体临时池里有没有" */
  const tempFontNames = computed<string[]>(() => {
    const names: string[] = []
    for (const f of tempFontFiles.value) {
      // 文件名主干：xxx.ttf → xxx（字体重命名后的 family 常与文件名一致）
      const stem = f.filename.replace(/\.[^.]+$/, '')
      if (stem) names.push(stem)
      // 常见命名：family-weight / family Bold 等，取第一段也加进去
      const first = stem.split(/[-_]/)[0]
      if (first && first !== stem) names.push(first)
    }
    return names
  })

  // ── 目录选择（复用 FolderBrowserModal，含多个目标） ──
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

  // ── 上传（跨 Tab 共用：页面级拖拽路由也调用这两个方法） ──
  const jobsUploading = ref(false)

  /** 上传字幕建任务（.ass/.ssa；JobsTab 的上传区与主视图页面级拖拽路由共用） */
  async function uploadSubtitles(files: File[]) {
    const valid = files.filter((f) => SUBTITLE_RE.test(f.name))
    const ignored = files.length - valid.length
    if (ignored > 0) showError(`已忽略 ${ignored} 个非字幕文件（仅支持 .ass / .ssa）`)
    if (!valid.length) return

    jobsUploading.value = true
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
      jobsUploading.value = false
    }
  }

  const tempUploading = ref(false)

  /** 上传临时字体（不入库，仅作为 -f 补充源；TempFontsTab 与页面级拖拽路由共用） */
  async function uploadTempFontsFiles(files: File[], emptyHint = '没有可用的字体文件') {
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

  // ── 页面分区（Tab） ──
  /** 当前 Tab：jobs=字幕任务 / library=字体库 / temp=临时字体 / history=处理历史 */
  const activeTab = ref<'jobs' | 'library' | 'temp' | 'history'>('jobs')
  /** 临时字体池有字体时在 Tab 上给个提示徽标 */
  const tempTabBadge = computed(() => (tempFontActive.value ? tempFontFiles.value.length : 0))
  /** 从任务列表跳到临时字体 Tab（缺字体 → 去补字体） */
  function goTempFonts() {
    activeTab.value = 'temp'
  }
  /** 切到字体库 Tab 时拉取明细（首屏已预取，避免闪空表/过期数据） */
  watch(activeTab, (t) => {
    if (t === 'library') fetchFonts()
  })

  // ── 防抖搜索 ──
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
    if (activeTab.value === 'library') {
      resetFontsLimit()
      fetchFonts()
    }
  })

  onUnmounted(() => {
    if (jobSearchDebounce) clearTimeout(jobSearchDebounce)
    if (fontsSearchDebounce) clearTimeout(fontsSearchDebounce)
  })

  // ── 索引重建 ──
  const rebuilding = ref(false)

  async function rebuildIndex() {
    rebuilding.value = true
    try {
      const res = await fontManagerApi.rebuildIndex()
      success(res?.message || '字体索引已重建')
      await fetchStatus()
      if (activeTab.value === 'library') await fetchFonts()
    } catch (e: any) {
      showError(e?.message || '索引重建失败')
    } finally {
      rebuilding.value = false
    }
  }

  // ── 设置对话框 ──
  function defaultConfigForm(): FontManagerConfig {
    return {
      // 字体来源
      library_dir: '',
      extra_library_dirs: [],
      index_dir: '',
      workspace_dir: '',
      // 字幕处理（模式 + 处理参数）
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

  /** 额外字体库目录列表编辑 */
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

  return {
    // 通知与确认
    success,
    showError,
    warning,
    showInfo,
    confirm,
    // 状态总览
    status,
    statusLoading,
    binary,
    indexInfo,
    libraryInfo,
    jobCounts,
    runOptions,
    libraryPaths,
    libraryWarnings,
    hasLibrary,
    indexReady,
    effectiveOptionsText,
    // 处理模式
    modeOptions,
    selectedMode,
    modeSaving,
    modeLabel,
    modeDescription,
    currentModeDescription,
    onModeChange,
    // 任务
    jobs,
    jobsTotal,
    jobsLoading,
    jobStatusFilter,
    jobSearch,
    busyIds,
    fontsExpanded,
    batchRunning,
    downloadingAll,
    clearingJobs,
    clearingAllJobs,
    statusFilterItems,
    runningCount,
    fetchJobs,
    fetchStatus,
    refreshAll,
    // 字体库
    fonts,
    fontsTotal,
    fontsFormats,
    fontsLoading,
    fontsQuery,
    fontsFormat,
    FONTS_PAGE,
    fontsLimit,
    libraryFontCount,
    formatFilterItems,
    fetchFonts,
    loadMoreFonts,
    resetFontsLimit,
    // 临时字体
    tempFonts,
    tempFontFiles,
    tempFontActive,
    tempFontNames,
    // 上传（跨 Tab / 页面级拖拽路由共用）
    jobsUploading,
    uploadSubtitles,
    tempUploading,
    uploadTempFontsFiles,
    // Tab
    activeTab,
    tempTabBadge,
    goTempFonts,
    // 索引重建 / 设置 / 目录选择
    rebuilding,
    rebuildIndex,
    showSettings,
    configLoading,
    savingConfig,
    configForm,
    configModeDescription,
    hdrEnabled,
    verboseItems,
    addExtraLibraryDir,
    removeExtraLibraryDir,
    setExtraLibraryDir,
    openSettings,
    saveSettings,
    showFolderBrowser,
    folderTitle,
    folderInitial,
    openFolderPicker,
    onFolderSelected,
    librarySaving,
  }
}

export type FontManagerStore = ReturnType<typeof createFontManagerStore>

/** provide/inject key（主视图 provide，各 Tab 子组件 inject 同一份） */
const FONT_MANAGER_STORE_KEY: InjectionKey<FontManagerStore> = Symbol('font-manager-store')

/** 主视图调用：创建共享状态并 provide 给子组件 */
export function provideFontManager(): FontManagerStore {
  const store = createFontManagerStore()
  provide(FONT_MANAGER_STORE_KEY, store)
  return store
}

/** Tab 子组件调用：取主视图提供的共享状态 */
export function useFontManager(): FontManagerStore {
  const store = inject(FONT_MANAGER_STORE_KEY)
  if (!store) throw new Error('useFontManager 必须在 <FontManagerView> 内使用（缺少 provideFontManager）')
  return store
}
