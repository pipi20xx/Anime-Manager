<script setup lang="ts">
import { onMounted, ref, nextTick, h, computed } from 'vue'
import { 
  NButton, NIcon, NBreadcrumb, NBreadcrumbItem,
  NList, NListItem, NSpace, NDivider,
  NDropdown, NModal, NCard, NDescriptions, NDescriptionsItem,
  useDialog
} from 'naive-ui'
import {
  ArrowUpwardOutlined as UpIcon,
  RefreshOutlined as RefreshIcon,
  ChevronRightOutlined as NextIcon,
  DriveFileMoveOutlined as OrganizeIcon,
  DescriptionOutlined as FileIcon,
  ContentCopyOutlined as CopyIcon,
  ContentPasteOutlined as PasteIcon,
  DeleteOutlined as DeleteIcon,
  InfoOutlined as InfoIcon,
  LinkOutlined as PathIcon,
  ContentCutOutlined as CutIcon
} from '@vicons/material'

import ManualOrganizeModal from '../../components/ManualOrganizeModal.vue'
import RecognitionModal from '../../components/RecognitionModal.vue'
import ExecutionLogModal from '../../components/ExecutionLogModal.vue'
import { useFileBrowserView } from '../../composables/views/useFileBrowserView'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  API_BASE,
  currentPath,
  parentPath,
  items,
  loading,
  recognizingPath,
  availableRules,
  defaultTask,
  breadcrumbParts,
  showManualModal,
  showResultModal,
  showExecModal,
  selectedFile,
  recognitionData,
  previewPath,
  isRecogLoading,
  isRenaming,
  execLogs,
  scanningStatus,
  isRunning,
  isDryRun,
  currentManualTask,
  clipboard,
  showInfoModal,
  fileInfo,
  fetchFiles,
  deleteItem,
  copyToClipboard,
  pasteItem,
  getFileInfo,
  copyPath,
  loadConfig,
  recognizeFile,
  handleRename,
  runManualOrganize,
  runManualOrganizeBackground,
  commitBatch,
  getFileIcon
} = useFileBrowserView()

const dialog = useDialog()
const showContextMenu = ref(false)
const x = ref(0)
const y = ref(0)
const contextMenuItem = ref<any>(null)

const menuOptions = computed(() => {
  const options: any[] = []
  
  if (contextMenuItem.value) {
    options.push({
      label: '复制',
      key: 'copy',
      icon: () => h(NIcon, null, { default: () => h(CopyIcon) })
    })
    options.push({
      label: '剪切',
      key: 'move',
      icon: () => h(NIcon, null, { default: () => h(CutIcon) })
    })
    options.push({
      label: '复制路径',
      key: 'copyPath',
      icon: () => h(NIcon, null, { default: () => h(PathIcon) })
    })
    options.push({
      label: '删除',
      key: 'delete',
      icon: () => h(NIcon, null, { default: () => h(DeleteIcon) })
    })
    options.push({
      label: '详情',
      key: 'info',
      icon: () => h(NIcon, null, { default: () => h(InfoIcon) })
    })
  }

  if (clipboard.value) {
    options.push({ type: 'divider', key: 'd1' })
    options.push({
      label: `粘贴: ${clipboard.value.name}`,
      key: 'paste',
      icon: () => h(NIcon, null, { default: () => h(PasteIcon) })
    })
  }

  return options
})

const handleContextMenu = (e: MouseEvent, item: any) => {
  e.preventDefault()
  showContextMenu.value = false
  nextTick(() => {
    contextMenuItem.value = item
    showContextMenu.value = true
    x.value = e.clientX
    y.value = e.clientY
  })
}

const handleMenuSelect = (key: string) => {
  showContextMenu.value = false
  const item = contextMenuItem.value
  switch (key) {
    case 'copy': copyToClipboard(item, 'copy'); break
    case 'move': copyToClipboard(item, 'move'); break
    case 'copyPath': copyPath(item.path); break
    case 'delete': 
      dialog.warning({
        title: '确认删除',
        content: `你确定要永久删除 "${item.name}" 吗？此操作不可撤销。`,
        action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
          h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
          h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { deleteItem(item.path); dialog.destroyAll() } }, { default: () => '确定删除' })
        ])
      })
      break
    case 'info': getFileInfo(item.path); break
    case 'paste': pasteItem(); break
  }
}

