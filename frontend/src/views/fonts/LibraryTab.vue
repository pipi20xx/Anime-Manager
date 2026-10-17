<script setup lang="ts">
/**
 * LibraryTab — 字体管家·字体库
 *
 * 索引内字体列表（格式分布 + 搜索 + 格式筛选 + 分页上限）+ 上传字体到库（永久入库）。
 * 状态与方法来自 useFontManager()（主视图 provide 的共享 store）。
 */
import { ref } from 'vue'
import { fontManagerApi } from '@/api'
import type { FontFace } from '@/api/fontManager'
import { useFontManager, FONT_ACCEPT, FONT_RE } from './useFontManager'

defineOptions({ name: 'FontManagerLibraryTab' })

const {
  success, showError, warning, showInfo,
  indexInfo,
  fonts, fontsTotal, fontsFormats, fontsLoading, fontsQuery, fontsFormat,
  FONTS_LIMIT_MAX, fontsLimit, libraryFontCount, formatFilterItems,
  fetchFonts, loadMoreFonts, resetFontsLimit, refreshAll,
} = useFontManager()

// ── 字体详情对话框 ─────────────────────────────────────────
const showDetail = ref(false)
const detailFont = ref<FontFace | null>(null)

function openDetail(f: FontFace) {
  detailFont.value = f
  showDetail.value = true
}

/** families + fullnames + psnames 合并去重（详情对话框用） */
function allNames(f: FontFace): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = []
  const seen = new Set<string>()
  const push = (label: string, v?: string) => {
    const t = (v || '').trim()
    if (!t || seen.has(t)) return
    seen.add(t)
    out.push({ label, value: t })
  }
  for (const v of f.families || []) push('Family', v)
  for (const v of f.fullnames || []) push('Fullname', v)
  for (const v of f.psnames || []) push('PostScript', v)
  return out
}

function weightText(f: FontFace): string {
  const parts: string[] = []
  if (f.weight != null) parts.push(String(f.weight))
  if (f.slant) parts.push('斜体')
  return parts.join(' / ') || '-'
}

// ── 下载（单个 / 按当前筛选打包） ──────────────────────────
const downloadingAll = ref(false)
const downloadingOne = ref('')

/** 按当前搜索与格式筛选打包下载 */
async function downloadFiltered() {
  if (!fontsTotal.value) {
    warning('当前筛选条件下没有可下载的字体')
    return
  }
  downloadingAll.value = true
  try {
    await fontManagerApi.downloadFontsAll({
      q: fontsQuery.value.trim() || undefined,
      fmt: fontsFormat.value || undefined,
    })
    success(`已开始打包下载 ${fontsTotal.value} 个字体（当前筛选）`)
  } catch (e: any) {
    showError(e?.message || '打包下载失败')
  } finally {
    downloadingAll.value = false
  }
}

async function downloadOne(filename: string) {
  downloadingOne.value = filename
  try {
    await fontManagerApi.downloadFont(filename)
    success(`已开始下载「${filename}」`)
  } catch (e: any) {
    showError(e?.message || '下载失败')
  } finally {
    downloadingOne.value = ''
  }
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
    // 索引状态可能已变化，同步刷新
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '上传字体到字体库失败')
  } finally {
    libraryUploading.value = false
  }
}
</script>

