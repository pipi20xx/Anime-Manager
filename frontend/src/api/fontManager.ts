/**
 * 字体管家 API — assfonts 的网页封装
 *
 * 对接后端 /api/font_manager 路由:
 * - 状态总览（二进制/索引/字体库/任务统计/处理模式与当前生效选项）
 * - 配置读写（字体库目录、处理模式、子集化参数、内核参数）
 * - 字体索引重建与字体库列表
 * - 字幕上传 → 按模式处理 → 下载成品（.ass 或字体包 zip）
 * - assfonts 内核更新检查与应用
 *
 * 说明：下载端点返回二进制流，不能走 apiFetch（会按 JSON 解析），
 *       因此这里单独用原生 fetch + blob 实现。
 */
import { api } from './client'

// ── 类型定义 ──────────────────────────────────────────────

/**
 * 任务状态：
 * pending=待处理 / running=处理中 / success=已完成 /
 * missing=缺字体 / failed=失败 /
 * skipped=已跳过（例如「清除已内嵌字体」时输入字幕本来就没有内嵌字体，error 字段说明原因）
 */
export type FontJobStatus = 'pending' | 'running' | 'success' | 'missing' | 'failed' | 'skipped'

/** 成品交付物类型：ass=单个字幕文件 / zip=字体包 */
export type FontOutputKind = 'ass' | 'zip'

/**
 * 下载交付物类型：
 * main=主成品（按 output_kind 为 .ass 或字体包 zip）
 * cleaned=附带的清理版字幕（x.cleaned.ass）
 * subset=_subsetted 子集字体文件夹（打包成 zip）
 */
export type FontDownloadKind = 'main' | 'cleaned' | 'subset'

/** 处理模式（GET /status 的 modes 字段；模式选择器的唯一数据源，不要硬编码） */
export interface FontModeOption {
  value: string
  label: string
  description: string
  output_kind: FontOutputKind
}

/** 后端合并配置与临时覆盖后，本次处理实际生效的选项（GET /status 的 options 字段） */
export interface FontRunOptions {
  mode: string
  mode_label: string
  output_kind: FontOutputKind
  extra_font_dirs: string[]
  extra_font_dir: string
  output_dir: string | null
  rename: boolean
  hdr_luminance: number
  threads: number
  verbose: number
  keep_subset_dir: boolean
  delete_source: boolean
}

/** assfonts 二进制信息 */
export interface FontBinaryInfo {
  ready: boolean
  version: string
  source: string
  source_label: string
  message: string
}

/** 内核 -h 帮助（GET /binary/help；help 为内核原始输出，更新内核后自动同步） */
export interface FontBinaryHelp {
  version: string
  source: string
  source_label: string
  path: string
  help: string
}

/** 字体索引信息 */
export interface FontIndexInfo {
  exists: boolean
  count: number
  file_count: number
  library_count: number
  library_file_count: number
  built_at: string
  path?: string
  error: string
}

/** 字体库目录状态 */
export interface FontLibraryInfo {
  path: string
  /** 全部字体库目录（主目录 + extra_library_dirs） */
  paths?: string[]
  exists: boolean
  writable: boolean
  message: string
  /** 后端给出的提示（如输出目录不存在、日志级别过低会吞掉缺字体提示） */
  warnings?: string[]
}

/** 任务统计 */
export interface FontJobCounts {
  total: number
  pending: number
  running: number
  success: number
  missing: number
  failed: number
  /** 已跳过（如清除内嵌时输入本就没有内嵌字体） */
  skipped: number
}

/** 字体管家配置（GET/PUT /config） */
export interface FontManagerConfig {
  // 字体来源
  library_dir: string
  /** 额外字体库目录（可多个，与主目录一起参与索引与缺字体判定） */
  extra_library_dirs: string[]
  index_dir: string
  workspace_dir: string
  // 处理模式与方式
  /** 默认处理模式，取值见 FontModeOption.value */
  mode: string
  /** 本次处理的额外字体目录（-f），用于「仅内嵌」等需要指定字体来源的场景 */
  extra_font_dir: string
  /** 输出目录（-o），留空 = 输出到任务工作目录 */
  output_dir: string
  rename_fonts: boolean
  /** HDR 亮度（-l），0 = 不处理 */
  hdr_luminance: number
  /** 内核内部线程数（-m），0 = 内核默认 */
  internal_threads: number
  /** 内核日志级别（-v），0-3；低于 2 时内核不再输出缺字体提示 */
  verbose_level: number
  keep_subset_dir: boolean
  /** 成功后删除上传的源字幕副本（删除后无法再次重试该任务） */
  delete_source: boolean
  // 内核
  binary_path: string
  proxy_for_update: boolean
}

