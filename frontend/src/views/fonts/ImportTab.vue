<script setup lang="ts">
/**
 * ImportTab — 字体管家·压缩包导入
 *
 * 流程：上传压缩包（rar/7z/zip/tar…，也可混选单个字体）
 *      → 后端解压（只抽字体）→ 用 assfonts 给这批字体建临时索引
 *      → 与主库 face 对撞 → 出报告（新增/重复/冲突/无效）
 *      → 勾选后入库到独立目录 → 延迟合并重建索引
 *
 * 关键点：**分析不动字体库**，入库是第二步动作；冲突默认保留库内版本。
 * 状态与方法来自 useFontManager()（主视图 provide 的共享 store）。
 */
import { computed, ref } from 'vue'
import { formatDbSize } from '@/composables'
import { EmptyState } from '@/components/common'
import type { FontImportItem } from '@/api/fontManager'
import {
  useFontManager,
  collectDroppedFiles,
  ARCHIVE_ACCEPT,
  ARCHIVE_RE,
  FONT_ACCEPT,
  FONT_RE,
  MAX_DROP_FILES,
} from './useFontManager'

defineOptions({ name: 'FontManagerImportTab' })

const {
  success, showError, warning, confirm, openSettings,
  importUploading, importCommitting, importJobId, importReport, importInfo,
  importJobs, importJobsLoading, importSelection,
  uploadImportFiles, commitImport, removeImportJob, loadImportJob, reanalyzeImport,
  fetchImportInfo, fetchImportJobs,
} = useFontManager()

const ACCEPT = `${ARCHIVE_ACCEPT},${FONT_ACCEPT}`

const fileInput = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)
const collecting = ref(false)
const policy = ref<'keep' | 'replace' | 'skip'>('keep')
const removeTarget = ref('')

const counts = computed(() => importReport.value?.counts || {})
const hasReport = computed(() => !!importReport.value)
const newItems = computed<FontImportItem[]>(() => importReport.value?.new || [])
const duplicateItems = computed<FontImportItem[]>(() => importReport.value?.duplicate || [])
const conflictItems = computed<FontImportItem[]>(() => importReport.value?.conflict || [])
const invalidItems = computed<FontImportItem[]>(() => importReport.value?.invalid || [])
const skippedFiles = computed(() => importReport.value?.skipped || [])
const canCommit = computed(() => !!importJobId.value && importSelection.value.length > 0)

const allNewSelected = computed({
  get: () => newItems.value.length > 0 && importSelection.value.length === newItems.value.length,
  set: (val: boolean) => {
    importSelection.value = val ? newItems.value.map((i) => i.name) : []
  },
})

/** 工作区保留时长文案（配置项 import_job_ttl_hours，默认 24 小时） */
const jobTtlText = computed(() => `${importInfo.value?.job_ttl_hours ?? 24} 小时`)

/** 限额展示（MB → 人话） */
const limitText = computed(() => {
  const l = importInfo.value?.limits || {}
  if (!l.max_archive_bytes) return ''
  const mb = (v?: number) => `${Math.round((v || 0) / 1024 / 1024)}MB`
  return `单包 ≤ ${mb(l.max_archive_bytes)} · 解压总量 ≤ ${mb(l.max_extract_bytes)} · 单字体 ≤ ${mb(l.max_font_bytes)} · 字体数 ≤ ${l.max_fonts || '—'}`
})

const extractorText = computed(() => {
  const list = importInfo.value?.extractors || []
  if (!list.length) return ''
  const ext = list.filter((x) => x.kind === 'external').map((x) => x.tool)
  return ext.length
    ? `外部解压器：${ext.join(' / ')}`
    : '未检测到 unar / bsdtar / 7z：rar、7z 包将无法解压（zip/tar 仍可用）'
})

function pickFiles() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files ? Array.from(input.files) : []
  input.value = ''
  if (list.length) void handleUpload(list)
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

function onDrop(e: DragEvent) {
  dragActive.value = false
  e.preventDefault()
  void handleDrop(e)
}

