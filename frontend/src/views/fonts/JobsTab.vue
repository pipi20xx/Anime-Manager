<script setup lang="ts">
/**
 * JobsTab — 字体管家·字幕任务
 *
 * 拖拽上传（ASS/SSA 与文件夹递归）+ 任务工具条（处理模式/搜索/批量操作）+ 任务列表。
 * 状态与方法来自 useFontManager()（主视图 provide 的共享 store）。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { fontManagerApi } from '@/api'
import { jobDownloadName } from '@/api/fontManager'
import type { FontDownloadKind, FontJob, FontJobStatus } from '@/api/fontManager'
import { useFontManager, collectDroppedFiles, formatFileSize, formatDateTime, formatDuration, SUBTITLE_RE, MAX_DROP_FILES } from './useFontManager'

defineOptions({ name: 'FontManagerJobsTab' })

const {
  success, showError, warning, showInfo, confirm,
  jobCounts, hasLibrary,
  modeOptions, selectedMode, modeSaving, modeLabel, modeDescription, currentModeDescription, onModeChange,
  jobs, jobsTotal, jobsLoading, jobStatusFilter, jobSearch, busyIds, fontsExpanded,
  batchRunning, downloadingAll, clearingJobs, clearingAllJobs, statusFilterItems,
  fetchJobs, fetchStatus, refreshAll, activeTab,
} = useFontManager()

// ── 上传（拖拽 / 点击选择） ───────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)
const uploading = ref(false)
/** 正在递归收集拖入文件夹中的字幕文件（与临时字体 Tab 共用收集状态提示） */
const collecting = ref(false)

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

// ── 页面级拖拽兜底（整页都是放置区域） ────────────────────
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
    const fontFiles = files.filter((f) => /\.(ttf|otf|ttc|otc|woff|woff2)$/i.test(f.name))
    if (fontFiles.length) {
      warning(
        `检测到 ${fontFiles.length} 个字体文件：请切到「临时字体」Tab 拖入，` +
          '或用字体库 Tab 的「上传字体到库 / 选择文件夹」按钮',
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

// ── 任务展示辅助 ──────────────────────────────────────────
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

function jobModeLabel(job: FontJob): string {
  return job.mode_label || modeLabel(job.mode || '')
}

function downloadLabel(job: FontJob): string {
  return job.output_kind === 'zip' ? '下载字体包' : '下载字幕'
}

/** 主成品之外的附加交付物（子集字体包 / 清理版字幕） */
interface DownloadExtra {
  kind: FontDownloadKind
  title: string
  icon: string
}

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
    const s = res?.summary || { total: 0, success: 0, missing: 0, failed: 0, skipped: 0 }
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

/** 缺字体任务：跳到临时字体 Tab 去补字体 */
function goTempFonts() {
  activeTab.value = 'temp'
}
</script>

<template>
  <div
    @dragenter.prevent="onPageDragEnter"
    @dragover.prevent
    @dragleave="onPageDragLeave"
    @drop.prevent="onPageDrop"
  >
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
      <!-- 第一行：处理模式 -->
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
              variant="tonal"
              color="error"
              prepend-icon="mdi-delete-outline"
              :disabled="!!busyIds[job.job_id]"
              title="删除任务（含工作目录与成品）"
              @click="removeJob(job)"
            >
              删除
            </v-btn>
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

            <v-btn
              size="x-small"
              variant="text"
              color="warning"
              prepend-icon="mdi-arrow-right-circle-outline"
              title="跳转到「临时字体」上传缺失的字体，然后回来重试"
              @click="goTempFonts"
            >
              去补字体
            </v-btn>
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
  </div>
</template>

<script lang="ts">
// EmptyState 在本文件模板中使用，与 <script setup> 并存时需要显式引入
import { EmptyState } from '@/components/common'
export default { components: { EmptyState } }
</script>

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
</style>