/** 索引重建结果（POST /fonts/upload 的 index 字段；未自动重建时为空对象） */
export interface FontIndexBuildResult {
  success?: boolean
  message?: string
  count?: number
  file_count?: number
  log?: string
}

/** 字体上传的单条结果（永久入库与临时上传共用） */
export interface FontUploadEntry {
  filename: string
  stored_name: string
  /** added=新入库 / renamed=同名另存为 name_1.ext / duplicate=同名同内容已存在 */
  action: string
  note: string
  size: number
  /** 字体最终落盘路径（仅永久入库时返回） */
  path?: string
}

/** 临时字体池索引状态 */
export interface TempFontIndexInfo {
  exists: boolean
  count: number
  file_count?: number
  built_at?: string
  error?: string
}

/** 临时字体池中的单个字体 */
export interface TempFontFile {
  filename: string
  size: number
  mtime: string
}

/** 临时字体池状态（/status 的 temp_fonts、/fonts/temp、删除接口返回） */
export interface TempFontState {
  dir: string
  count: number
  files: TempFontFile[]
  index: TempFontIndexInfo
  /** 池内有字体时为真：处理时会自动作为补充字体源（-f）参与 */
  active: boolean
}

/** 永久入库返回体（POST /fonts/upload） */
export interface FontLibraryUploadResult {
  status?: string
  data: FontUploadEntry[]
  skipped: FontUploadSkipped[]
  /** 实际写入的字体数（duplicate 不计入） */
  added: number
  index: FontIndexBuildResult
}

/** 临时字体上传返回体（POST /fonts/temp/upload） */
export interface TempFontUploadResult {
  status?: string
  data: FontUploadEntry[]
  skipped: FontUploadSkipped[]
  temp: TempFontState
}

/** 临时字体删除返回体（DELETE /fonts/temp） */
export interface TempFontDeleteResult {
  status?: string
  removed: string[]
  count: number
  index: TempFontIndexInfo
}

/** GET /status 返回体 */
export interface FontManagerStatus {
  binary: FontBinaryInfo
  index: FontIndexInfo
  library: FontLibraryInfo
  /** 临时字体池状态（有字体时处理会自动带上它作为 -f） */
  temp_fonts: TempFontState
  jobs: FontJobCounts
  /** 后端合并后的当前生效选项 */
  options: FontRunOptions
  /** 可选处理模式列表（模式选择器数据源） */
  modes: FontModeOption[]
  config: Partial<FontManagerConfig>
}

/** 处理任务 */
export interface FontJob {
  job_id: string
  filename: string
  status: FontJobStatus
  /** 本任务实际使用的处理模式 */
  mode: string
  mode_label: string
  output_kind: FontOutputKind
  referenced_fonts: string[]
  missing_fonts: string[]
  has_embedded: boolean
  /** 是否保留了 _subsetted 子集字体目录 */
  has_subset_dir: boolean
  output_name: string
  output_size: number
  /** 「清除已内嵌字体」模式另存的文件名（如 x.cleaned.ass） */
  cleaned_name: string
  duration_ms: number
  error: string
  created_at: string
  updated_at: string
}

/** 索引中的字体 face */
export interface FontFace {
  /** 首选 family（families[0]，缺失时退回 fullname） */
  family: string
  /** 全部 family 名（含本地化名，如日文/英文名） */
  families: string[]
  /** 首选全名 */
  fullname?: string
  /** 全部全名 */
  fullnames?: string[]
  /** 首选 PostScript 名 */
  psname?: string
  /** 全部 PostScript 名 */
  psnames?: string[]
  filename: string
  format: string
  in_library: boolean
  weight?: number | null
  slant?: number | null
  /** TTC/OTC 集合内的 face 序号 */
  face_index?: number
  last_write_time?: string
}