const formatSize = (bytes: number | null) => {
  if (bytes === null) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

onMounted(() => {
  fetchFiles('/')
  loadConfig()
})
</script>

<template>
  <div class="file-browser">
    <div class="page-header">
      <div>
        <h1>文件浏览</h1>
        <div class="subtitle">文件资源管理器</div>
      </div>
      <n-button v-bind="getButtonStyle('primary')" size="large" @click="showManualModal = true">
        整理当前目录
      </n-button>
    </div>

    <div class="browser-container">
      <!-- 顶部工具栏：整合面包屑和操作 -->
      <div class="browser-toolbar">
        <n-space align="center" justify="space-between" class="w-100">
          <n-space align="center" size="large">
            <n-button v-bind="getButtonStyle('icon')" :disabled="!parentPath || currentPath === '/'" @click="parentPath && fetchFiles(parentPath)">
              <template #icon><n-icon><UpIcon /></n-icon></template>
            </n-button>
            <n-breadcrumb>
              <n-breadcrumb-item @click="fetchFiles('/')" style="cursor: pointer">/</n-breadcrumb-item>
              <n-breadcrumb-item 
                v-for="part in breadcrumbParts" 
                :key="part.path" 
                @click="fetchFiles(part.path)" 
                style="cursor: pointer"
              >
                {{ part.name }}
              </n-breadcrumb-item>
            </n-breadcrumb>
          </n-space>
          <n-space>
            <n-button v-bind="getButtonStyle('icon')" @click="fetchFiles(currentPath)">
              <template #icon><n-icon><RefreshIcon /></n-icon></template>
            </n-button>
          </n-space>
        </n-space>
      </div>

      <!-- 文件列表 -->
      <div class="list-wrapper" @contextmenu="handleContextMenu($event, null)">
        <n-list hoverable clickable class="modern-list">
          <n-list-item 
            v-for="item in items" 
            :key="item.path" 
            @click="item.is_dir && fetchFiles(item.path)"
            @contextmenu.stop="handleContextMenu($event, item)"
          >
            <template #prefix>
              <div class="file-icon-box" :class="{ 'is-dir': item.is_dir }">
                <n-icon size="20"><component :is="getFileIcon(item)" /></n-icon>
              </div>
            </template>
            <div class="file-info">
              <div class="file-name">{{ item.name }}</div>
              <div class="file-meta">
                <span>{{ (item.size/1024/1024).toFixed(2) }} MB</span>
                <n-divider vertical />
                <span>{{ new Date(item.mtime*1000).toLocaleString() }}</span>
              </div>
            </div>
            <template #suffix>
              <n-button v-if="!item.is_dir" size="small" secondary round type="info" :loading="recognizingPath === item.path" @click.stop="recognizeFile(item)">
                识别测试
              </n-button>
              <n-icon v-else color="#444" size="20"><NextIcon /></n-icon>
            </template>
          </n-list-item>
        </n-list>
      </div>

      <!-- 底部轻量信息显示 -->
      <div class="browser-footer">
        <div class="count-info">
          <n-icon size="16"><FileIcon /></n-icon>
          <span>当前目录共 <b>{{ items.length }}</b> 项内容</span>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <ManualOrganizeModal 
      v-model:show="showManualModal"
      :current-path="currentPath"
      :available-rules="availableRules"
      :default-task="defaultTask"
      :api-base="API_BASE"
      @run="runManualOrganize"
      @run-background="runManualOrganizeBackground"
    />

    <RecognitionModal 
      v-model:show="showResultModal"
      :file="selectedFile"
      :data="recognitionData"
      :preview-path="previewPath"
      :loading="isRecogLoading"
      :is-renaming="isRenaming"
      :api-base="API_BASE"
      :available-rules="availableRules"
      @recognize="p => recognizeFile(selectedFile!, p)"
      @rename="handleRename"
    />

    <ExecutionLogModal 
      v-model:show="showExecModal"
      :is-dry-run="isDryRun"
      :is-running="isRunning"
      :logs="execLogs"
      :scanning-status="scanningStatus"
      :target-dir="currentManualTask?.target_dir || ''"
      @commit="commitBatch"
    />

    <n-dropdown
      placement="bottom-start"
      trigger="manual"
      :x="x"
      :y="y"
      :options="menuOptions"
      :show="showContextMenu"
      :on-clickoutside="() => showContextMenu = false"
      @select="handleMenuSelect"
    />

    <n-modal v-model:show="showInfoModal">
      <n-card
        style="width: 600px"
        title="项目详情"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <n-descriptions label-placement="left" bordered :column="1">
          <n-descriptions-item label="名称">{{ fileInfo?.name }}</n-descriptions-item>
          <n-descriptions-item label="路径">{{ fileInfo?.path }}</n-descriptions-item>
          <n-descriptions-item label="类型">{{ fileInfo?.is_dir ? '文件夹' : '文件' }}</n-descriptions-item>
          <n-descriptions-item v-if="!fileInfo?.is_dir" label="大小">{{ formatSize(fileInfo?.size) }}</n-descriptions-item>
          <n-descriptions-item label="修改时间">{{ new Date(fileInfo?.mtime * 1000).toLocaleString() }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ new Date(fileInfo?.ctime * 1000).toLocaleString() }}</n-descriptions-item>
          <n-descriptions-item label="权限">{{ fileInfo?.mode }}</n-descriptions-item>
        </n-descriptions>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showInfoModal = false">关闭</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<style scoped>
.file-browser { width: 100%; padding-bottom: 40px; }
.browser-container { display: flex; flex-direction: column; gap: 16px; }

/* 顶部工具栏 */
.browser-toolbar { 
  background: var(--app-surface-subtle); 
  padding: 12px 20px; 
  border-radius: var(--card-border-radius, 12px); 
  border: 1px solid var(--app-border-light); 
}

/* 现代列表样式 */
.list-wrapper { 
  background: var(--app-surface-card); 
  border-radius: var(--card-border-radius, 12px); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; 
}
.modern-list :deep(.n-list-item) { padding: 12px 20px !important; transition: background 0.2s; border-bottom: 1px solid var(--app-border-light); }
.modern-list :deep(.n-list-item:last-child) { border-bottom: none; }

.file-icon-box { 
  width: 40px; height: 40px; 
  border-radius: var(--button-border-radius, 10px); 
  display: flex; align-items: center; justify-content: center; 
  background: color-mix(in srgb, var(--n-primary-color), transparent 90%); 
  color: var(--n-primary-color); 
}
.file-icon-box.is-dir { 
  background: color-mix(in srgb, var(--n-info-color), transparent 90%); 
  color: var(--n-info-color); 
}

.file-info .file-name { font-weight: 600; font-size: 15px; color: var(--n-text-color-1); margin-bottom: 4px; }
.file-meta { font-size: 12px; color: var(--n-text-color-3); display: flex; align-items: center; gap: 8px; }

/* 底部页脚 */
.browser-footer { padding: 16px 4px; border-top: 1px solid var(--app-border-light); margin-top: 8px; }
.count-info { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--n-text-color-3); }
.count-info b { color: var(--n-primary-color); }

.w-100 { width: 100%; }
</style>
