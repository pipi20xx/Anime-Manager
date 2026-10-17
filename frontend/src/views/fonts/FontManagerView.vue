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
import { ref, onMounted } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import { EmptyState } from '@/components/common'
import FolderBrowserModal from '@/views/organizer/FolderBrowserModal.vue'
import FontStatusBar from './FontStatusBar.vue'
import JobsTab from './JobsTab.vue'
import LibraryTab from './LibraryTab.vue'
import TempFontsTab from './TempFontsTab.vue'
import FontSettingsDialog from './FontSettingsDialog.vue'
import FontHelpDialog from './FontHelpDialog.vue'
import { provideFontManager } from './useFontManager'

defineOptions({ name: 'FontManagerView' })

// 共享状态：主视图创建一次，provide 给全部子组件
const fm = provideFontManager()
const {
  status, statusLoading, binary, hasLibrary, indexReady,
  activeTab, fetchFonts, refreshAll,
  librarySaving,
  openSettings, openFolderPicker,
  showFolderBrowser, folderTitle, folderInitial, onFolderSelected,
} = fm

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
