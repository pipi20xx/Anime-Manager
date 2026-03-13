<script setup lang="ts">
import { onMounted, ref, nextTick, computed, h } from 'vue'
import { 
  NButton, NIcon, NList, NListItem, NSpace, NDivider,
  NDropdown, NModal, NCard, NDescriptions, NDescriptionsItem,
  useDialog, useMessage
} from 'naive-ui'
import {
  ArrowUpwardOutlined as UpIcon,
  RefreshOutlined as RefreshIcon,
  DriveFileMoveOutlined as OrganizeIcon,
  DescriptionOutlined as FileIcon,
  ContentCopyOutlined as CopyIcon,
  ContentPasteOutlined as PasteIcon,
  DeleteOutlined as DeleteIcon,
  InfoOutlined as InfoIcon,
  LinkOutlined as PathIcon,
  ContentCutOutlined as CutIcon,
  MoreVertOutlined as MoreIcon
} from '@vicons/material'

import ManualOrganizeModal from '../../components/ManualOrganizeModal.vue'
import RecognitionModal from '../../components/RecognitionModal.vue'
import ExecutionLogModal from '../../components/ExecutionLogModal.vue'
import { useFileBrowserView } from '../../composables/views/useFileBrowserView'
import { useBackClose } from '../../composables/useBackClose'
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
const message = useMessage()

// Apply Back Button support to Modals
useBackClose(showManualModal)
useBackClose(showResultModal)
useBackClose(showExecModal)
useBackClose(showInfoModal)

const showContextMenu = ref(false)
const x = ref(0)
const y = ref(0)
const contextMenuItem = ref<any>(null)

const menuOptions = computed(() => {
  if (!contextMenuItem.value) return []
  return [
    {
      label: '复制',
      key: 'copy',
      icon: () => h(NIcon, null, { default: () => h(CopyIcon) })
    },
    {
      label: '剪切',
      key: 'move',
      icon: () => h(NIcon, null, { default: () => h(CutIcon) })
    },
    {
      label: '复制路径',
      key: 'copyPath',
      icon: () => h(NIcon, null, { default: () => h(PathIcon) })
    },
    {
      label: '删除',
      key: 'delete',
      icon: () => h(NIcon, null, { default: () => h(DeleteIcon) })
    },
    {
      label: '详情',
      key: 'info',
      icon: () => h(NIcon, null, { default: () => h(InfoIcon) })
    }
  ]
})

let pressTimer: any = null

const handleTouchStart = (e: TouchEvent, item: any) => {
  pressTimer = setTimeout(() => {
    handleContextMenuMobile(e, item)
  }, 600)
}

const handleTouchEnd = () => {
  clearTimeout(pressTimer)
}

const handleContextMenuMobile = (e: TouchEvent | MouseEvent, item: any) => {
  if (e instanceof MouseEvent) e.preventDefault()
  showContextMenu.value = false
  nextTick(() => {
    contextMenuItem.value = item
    showContextMenu.value = true
    if (e instanceof TouchEvent) {
      x.value = e.touches[0].clientX
      y.value = e.touches[0].clientY
    } else {
      x.value = e.clientX
      y.value = e.clientY
    }
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
        content: `确定永久删除 "${item.name}" 吗？`,
        action: () => h('div', { style: 'display: flex; gap: var(--m-spacing-md); justify-content: flex-end; margin-top: var(--m-spacing-lg);' }, [
          h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
          h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { deleteItem(item.path); dialog.destroyAll() } }, { default: () => '确定' })
        ])
      })
      break
    case 'info': getFileInfo(item.path); break
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

