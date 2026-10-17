<script setup lang="ts">
/**
 * TempFontsTab — 字体管家·临时字体
 *
 * 临时字体池：上传/拖拽临时字体，仅作为内核 -f 补充源，不入库，可单删/清空。
 * 状态与方法来自 useFontManager()（主视图 provide 的共享 store）。
 */
import { ref } from 'vue'
import { fontManagerApi } from '@/api'
import type { TempFontFile } from '@/api/fontManager'
import { formatDbSize } from '@/composables'
import { useFontManager, collectDroppedFiles, FONT_ACCEPT, FONT_RE, MAX_DROP_FILES } from './useFontManager'

defineOptions({ name: 'FontManagerTempFontsTab' })

const {
  success, showError, warning, confirm,
  status, tempFonts, tempFontFiles, tempFontActive,
  refreshAll, tempUploading: uploadTempUploading, uploadTempFontsFiles,
} = useFontManager()

// ── 临时字体池交互状态 ────────────────────────────────────
const tempFontInput = ref<HTMLInputElement | null>(null)
/** 上传状态来自共享 store（页面级拖拽路由也会触发上传） */
const tempUploading = uploadTempUploading
const tempDragActive = ref(false)
const tempDeleting = ref('')
const clearingTemp = ref(false)
/** 正在递归收集拖入文件夹中的字体文件 */
const collecting = ref(false)

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

/** 上传临时字体：统一走 store（页面级拖拽路由也调用同一实现） */
function handleTempFontUpload(files: File[], emptyHint = '没有可用的字体文件') {
  return uploadTempFontsFiles(files, emptyHint)
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

// 模板用到的 status 类型收窄（取 status.value.temp_fonts 的兜底）
const statusRef = status
</script>

<template>
  <v-card
    class="glass-card temp-font-card"
    :class="{ 'temp-font-card--active': tempDragActive, 'temp-font-card--busy': tempUploading || collecting }"
    variant="flat"
    @dragenter.prevent="onTempDragEnter"
    @dragover.prevent="onTempDragEnter"
    @dragleave.prevent="onTempDragLeave"
    @drop.prevent="onTempDrop"
  >
    <v-card-title class="pa-4 d-flex align-center flex-wrap ga-2">
      <v-icon color="primary">mdi-timer-outline</v-icon>
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
        字体库入库请切到「字体库」Tab，避免拖拽误把字体永久写进库里。
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
            <th class="text-left" style="width: 120px">操作</th>
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
                size="small"
                variant="tonal"
                color="error"
                prepend-icon="mdi-delete-outline"
                :loading="tempDeleting === f.filename"
                title="删除该临时字体"
                @click="removeTempFont(f)"
              >
                删除
              </v-btn>
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

<style scoped>
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