/** 上游更新信息 */
export interface FontUpdateInfo {
  current: string
  latest: string
  has_update: boolean
  asset_name: string
  download_url: string
  published_at: string
  notes: string
  size: number
  error: string
}

/** 批量执行汇总 */
export interface FontSubsetSummary {
  total: number
  success: number
  missing: number
  failed: number
  /** 已跳过（如清除内嵌时输入本就没有内嵌字体） */
  skipped: number
}

/** 上传时被跳过的文件 */
export interface FontUploadSkipped {
  filename: string
  reason: string
}

/** 索引精简信息（/index/rebuild 与 /fonts 返回） */
export interface FontIndexSummary {
  exists: boolean
  count: number
  file_count: number
  built_at: string
  library_count?: number
  library_file_count?: number
  error?: string
}

/** 随行字幕子集化处理历史（整理任务联动） */
export interface FontSubsetHistoryItem {
  id: number
  source_name: string
  source_path: string
  target_path: string
  target_name: string
  /** 目标归属域：local=本地文件 / cd2=云端（重试走 CD2 API 下载→子集化→上传） */
  target_via: 'local' | 'cd2'
  status: 'success' | 'missing' | 'failed' | 'skipped'
  missing_fonts: string[]
  referenced_fonts: string[]
  file_size: number
  attempts: number
  last_error: string
  task_id: string
  video_title: string
  tmdb_id: string
  season: number | null
  episode: string
  created_at: string
  updated_at: string
  /** 交付文件当前是否还在；云端记录为 null（本地无法判定，重试时再确认） */
  exists: boolean | null
}

export interface FontSubsetHistoryList {
  status?: string
  total: number
  counts: Record<string, number>
  limit: number
  offset: number
  data: FontSubsetHistoryItem[]
}

const BASE = '/api/font_manager'
/** 下载走原生 fetch，需要自行拼接 base（apiFetch 会自动加 VITE_API_BASE_URL） */
const RAW_BASE = `${import.meta.env.VITE_API_BASE_URL || ''}${BASE}`

// ── 下载（原生 fetch + blob） ──────────────────────────────

/** 下载二进制流并触发浏览器保存 */
async function downloadBlob(url: string, filename: string): Promise<void> {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token') || ''
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) {
    const data: any = await res.json().catch(() => ({}))
    throw new Error(data?.detail || '下载失败')
  }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(a.href)
}

/** 打包文件名用的时间戳 */
function zipStamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

/** 取字幕文件名的主干（去掉目录与 .ass/.ssa 后缀） */
function subtitleStem(filename: string): string {
  const base = (filename || '').split(/[\\/]/).pop() || ''
  return base.replace(/\.(ass|ssa)$/i, '') || 'subtitle'
}

/**
 * 下载文件名：
 * - main    → 后端已给好的 job.output_name（x.assfonts.ass / x_subsetted.zip / x.cleaned.ass）
 * - cleaned → job.cleaned_name（x.cleaned.ass）
 * - subset  → <原字幕名>_subsetted.zip
 */
export function jobDownloadName(job: FontJob, kind: FontDownloadKind = 'main'): string {
  if (kind === 'cleaned') return job.cleaned_name || `${subtitleStem(job.filename)}.cleaned.ass`
  if (kind === 'subset') return `${subtitleStem(job.filename)}_subsetted.zip`
  if (job.output_name) return job.output_name
  return job.output_kind === 'zip'
    ? `${subtitleStem(job.filename)}_subsetted.zip`
    : `${subtitleStem(job.filename)}.assfonts.ass`
}

// ── API 调用 ──────────────────────────────────────────────