const getShortName = (path: string) => {
  if (path === '/') return '根目录'
  const parts = path.split('/').filter(x => x)
  return parts[parts.length - 1] || 'Unknown'
}
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <!-- 页面头部 -->
    <div class="m-header m-header-plain">
      <h1 class="m-header-title">文件浏览</h1>
      <n-button v-bind="getButtonStyle('icon')" @click="showManualModal = true">
        <template #icon><n-icon><OrganizeIcon /></n-icon></template>
      </n-button>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="path-display">
         <span class="path-text m-truncate">{{ getShortName(currentPath) }}</span>
      </div>
      <n-space>
        <n-button v-bind="getButtonStyle('icon')" size="small" :disabled="!parentPath || currentPath === '/'" @click="parentPath && fetchFiles(parentPath)">
          <template #icon><n-icon><UpIcon /></n-icon></template>
        </n-button>
        <n-button v-bind="getButtonStyle('icon')" size="small" @click="fetchFiles(currentPath)">
          <template #icon><n-icon><RefreshIcon /></n-icon></template>
        </n-button>
      </n-space>
    </div>

    <!-- 文件列表 -->
    <div class="m-page-scrollable m-content-compact">
      <n-list hoverable clickable class="mobile-file-list">
        <n-list-item 
          v-for="item in items" 
          :key="item.path" 
          @click="item.is_dir && fetchFiles(item.path)"
          @touchstart="handleTouchStart($event, item)"
          @touchend="handleTouchEnd"
          @contextmenu.prevent="handleContextMenuMobile($event, item)"
          class="m-touchable"
        >
          <template #prefix>
            <div class="file-icon-box" :class="{ 'is-dir': item.is_dir }">
              <n-icon size="24"><component :is="getFileIcon(item)" /></n-icon>
            </div>
          </template>
          <div class="file-info">
            <div class="file-name m-truncate">{{ item.name }}</div>
            <div class="file-meta">
              <span>{{ formatSize(item.size) }}</span>
              <n-divider vertical />
              <span>{{ new Date(item.mtime * 1000).toLocaleDateString() }}</span>
            </div>
          </div>
          <template #suffix>
             <n-space>
               <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop="handleContextMenuMobile($event, item)">
                 <template #icon><n-icon><MoreIcon /></n-icon></template>
               </n-button>
               <n-button v-if="!item.is_dir" v-bind="getButtonStyle('primary')" size="tiny" :loading="recognizingPath === item.path" @click.stop="recognizeFile(item)">
                  识别
                </n-button>
             </n-space>
          </template>
        </n-list-item>
      </n-list>
    </div>

    <!-- 粘贴按钮 -->
    <transition name="fade">
      <div v-if="clipboard" class="paste-fab m-touchable" @click="pasteItem">
        <n-icon size="24"><PasteIcon /></n-icon>
        <span>粘贴</span>
      </div>
    </transition>

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

    <!-- 文件详情弹窗 -->
    <n-modal v-model:show="showInfoModal">
      <n-card
        style="width: 90vw; max-width: 400px"
        title="项目详情"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <n-descriptions label-placement="left" bordered :column="1">
          <n-descriptions-item label="名称">{{ fileInfo?.name }}</n-descriptions-item>
          <n-descriptions-item label="类型">{{ fileInfo?.is_dir ? '文件夹' : '文件' }}</n-descriptions-item>
          <n-descriptions-item v-if="!fileInfo?.is_dir" label="大小">{{ formatSize(fileInfo?.size) }}</n-descriptions-item>
          <n-descriptions-item label="修改时间">{{ new Date(fileInfo?.mtime * 1000).toLocaleString() }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ new Date(fileInfo?.ctime * 1000).toLocaleString() }}</n-descriptions-item>
          <n-descriptions-item label="权限">{{ fileInfo?.mode }}</n-descriptions-item>
          <n-descriptions-item label="完整路径">
            <div style="word-break: break-all; font-size: var(--m-text-sm)">{{ fileInfo?.path }}</div>
          </n-descriptions-item>
        </n-descriptions>
        <template #footer>
          <n-space justify="end">
            <n-button v-bind="getButtonStyle('secondary')" @click="showInfoModal = false">关闭</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<style scoped>
.toolbar {
  padding: var(--m-spacing-sm) var(--m-spacing-lg) var(--m-spacing-md);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
}

.path-display {
  font-weight: 600;
  font-size: var(--m-text-lg);
  max-width: 60%;
}

.mobile-file-list {
  background: transparent;
}

.mobile-file-list :deep(.n-list-item) {
  padding: var(--m-spacing-md);
  margin-bottom: var(--m-spacing-sm);
  border-radius: var(--m-radius-lg);
  background-color: var(--app-surface-card);
  border: 1px solid var(--border-light);
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.mobile-file-list :deep(.n-list-item):active {
  transform: scale(0.98);
  box-shadow: var(--shadow-sm);
}

.file-icon-box {
  width: 42px;
  height: 42px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-surface-inner);
  color: var(--n-primary-color);
  margin-right: var(--m-spacing-md);
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.file-icon-box.is-dir {
  background: var(--warning-light);
  color: var(--n-warning-color);
  border-color: transparent;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-weight: 600;
  font-size: var(--m-text-md);
  line-height: 1.4;
  margin-bottom: var(--m-spacing-xs);
}

.file-meta {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: var(--m-spacing-xs);
}

.paste-fab {
  position: fixed;
  bottom: calc(var(--m-safe-bottom) + var(--m-spacing-lg));
  right: var(--m-spacing-lg);
  background-color: var(--n-primary-color);
  color: var(--text-primary);
  padding: var(--m-spacing-md) var(--m-spacing-xl);
  border-radius: var(--m-radius-full);
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  font-weight: 600;
  font-size: var(--m-text-sm);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