<template>
  <v-card class="glass-card" variant="flat">
    <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
      <v-icon start color="primary">mdi-database-outline</v-icon>
      <span class="text-body-1 font-weight-medium">字体库</span>
      <v-chip size="x-small" variant="tonal" title="来自字体索引">
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
        title="把字体永久写入字体库目录，并按设置自动重建索引（不会覆盖同名文件）"
        @click="pickLibraryFonts"
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
        title="选择整个文件夹（含子目录）入库，只挑其中的字体文件"
        @click="pickLibraryFolder"
      >
        选择文件夹
      </v-btn>
    </v-card-title>

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
        <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="fontsLoading" @click="fetchFonts">
          刷新列表
        </v-btn>
        <v-btn
          size="small"
          variant="tonal"
          color="info"
          prepend-icon="mdi-download-multiple-outline"
          :loading="downloadingAll"
          :disabled="!fontsTotal"
          :title="fontsTotal ? `打包下载当前筛选的全部 ${fontsTotal} 个字体` : '当前没有可下载的字体'"
          @click="downloadFiltered"
        >
          全部下载
        </v-btn>
      </div>

      <v-progress-linear v-if="fontsLoading" indeterminate color="primary" class="mb-3" />

      <v-table v-if="fonts.length" density="compact" class="fonts-table">
        <thead>
          <tr>
            <th class="text-left">字体名 (family)</th>
            <th class="text-left">文件名</th>
            <th class="text-left" style="width: 80px">格式</th>
            <th class="text-left" style="width: 160px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(f, i) in fonts" :key="`${f.filename}-${i}`">
            <td class="text-body-2">
              {{ f.family || '-' }}
              <v-chip
                v-if="(f.face_index ?? 0) > 0"
                size="x-small"
                variant="tonal"
                color="primary"
                class="ml-1"
                :title="`TTC/OTC 集合内第 ${(f.face_index ?? 0) + 1} 个 face`"
              >
                #{{ f.face_index }}
              </v-chip>
            </td>
            <td class="text-body-2 font-mono text-truncate" style="max-width: 320px" :title="f.filename">
              {{ f.filename }}
            </td>
            <td>
              <v-chip size="x-small" variant="tonal">{{ (f.format || 'unknown').toUpperCase() }}</v-chip>
            </td>
            <td style="width: 160px">
              <v-btn
                size="x-small"
                variant="tonal"
                prepend-icon="mdi-information-outline"
                title="查看该字体的全部名称与元数据"
                @click="openDetail(f)"
              >
                详情
              </v-btn>
              <v-btn
                size="x-small"
                variant="tonal"
                color="info"
                prepend-icon="mdi-download"
                class="ml-1"
                :loading="downloadingOne === f.filename"
                title="下载该字体文件"
                @click="downloadOne(f.filename)"
              >
                下载
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <EmptyState
        v-else-if="!fontsLoading"
        icon="mdi-format-font"
        title="字体库中暂无字体"
        description="确认字体库目录下有 .ttf/.otf/.ttc 字体文件后，点击顶部状态条的「重建索引」，或在上方上传字体到库"
      />

      <!-- 条数上限提示 + 加载更多 -->
      <div v-if="fontsTotal > fonts.length" class="d-flex align-center flex-wrap ga-2 mt-3">
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
  </v-card>

  <!-- ══ 字体详情对话框 ══ -->
  <v-dialog v-model="showDetail" max-width="560" scrollable>
    <v-card class="glass-card">
      <DialogTitle
        icon="mdi-information-outline"
        icon-color="primary"
        :title="detailFont?.family || '字体详情'"
        @close="showDetail = false"
      />
      <v-divider />

      <v-card-text class="pa-4" v-if="detailFont">
        <!-- 基本信息 -->
        <div class="detail-grid mb-4">
          <div class="text-caption text-medium-emphasis">文件名</div>
          <div class="text-body-2 font-mono text-break">{{ detailFont.filename }}</div>

          <div class="text-caption text-medium-emphasis">格式</div>
          <div>
            <v-chip size="x-small" variant="tonal">{{ (detailFont.format || 'unknown').toUpperCase() }}</v-chip>
            <v-chip
              v-if="(detailFont.face_index ?? 0) > 0"
              size="x-small"
              variant="tonal"
              color="primary"
              class="ml-1"
            >
              face #{{ detailFont.face_index }}
            </v-chip>
          </div>

          <div class="text-caption text-medium-emphasis">字重 / 斜体</div>
          <div class="text-body-2">{{ weightText(detailFont) }}</div>

          <div class="text-caption text-medium-emphasis">索引时间</div>
          <div class="text-body-2 text-medium-emphasis">{{ detailFont.last_write_time || '-' }}</div>
        </div>

        <!-- 全部名称 -->
        <div class="section-title mb-2">
          <v-icon size="16" color="primary">mdi-format-quote-close</v-icon>
          全部名称（{{ allNames(detailFont).length }} 个，字幕匹配按这些名字进行）
        </div>
        <div class="names-list">
          <div
            v-for="(n, idx) in allNames(detailFont)"
            :key="`${n.label}-${idx}`"
            class="d-flex align-start ga-2 py-1"
          >
            <v-chip size="x-small" variant="tonal" class="name-kind">{{ n.label }}</v-chip>
            <span class="text-body-2 font-mono text-break" style="word-break: break-all">{{ n.value }}</span>
          </div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn
          variant="tonal"
          color="info"
          prepend-icon="mdi-download"
          :loading="downloadingOne === detailFont?.filename"
          @click="detailFont && downloadOne(detailFont.filename)"
        >
          下载字体
        </v-btn>
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showDetail = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { EmptyState } from '@/components/common'
export default { components: { EmptyState } }
</script>

<style scoped>
.fonts-table {
  background: transparent;
}
.detail-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px 16px;
  align-items: start;
}
.names-list {
  max-height: 34vh;
  overflow: auto;
  padding-right: 4px;
}
.name-kind {
  flex: 0 0 auto;
  min-width: 78px;
  justify-content: center;
}
</style>
