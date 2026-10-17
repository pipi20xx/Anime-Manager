<script setup lang="ts">
/**
 * FontManagerView — 字体管家
 *
 * 对标后端 /api/font_manager（assfonts 的网页封装）。
 * 拆分为 Tab 子组件 + 共享状态层（useFontManager provide/inject）：
 * - FontStatusBar: 顶部状态条（常驻）：内核版本/来源、检查更新、索引状态、字体库路径、警告、任务统计
 * - JobsTab:       字幕任务（拖拽上传 + 工具条 + 任务列表）
 * - LibraryTab:    字体库（索引明细 + 搜索/筛选 + 上传入库）
 * - TempFontsTab:  临时字体（-f 补充源，不入库）
 * - FontSettingsDialog: 设置（字体来源 / 字幕处理 / 内核与网络）
 * - FontHelpDialog:     内核参数帮助（-h 原文 + 对照表）
 * Tab 通过 useDynamicHeaderTab 注册到顶栏，与订阅管理等页面一致。
 * 有任务处于 running 时每 1.5s 轮询任务列表。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import { EmptyState } from '@/components/common'
import FolderBrowserModal from '@/views/organizer/FolderBrowserModal.vue'
import FontStatusBar from './FontStatusBar.vue'
import JobsTab from './JobsTab.vue'
import LibraryTab from './LibraryTab.vue'
import TempFontsTab from './TempFontsTab.vue'
import FontSettingsDialog from './FontSettingsDialog.vue'
import FontHelpDialog from './FontHelpDialog.vue'
import {
  provideFontManager,
  collectDroppedFiles,
  SUBTITLE_RE,
  FONT_RE,
  MAX_DROP_FILES,
} from './useFontManager'

defineOptions({ name: 'FontManagerView' })

// 共享状态：主视图创建一次，provide 给全部子组件
const fm = provideFontManager()
const {
  success, showError, warning,
  hasLibrary, librarySaving,
  activeTab, fetchFonts, refreshAll,
  jobsUploading, uploadSubtitles,
  tempUploading, uploadTempFontsFiles,
  openSettings, openFolderPicker,
  showFolderBrowser, folderTitle, folderInitial, onFolderSelected,
} = fm

// ── 全局拖拽路由：按文件类型自动分流 ──────────────────────
// 字幕(.ass/.ssa) → 切到「字幕任务」并建任务；字体(ttf/otf/…) → 切到「临时字体」并进临时池。
// 监听挂在 document 上（本页激活期间），页面任意位置拖入都有效；
// 卡片自己的 drop 会 preventDefault，这里通过 defaultPrevented 判断不重复处理。
const pageDragActive = ref(false)
const pageCollecting = ref(false)
const pageDragging = computed(() => pageDragActive.value || pageCollecting.value)
/** dragenter/dragleave 成对触发（子元素间移动也会触发），用计数器维持状态稳定 */
let dragDepth = 0

function hasFiles(e: DragEvent): boolean {
  return Array.from(e.dataTransfer?.types || []).includes('Files')
}

function onDocDragEnter(e: DragEvent) {
  if (!hasFiles(e)) return
  dragDepth += 1
  pageDragActive.value = true
}

function onDocDragOver(e: DragEvent) {
  // 必须 prevent，否则浏览器会打开文件而不是触发 drop
  if (hasFiles(e)) e.preventDefault()
}

function onDocDragLeave(e: DragEvent) {
  if (!hasFiles(e)) return
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) pageDragActive.value = false
}

async function onDocDrop(e: DragEvent) {
  dragDepth = 0
  pageDragActive.value = false
  // 上传卡片 / 临时字体卡片已处理过（它们调用过 preventDefault），不重复处理
  if (e.defaultPrevented) return
  const dt = e.dataTransfer
  if (!dt) return
  e.preventDefault()

  // drop 时统一按扩展名分流
  pageCollecting.value = true
  try {
    const collected = await collectDroppedFiles(e, /.*/)
    const files = collected ? collected.files : Array.from(dt.files || [])

    const subtitles = files.filter((f) => SUBTITLE_RE.test(f.name))
    const fonts = files.filter((f) => FONT_RE.test(f.name))
    const others = files.length - subtitles.length - fonts.length

    if (collected?.truncated) {
      warning(`拖入的文件过多，仅收集前 ${MAX_DROP_FILES} 个文件`)
    }
    if (others > 0) {
      warning(`已忽略 ${others} 个不支持的文件（仅支持 .ass/.ssa 字幕与常见字体格式）`)
    }

    if (subtitles.length) {
      activeTab.value = 'jobs'
      await uploadSubtitles(subtitles)
    }
    if (fonts.length) {
      activeTab.value = 'temp'
      await uploadTempFontsFiles(fonts)
    }
    if (!files.length) {
      warning('没有找到可处理的文件（支持 .ass/.ssa 字幕与字体文件）')
    }
  } catch (err: any) {
    showError(err?.message || '读取拖入内容失败')
  } finally {
    pageCollecting.value = false
  }
}

onMounted(() => {
  document.addEventListener('dragenter', onDocDragEnter)
  document.addEventListener('dragover', onDocDragOver)
  document.addEventListener('dragleave', onDocDragLeave)
  document.addEventListener('drop', onDocDrop)
})

onUnmounted(() => {
  document.removeEventListener('dragenter', onDocDragEnter)
  document.removeEventListener('dragover', onDocDragOver)
  document.removeEventListener('dragleave', onDocDragLeave)
  document.removeEventListener('drop', onDocDrop)
})

// 帮助对话框 ref（open 由子组件 expose；FontStatusBar 通过 emit 请求打开）
const helpDialogRef = ref<InstanceType<typeof FontHelpDialog> | null>(null)

// 注册动态顶栏 Tab（与 SubscriptionView 同款：Tab 嵌在顶栏内）
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '字幕任务', tab: 'jobs' },
    { title: '字体库', tab: 'library' },
    { title: '临时字体', tab: 'temp' },
  ],
  modelValue: activeTab,
})

onMounted(async () => {
  await refreshAll()
  // 预取字体明细，切到字体库 Tab 时不会先闪一下空表
  await fetchFonts()
})

// 未配置字体库时的引导
async function pickLibraryFolder(path: string) {
  await onFolderSelected(path)
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- ══ 顶部状态条（常驻） ══ -->
    <FontStatusBar
      @open-settings="openSettings"
      @pick-library="openFolderPicker({ type: 'library' })"
      @open-help="helpDialogRef?.open()"
    />

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

    <!-- ══ Tab 内容 ══ -->
    <v-window v-else v-model="activeTab">
      <v-window-item value="jobs">
        <JobsTab />
      </v-window-item>
      <v-window-item value="library">
        <LibraryTab />
      </v-window-item>
      <v-window-item value="temp">
        <TempFontsTab />
      </v-window-item>
    </v-window>

    <!-- ══ 设置 / 帮助 对话框 ══ -->
    <FontSettingsDialog />
    <FontHelpDialog ref="helpDialogRef" />

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
/* 页面级拖拽提示浮层：不拦截指针（drop 仍落到容器上） */
.drag-hint-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-surface), 0.72);
  backdrop-filter: blur(2px);
  pointer-events: none;
}
.drag-hint-card {
  padding: 28px 40px;
  border-radius: 16px;
  border: 2px dashed rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-surface), 0.92);
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
}
</style>