/** 拖拽：压缩包/字体都可以，文件夹会递归收集 */
async function handleDrop(e: DragEvent) {
  const dt = e.dataTransfer
  if (!dt) return
  collecting.value = true
  try {
    const collected = await collectDroppedFiles(e, new RegExp(`${ARCHIVE_RE.source}|${FONT_RE.source}`, 'i'))
    if (!collected) {
      const list = Array.from(dt.files || [])
      if (list.length) await handleUpload(list)
      return
    }
    if (collected.truncated) warning(`拖入的文件过多，仅收集前 ${MAX_DROP_FILES} 个文件`)
    if (!collected.files.length) {
      warning(collected.sawDirectory ? '该文件夹内没有压缩包或字体文件' : '没有找到压缩包或字体文件')
      return
    }
    await handleUpload(collected.files)
  } catch (err: any) {
    showError(err?.message || '读取拖入内容失败')
  } finally {
    collecting.value = false
  }
}

function handleUpload(files: File[]) {
  return uploadImportFiles(files)
}

async function doCommit() {
  await commitImport(policy.value)
}

async function askRemove(jobId: string) {
  const ok = await confirm({
    title: '删除导入任务',
    content: `确定删除导入任务 ${jobId} 吗？工作区（解压产物、报告）会被清理，已入库的字体不受影响。`,
    confirmText: '删除',
    cancelText: '取消',
    confirmColor: 'error',
  })
  if (!ok) return
  removeTarget.value = jobId
  try {
    await removeImportJob(jobId)
  } finally {
    removeTarget.value = ''
  }
}

function faceNames(item: FontImportItem): string {
  return (item.faces || [])
    .map((f) => (f.psname || f.family || '').trim())
    .filter(Boolean)
    .join('、')
}

function conflictExisting(item: FontImportItem): string {
  const paths = new Set<string>()
  for (const c of item.conflicts || []) {
    for (const e of c.existing || []) if (e.path) paths.add(e.path)
  }
  return Array.from(paths).join('\n')
}

const openPanels = ref<string[]>(['new'])

void fetchImportInfo()
</script>