export const fontManagerApi = {
  /** 总状态：二进制 / 索引 / 字体库 / 任务统计 / 生效选项 / 可用处理模式 */
  getStatus: () =>
    api.get<FontManagerStatus>(`${BASE}/status`),

  /** 读取配置 */
  getConfig: () =>
    api.get<{ status?: string; data: FontManagerConfig }>(`${BASE}/config`),

  /** 保存配置（只传需要修改的字段） */
  updateConfig: (patch: Partial<FontManagerConfig>) =>
    api.put<{ status?: string; data: FontManagerConfig }>(`${BASE}/config`, patch),

  /** 重建字体索引（失败返回 HTTP 400 {detail}） */
  rebuildIndex: () =>
    api.post<{ status?: string; message: string; log?: string; index: FontIndexSummary }>(`${BASE}/index/rebuild`),

  /** 内核 -h 原始帮助输出（失败返回 HTTP 500 {detail}） */
  getBinaryHelp: () =>
    api.get<{ status?: string } & FontBinaryHelp>(`${BASE}/binary/help`),

  /**
   * 上传字体到字体库（永久，FormData 字段名 files）。
   * 同名同内容记为 duplicate 不重复占空间，同名不同内容另存 name_1.ext 绝不覆盖；
   * 按配置 auto_rebuild_after_upload 自动重建索引（index 为空对象表示未重建）。
   * 全部被拒时返回 HTTP 400 {detail}。
   */
  uploadFonts: (files: File[]) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post<FontLibraryUploadResult>(`${BASE}/fonts/upload`, formData)
  },

  /**
   * 上传临时字体（FormData 字段名 files）。
   * 只作为内核处理时的 -f 补充字体源，不写入字体库；上传后立即重建临时索引参与缺字体预检。
   */
  uploadTempFonts: (files: File[]) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post<TempFontUploadResult>(`${BASE}/fonts/temp/upload`, formData)
  },

  /** 临时字体列表 */
  listTempFonts: () =>
    api.get<TempFontState>(`${BASE}/fonts/temp`),

  /** 删除临时字体（不传 filename = 全部清空） */
  deleteTempFont: (filename?: string) =>
    api.delete<TempFontDeleteResult>(`${BASE}/fonts/temp`, {
      params: filename ? { filename } : undefined,
    }),

  /** 字体列表（默认仅字体库目录内） */
  listFonts: (params?: {
    q?: string
    fmt?: string
    scope?: 'library' | 'all'
    limit?: number
    offset?: number
  }) =>
    api.get<{
      status?: string
      index: FontIndexSummary
      scope?: string
      formats: Record<string, number>
      total: number
      limit?: number
      offset?: number
      data: FontFace[]
    }>(`${BASE}/fonts`, { params }),

  /** 上传字幕（多文件，FormData 字段名 files） */
  upload: (files: File[]) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post<{
      status?: string
      data: FontJob[]
      skipped: FontUploadSkipped[]
    }>(`${BASE}/jobs/upload`, formData)
  },

  /** 任务列表 */
  listJobs: (params?: { status?: string; q?: string; limit?: number; offset?: number }) =>
    api.get<{ status?: string; total: number; limit?: number; offset?: number; data: FontJob[] }>(
      `${BASE}/jobs`,
      { params },
    ),

  /** 执行单个任务（含重试），可临时覆盖处理模式 */
  runJob: (jobId: string, mode?: string) =>
    api.post<{ status?: string; data: FontJob }>(
      `${BASE}/jobs/${encodeURIComponent(jobId)}/run`,
      undefined,
      { params: mode ? { mode } : undefined },
    ),

  /** 批量执行待处理/缺字体/失败任务，可临时覆盖处理模式 */
  runAll: (includeFailed = true, mode?: string) =>
    api.post<{
      status?: string
      message?: string
      summary: FontSubsetSummary
      mode?: string
      mode_label?: string
      data: FontJob[]
    }>(`${BASE}/jobs/run-all`, undefined, {
      params: { include_failed: includeFailed, ...(mode ? { mode } : {}) },
    }),

  /** 删除任务（同时删除工作目录） */
  deleteJob: (jobId: string) =>
    api.delete<{ status?: string }>(`${BASE}/jobs/${encodeURIComponent(jobId)}`),

  /**
   * 清理任务。
   * - 默认（keepFailed=true, includePending=false）：清 success + skipped；
   *   failed / missing / pending 都算「还没了结」，保留下来便于补齐字体后重试
   * - keepFailed=false：再清 failed + missing
   * - includePending=true：再清 pending（配合 keepFailed=false 即「清空全部」）
   * running 状态的任务永不清理
   */
  clearJobs: (options?: { keepFailed?: boolean; includePending?: boolean }) =>
    api.post<{ status?: string; removed: number }>(`${BASE}/jobs/clear`, undefined, {
      params: {
        keep_failed: options?.keepFailed ?? true,
        include_pending: options?.includePending ?? false,
      },
    }),

  /**
   * 下载单个交付物（原生 fetch + blob）。
   * kind=main 主成品 / cleaned 清理版字幕 / subset 子集字体包；
   * 后端按 kind 返回 .ass 流或 zip 流，文件名由 jobDownloadName 决定。
   */
  downloadJob: (job: FontJob, kind: FontDownloadKind = 'main') =>
    downloadBlob(
      `${RAW_BASE}/jobs/${encodeURIComponent(job.job_id)}/download?kind=${encodeURIComponent(kind)}`,
      jobDownloadName(job, kind),
    ),

  /** 打包下载全部成品（zip，原生 fetch + blob） */
  downloadAllJobs: () =>
    downloadBlob(`${RAW_BASE}/jobs/download-all`, `font_subset_${zipStamp()}.zip`),

  /** 下载字体库中的单个字体文件（原生 fetch + blob） */
  downloadFont: (filename: string) =>
    downloadBlob(
      `${RAW_BASE}/fonts/download?filename=${encodeURIComponent(filename)}`,
      filename,
    ),

  /**
   * 按筛选条件打包下载字体库（zip，原生 fetch + blob）。
   * q / fmt 与 /fonts 列表接口的筛选语义一致：下载当前筛选出的全部字体。
   */
  downloadFontsAll: (params?: { q?: string; fmt?: string }) => {
    const qs = new URLSearchParams()
    if (params?.q) qs.set('q', params.q)
    if (params?.fmt) qs.set('fmt', params.fmt)
    const query = qs.toString()
    return downloadBlob(
      `${RAW_BASE}/fonts/download-all${query ? `?${query}` : ''}`,
      `font_library_${zipStamp()}.zip`,
    )
  },

  /** 检查 assfonts 上游更新 */
  checkUpdate: () =>
    api.get<{ status?: string; data: FontUpdateInfo }>(`${BASE}/update/check`),

  /** 应用 assfonts 更新（不传 body 时后端自动查询最新 Release） */
  applyUpdate: (body: { download_url?: string; asset_name?: string; version?: string } = {}) =>
    api.post<{ status?: string; data: { success: boolean; version: string; message: string } }>(
      `${BASE}/update/apply`,
      body,
    ),

  // ── 处理历史（整理任务联动） ────────────────────────────

  /** 随行字幕子集化处理历史（成功也记、缺字体也记） */
  listSubsetHistory: (params?: { status?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.q) qs.set('q', params.q)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const query = qs.toString()
    return api.get<FontSubsetHistoryList>(`${BASE}/history${query ? `?${query}` : ''}`)
  },

  /** 按交付路径重新子集化一条记录（成功则替换原文件） */
  retrySubsetHistory: (id: number) =>
    api.post<{ status?: string; data: FontSubsetHistoryItem }>(`${BASE}/history/${id}/retry`),

  /** 批量重新子集化（默认处理「缺字体」的记录） */
  retrySubsetHistoryBulk: (status = 'missing', limit = 20) =>
    api.post<{ status?: string; summary: Record<string, number>; data: FontSubsetHistoryItem[] }>(
      `${BASE}/history/retry?status=${encodeURIComponent(status)}&limit=${limit}`,
    ),

  /** 删除一条处理历史 */
  deleteSubsetHistory: (id: number) =>
    api.delete<{ status?: string }>(`${BASE}/history/${id}`),

  /** 清理处理历史（默认保留缺字体/失败，方便补完字体再重试） */
  clearSubsetHistory: (keepUnresolved = true) =>
    api.post<{ status?: string; removed: number }>(
      `${BASE}/history/clear?keep_unresolved=${keepUnresolved}`,
    ),
}