<template>
  <div class="import-tab">
    <!-- ══ 上传区 ══ -->
    <v-card class="glass-card mb-4" variant="flat">
      <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
        <v-icon icon="mdi-package-variant-closed" class="mr-1" />
        上传字体压缩包
        <v-chip size="x-small" variant="tonal" color="info">解压 → 比对 → 入库，两步走</v-chip>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          prepend-icon="mdi-refresh"
          @click="fetchImportInfo()"
        >
          刷新能力信息
        </v-btn>
      </v-card-title>

      <v-card-text>
        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': dragActive, 'drop-zone--busy': importUploading || collecting }"
          @dragenter.prevent="onDragEnter"
          @dragover.prevent
          @dragleave="onDragLeave"
          @drop="onDrop"
          @click="pickFiles"
        >
          <input
            ref="fileInput"
            type="file"
            multiple
            :accept="ACCEPT"
            class="d-none"
            @change="onFileChange"
          />
          <v-progress-circular
            v-if="importUploading || collecting"
            indeterminate
            color="primary"
            size="28"
            class="mb-2"
          />
          <v-icon v-else icon="mdi-cloud-upload-outline" size="36" class="mb-2" />
          <div class="text-subtitle-2">
            {{ importUploading ? '正在解压与比对…' : '把字体压缩包拖到这里，或点击选择文件' }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            支持 {{ importInfo?.formats?.join(' / ') || ARCHIVE_ACCEPT }}，也可混选单个字体
          </div>
          <div v-if="limitText" class="text-caption text-medium-emphasis mt-1">{{ limitText }}</div>
          <div v-if="extractorText" class="text-caption mt-2">
            <v-icon
              :icon="(importInfo?.extractors || []).some((x) => x.kind === 'external')
                ? 'mdi-check-circle-outline'
                : 'mdi-alert-outline'"
              size="14"
              :color="(importInfo?.extractors || []).some((x) => x.kind === 'external')
                ? 'success'
                : 'warning'"
              class="mr-1"
            />
            {{ extractorText }}
          </div>
        </div>

        <div v-if="importInfo" class="text-caption text-medium-emphasis mt-3">
          入库目标：<code>{{ importInfo.target }}</code>
          <template v-if="importInfo.target_in_library">
            （在字体库目录内，建索引时自动扫到，无需额外关联）
          </template>
          <template v-else>
            （不在字体库内，已自动作为额外字体目录参与索引）
          </template>
          ，
          <template v-if="importInfo.import_subfolder !== false">
            每次导入建独立子目录
          </template>
          <template v-else>
            直接放入该目录（不建子目录）
          </template>
          ，
          索引合并重建延迟 {{ importInfo.rebuild_debounce }}s
          <v-btn
            size="x-small"
            variant="text"
            class="ml-1"
            prepend-icon="mdi-cog-outline"
            @click="openSettings()"
          >
            修改
          </v-btn>
        </div>
        <div class="text-caption text-medium-emphasis mt-1">
          导入工作区（原始压缩包、报告）保留 {{ jobTtlText }}：从<strong>最后一次操作</strong>算起
          （上传/分析/入库都会刷新计时），到期后在下一次上传压缩包时自动清理；
          已入库的字体不受影响，字体库里的文件也不会被删。
        </div>
      </v-card-text>
    </v-card>

    <!-- ══ 分析报告 ══ -->
    <v-card v-if="hasReport" class="glass-card mb-4" variant="flat">
      <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
        <v-icon icon="mdi-clipboard-check-outline" class="mr-1" />
        比对结果
        <v-chip size="x-small" variant="text">任务 {{ importJobId || '—' }}</v-chip>
        <v-spacer />
        <v-select
          v-model="policy"
          :items="[
            { title: '冲突：保留库内版本', value: 'keep' },
            { title: '冲突：备份旧文件后替换', value: 'replace' },
            { title: '冲突：跳过', value: 'skip' },
          ]"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 240px"
        />
        <v-btn
          size="small"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="importUploading"
          title="重新解压原始压缩包，并与当前字体库重新比对（覆盖旧报告）"
          @click="reanalyzeImport()"
        >
          重新分析
        </v-btn>
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-database-arrow-up-outline"
          :loading="importCommitting"
          :disabled="!canCommit"
          @click="doCommit"
        >
          入库（{{ importSelection.length }}）
        </v-btn>
      </v-card-title>

      <v-card-text>
        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-chip color="success" variant="tonal" prepend-icon="mdi-plus-circle-outline">
            新增 {{ counts.new || 0 }}
          </v-chip>
          <v-chip color="info" variant="tonal" prepend-icon="mdi-content-duplicate">
            重复 {{ counts.duplicate || 0 }}
          </v-chip>
          <v-chip color="warning" variant="tonal" prepend-icon="mdi-alert-circle-outline">
            冲突 {{ counts.conflict || 0 }}
          </v-chip>
          <v-chip color="error" variant="tonal" prepend-icon="mdi-file-alert-outline">
            无效 {{ counts.invalid || 0 }}
          </v-chip>
          <v-chip
            v-if="skippedFiles.length"
            size="small"
            variant="text"
            prepend-icon="mdi-trash-can-outline"
          >
            丢弃条目 {{ importReport?.skipped_count || skippedFiles.length }}
          </v-chip>
          <v-spacer />
          <v-chip size="small" variant="text">
            探测 face {{ importReport?.probe?.faces || 0 }} ·
            库内 face {{ importReport?.library?.faces || 0 }}
          </v-chip>
        </div>

        <div class="text-caption text-medium-emphasis mb-3">
          报告是分析那一刻的快照：从「最近导入任务」进来再入库时，会按需重新解压原始压缩包
          （压缩包随任务过期清理后才需要重新上传）；若字体库在这之后变过（补了字体 / 删了重复 / 重建了索引），
          点「重新分析」生成新报告。已入库过的条目会自动从报告里移除，重复点入库不会重复导入。
        </div>

        <v-alert
          v-if="importReport?.probe && !importReport.probe.success"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          内核探测失败，已降级为「同名 + 同哈希」比对：{{ importReport.probe_error || importReport.probe.message }}
        </v-alert>
        <v-alert
          v-if="importReport?.library && !importReport.library.index_available"
          type="info"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          主库索引不存在，本次未做 face 级比对（建议先在字体库页重建索引）。
        </v-alert>
        <v-alert
          v-else-if="importReport?.library?.stale"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          主库索引（{{ importReport.library.built_at || '—' }}）比库内最新字体文件（{{
            importReport.library.newest || '—'
          }}）旧，比对可能把「其实已在库里」的字体判成新增。建议先到「字体库」页点「重建索引」，
          再重新上传分析。
        </v-alert>

        <!-- 压缩包处理结果 -->
        <div v-if="importReport?.archives?.length" class="mb-3">
          <div v-for="a in importReport.archives" :key="a.name" class="text-caption mb-1">
            <v-icon
              :icon="a.success ? 'mdi-check-circle-outline' : 'mdi-close-circle-outline'"
              size="14"
              :color="a.success ? 'success' : 'error'"
              class="mr-1"
            />
            {{ a.name }} · {{ a.format }} · 解出 {{ a.fonts }} 个字体
            <span v-if="a.extractor">（{{ a.extractor }}）</span>
            <span v-if="!a.success" class="text-error">：{{ a.message }}</span>
          </div>
        </div>

        <v-expansion-panels v-model="openPanels" multiple variant="accordion">
          <!-- 新增 -->
          <v-expansion-panel value="new">
            <v-expansion-panel-title>
              <v-icon icon="mdi-plus-circle-outline" color="success" size="18" class="mr-2" />
              新增（{{ newItems.length }}）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-if="!newItems.length" class="text-caption text-medium-emphasis">
                这个包里没有新字体，全部已在库中。
              </div>
              <template v-else>
                <v-checkbox
                  v-model="allNewSelected"
                  density="compact"
                  hide-details
                  label="全选新增字体"
                  class="mb-1"
                />
                <v-table density="compact">
                  <thead>
                    <tr>
                      <th style="width: 48px" />
                      <th>文件</th>
                      <th style="width: 110px">大小</th>
                      <th>face</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in newItems" :key="item.name">
                      <td>
                        <v-checkbox v-model="importSelection" :value="item.name" density="compact" hide-details />
                      </td>
                      <td>
                        <div class="text-body-2">{{ item.name }}</div>
                        <div v-if="item.source && item.source !== item.name" class="text-caption text-medium-emphasis">
                          {{ item.source }}
                        </div>
                      </td>
                      <td class="text-caption">{{ formatDbSize(item.size) }}</td>
                      <td class="text-caption">{{ faceNames(item) || '—' }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- 重复 -->
          <v-expansion-panel value="duplicate">
            <v-expansion-panel-title>
              <v-icon icon="mdi-content-duplicate" color="info" size="18" class="mr-2" />
              重复（{{ duplicateItems.length }}）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-if="!duplicateItems.length" class="text-caption text-medium-emphasis">无</div>
              <v-table v-else density="compact">
                <thead>
                  <tr>
                    <th>文件</th>
                    <th>原因</th>
                    <th>库内已有</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in duplicateItems" :key="item.name">
                    <td class="text-body-2">{{ item.name }}</td>
                    <td class="text-caption">{{ item.reason || '已存在' }}</td>
                    <td class="text-caption text-medium-emphasis">{{ item.existing || '—' }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- 冲突 -->
          <v-expansion-panel value="conflict">
            <v-expansion-panel-title>
              <v-icon icon="mdi-alert-circle-outline" color="warning" size="18" class="mr-2" />
              冲突（{{ conflictItems.length }}）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-if="!conflictItems.length" class="text-caption text-medium-emphasis">
                无（同 family 不同版本的字体才会落在这里）
              </div>
              <template v-else>
                <v-alert type="info" variant="tonal" density="compact" class="mb-2">
                  默认保留库内版本。要替换请把上面的「冲突」策略改成「备份旧文件后替换」，再勾选这些文件入库。
                </v-alert>
                <v-table density="compact">
                  <thead>
                    <tr>
                      <th style="width: 48px" />
                      <th>文件</th>
                      <th>原因</th>
                      <th>库内同 face 文件</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in conflictItems" :key="item.name">
                      <td>
                        <v-checkbox v-model="importSelection" :value="item.name" density="compact" hide-details />
                      </td>
                      <td>
                        <div class="text-body-2">{{ item.name }}</div>
                        <div class="text-caption text-medium-emphasis">{{ faceNames(item) }}</div>
                      </td>
                      <td class="text-caption">{{ item.reason || '同 face 不同版本' }}</td>
                      <td class="text-caption text-medium-emphasis" style="white-space: pre-line">
                        {{ conflictExisting(item) || '—' }}
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- 无效 -->
          <v-expansion-panel value="invalid">
            <v-expansion-panel-title>
              <v-icon icon="mdi-file-alert-outline" color="error" size="18" class="mr-2" />
              无效（{{ invalidItems.length }}）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-if="!invalidItems.length" class="text-caption text-medium-emphasis">无</div>
              <v-table v-else density="compact">
                <thead>
                  <tr>
                    <th>文件</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in invalidItems" :key="item.name">
                    <td class="text-body-2">{{ item.name }}</td>
                    <td class="text-caption">{{ item.reason || '无法解析' }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- 丢弃条目 -->
          <v-expansion-panel v-if="skippedFiles.length" value="skipped">
            <v-expansion-panel-title>
              <v-icon icon="mdi-trash-can-outline" size="18" class="mr-2" />
              丢弃的条目（{{ skippedFiles.length }}）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>条目</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(s, idx) in skippedFiles" :key="`${s.name}-${idx}`">
                    <td class="text-caption">{{ s.name }}</td>
                    <td class="text-caption text-medium-emphasis">{{ s.reason }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
    </v-card>

    <!-- ══ 最近的导入任务 ══ -->
    <v-card class="glass-card" variant="flat">
      <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
        <v-icon icon="mdi-history" class="mr-1" />
        最近导入任务
        <v-chip v-if="importJobs.length" size="x-small" variant="text">共 {{ importJobs.length }} 条</v-chip>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="importJobsLoading"
          @click="fetchImportJobs()"
        >
          刷新
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div class="text-caption text-medium-emphasis mb-2">
          任务记录保留 {{ jobTtlText }}（自最后一次操作起算），到期后在下一次上传压缩包时自动清理；
          列表最多显示最近 20 条，已入库的字体与字体库文件都不受影响。
        </div>
        <EmptyState
          v-if="!importJobs.length"
          icon="mdi-package-variant-closed"
          title="还没有导入记录"
          description="上传一个字体压缩包，解压比对后任务会出现在这里"
        />
        <v-table v-else density="compact">
          <thead>
            <tr>
              <th>任务</th>
              <th>时间</th>
              <th>压缩包</th>
              <th>结果</th>
              <th style="width: 200px" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in importJobs" :key="job.job_id">
              <td class="text-caption">{{ job.job_id }}</td>
              <td class="text-caption">{{ job.created_at || '—' }}</td>
              <td class="text-caption">{{ (job.archives || []).join('、') || '—' }}</td>
              <td class="text-caption">
                <template v-if="job.committed">
                  <v-chip size="x-small" color="success" variant="tonal">已入库 {{ job.committed_count }}</v-chip>
                </template>
                <template v-else-if="job.analyzed">
                  新增 {{ job.counts?.new || 0 }} / 重复 {{ job.counts?.duplicate || 0 }} /
                  冲突 {{ job.counts?.conflict || 0 }}
                </template>
                <span v-else class="text-medium-emphasis">未分析</span>
              </td>
              <td class="text-no-wrap">
                <div class="action-cell">
                  <v-btn
                    size="small"
                    variant="tonal"
                    prepend-icon="mdi-information-outline"
                    :disabled="!job.analyzed"
                    title="查看该任务的比对报告"
                    @click="loadImportJob(job.job_id)"
                  >
                    详情
                  </v-btn>
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="error"
                    prepend-icon="mdi-delete-outline"
                    :loading="removeTarget === job.job_id"
                    title="删除该任务及其工作区（已入库的字体不受影响）"
                    @click="askRemove(job.job_id)"
                  >
                    删除
                  </v-btn>
                </div>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </div>
</template>

<style scoped>
.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 20px;
  border: 2px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 12px;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.drop-zone:hover {
  border-color: rgb(var(--v-theme-primary));
}
.drop-zone--active {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.06);
}
.drop-zone--busy {
  pointer-events: none;
  opacity: 0.75;
}
/* 与字体库表格的操作列同一套写法：不换行、等距、按钮不吃 margin */
.action-cell {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
}
.action-cell :deep(.v-btn) {
  flex: 0 0 auto;
  margin: 0;
}
</style>
