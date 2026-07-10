<script setup lang="ts">
import { onMounted, ref, nextTick, h, computed } from 'vue'
import { 
  NButton, NIcon, NBreadcrumb, NBreadcrumbItem,
  NList, NListItem, NSpace, NDivider,
  NDropdown, NModal, NCard, NDescriptions, NDescriptionsItem,
  NInput, NText,
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
  ContentCutOutlined as CutIcon,
  StarOutlineOutlined as StarIcon,
  StarOutlined as StarFilledIcon,
  FolderOpenOutlined as FolderOpenIcon,
  DriveFileMoveOutlined as GoToIcon
} from '@vicons/material'

import ManualOrganizeModal from '../../components/desktop/ManualOrganizeModalDesktop.vue'
import RecognitionModal from '../../components/desktop/RecognitionModalDesktop.vue'
import ExecutionLogModal from '../../components/ExecutionLogModal.vue'
import { useFileBrowserView } from '../../composables/views/useFileBrowserView'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  API_BASE,
  currentPath,
  parentPath,
  items,
  loading,
  showSkeleton,
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
  favorites,
  showGoToPathModal,
  goToPathInput,
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
  getFileIcon,
  addFavorite,
  removeFavorite,
  goToPath
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

const toggleCurrentFavorite = () => {
  const isFavorite = favorites.value.some(f => f.path === currentPath.value)
  if (isFavorite) {
    removeFavorite(currentPath.value)
  } else {
    addFavorite(currentPath.value)
  }
}

const handleFavoriteClick = (path: string) => {
  fetchFiles(path)
}

const formatSize = (bytes: number | null) => {
  if (bytes === null) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const textMutedColor = computed(() => {
  return 'var(--text-muted)'
})

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

    <div class="browser-layout">
      <!-- 左侧收藏夹侧边栏 -->
      <div class="favorites-sidebar">
        <div class="favorites-header">
          <n-icon size="18" :color="'var(--n-primary-color)'"><StarFilledIcon /></n-icon>
          <span class="favorites-title">收藏夹</span>
        </div>
        <div class="favorites-list">
          <div 
            v-for="fav in favorites" 
            :key="fav.path"
            class="favorite-item"
            :class="{ active: fav.path === currentPath }"
          >
            <div class="favorite-content" @click="handleFavoriteClick(fav.path)">
              <n-icon size="16"><FolderOpenIcon /></n-icon>
              <span class="favorite-name">{{ fav.name }}</span>
            </div>
            <n-button 
              v-bind="getButtonStyle('iconDanger')" 
              size="tiny"
              class="favorite-delete"
              @click.stop="removeFavorite(fav.path)"
              title="删除收藏"
            >
              <template #icon><n-icon><DeleteIcon /></n-icon></template>
            </n-button>
          </div>
          <div v-if="favorites.length === 0" class="favorites-empty">
            暂无收藏
          </div>
        </div>
      </div>

      <!-- 右侧主内容区 -->
      <div class="browser-main">
        <!-- 顶部工具栏 -->
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
              <!-- 复制当前路径按钮 -->
              <n-button 
                v-bind="getButtonStyle('icon')" 
                @click="copyPath(currentPath)"
                title="复制当前路径"
              >
                <template #icon><n-icon><CopyIcon /></n-icon></template>
              </n-button>
              <!-- 收藏按钮 -->
              <n-button 
                v-bind="getButtonStyle('icon')" 
                :type="favorites.some(f => f.path === currentPath) ? 'warning' : 'default'"
                @click="toggleCurrentFavorite"
                title="点击收藏/取消收藏当前目录"
              >
                <template #icon>
                  <n-icon>
                    <component :is="favorites.some(f => f.path === currentPath) ? StarFilledIcon : StarIcon" />
                  </n-icon>
                </template>
              </n-button>
              <n-button v-bind="getButtonStyle('icon')" @click="showGoToPathModal = true" title="前往指定路径">
                <template #icon><n-icon><GoToIcon /></n-icon></template>
              </n-button>
              <n-button v-bind="getButtonStyle('icon')" @click="fetchFiles(currentPath)" title="刷新">
                <template #icon><n-icon><RefreshIcon /></n-icon></template>
              </n-button>
            </n-space>
          </n-space>
        </div>

        <!-- 文件列表 -->
        <div class="list-wrapper" @contextmenu="handleContextMenu($event, null)">
          <!-- 顶部加载进度条 -->
          <Transition name="loading-bar">
            <div v-if="loading" class="loading-bar">
              <div class="loading-bar-inner"></div>
            </div>
          </Transition>

          <!-- 骨架屏 -->
          <Transition name="skeleton-fade">
            <div v-if="showSkeleton" class="skeleton-list">
              <div v-for="i in 8" :key="i" class="skeleton-item">
                <div class="skeleton-icon"></div>
                <div class="skeleton-text-area">
                  <div class="skeleton-line skeleton-line-1"></div>
                  <div class="skeleton-line skeleton-line-2"></div>
                </div>
                <div class="skeleton-suffix"></div>
              </div>
            </div>
          </Transition>

          <!-- 文件列表 -->
          <Transition name="list-fade">
            <n-list v-if="!showSkeleton" hoverable clickable class="modern-list" :key="currentPath">
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
                    单文件识别
                  </n-button>
                  <n-icon v-else :color="textMutedColor" size="20"><NextIcon /></n-icon>
                </template>
              </n-list-item>
            </n-list>
          </Transition>
        </div>

        <!-- 底部轻量信息显示 -->
        <div class="browser-footer">
          <div class="count-info">
            <n-icon size="16"><FileIcon /></n-icon>
            <span>当前目录共 <b>{{ items.length }}</b> 项内容</span>
          </div>
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

    <!-- 前往指定路径弹框 -->
    <n-modal v-model:show="showGoToPathModal" preset="card" title="前往指定路径" style="width: 500px" :bordered="false">
      <n-space vertical>
        <n-input
          v-model:value="goToPathInput"
          placeholder="请输入路径，如 /mnt/media/anime"
          size="large"
          @keydown.enter="goToPath(goToPathInput)"
        >
          <template #prefix>
            <n-icon><FolderOpenIcon /></n-icon>
          </template>
        </n-input>
        <n-text depth="3" style="font-size: 12px;">
          提示：路径以 / 开头，支持直接粘贴完整路径
        </n-text>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('secondary')" @click="showGoToPathModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" type="primary" @click="goToPath(goToPathInput)">前往</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.file-browser { width: 100%; padding-bottom: 40px; }

/* 布局：左侧收藏夹 + 右侧主内容 */
.browser-layout {
  display: flex;
  gap: 16px;
  min-height: calc(100vh - 200px);
}

/* 左侧收藏夹侧边栏 */
.favorites-sidebar {
  width: 200px;
  flex-shrink: 0;
  background: var(--app-surface-card-mixed);
  border-radius: var(--card-border-radius, 12px);
  border: 1px solid var(--app-border-light);
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}

.favorites-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-border-light);
  margin-bottom: 12px;
}

.favorites-title {
  font-weight: 600;
  font-size: var(--text-md);
  color: var(--text-primary);
}

.favorites-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.favorite-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: var(--button-border-radius, 8px);
  cursor: pointer;
  transition: all var(--transition-fast);
  color: var(--text-secondary);
  min-width: 0;
  box-sizing: border-box;
}

.favorite-item:hover {
  background: var(--app-surface-hover);
  color: var(--text-primary);
}

.favorite-item:hover .favorite-delete {
  opacity: 1;
}

.favorite-item.active {
  background: var(--n-primary-color-suppl, rgba(24, 160, 88, 0.1));
  color: var(--n-primary-color);
}

.favorite-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.favorite-name {
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.favorite-delete {
  opacity: 0;
  transition: opacity var(--transition-fast);
  padding: 4px !important;
  height: auto !important;
}

.favorite-delete:hover {
  color: var(--n-error-color) !important;
}

.favorites-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

/* 右侧主内容区 */
.browser-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 顶部工具栏 */
.browser-toolbar { 
  background: var(--app-surface-card-mixed); 
  padding: 12px 20px; 
  border-radius: var(--card-border-radius, 12px); 
  border: 1px solid var(--app-border-light); 
}

/* 现代列表样式 */
.list-wrapper { 
  background: var(--app-surface-card-mixed); 
  border-radius: var(--card-border-radius, 12px); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; 
  flex: 1;
  position: relative;
}

/* 顶部加载进度条 */
.loading-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  z-index: 10;
  overflow: hidden;
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 15%, transparent);
}
.loading-bar-inner {
  height: 100%;
  width: 40%;
  background: var(--n-primary-color, #18a058);
  border-radius: 0 4px 4px 0;
  animation: loading-slide 1.2s ease-in-out infinite;
}
@keyframes loading-slide {
  0% { transform: translateX(-100%); }
  50% { transform: translateX(150%); }
  100% { transform: translateX(350%); }
}
.loading-bar-enter-active,
.loading-bar-leave-active {
  transition: opacity 0.2s ease;
}
.loading-bar-enter-from,
.loading-bar-leave-to {
  opacity: 0;
}

/* 骨架屏 */
.skeleton-list {
  padding: 12px 20px;
}
.skeleton-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--app-border-light);
}
.skeleton-item:last-child {
  border-bottom: none;
}
.skeleton-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--card-border-radius, var(--button-border-radius, 10px));
  flex-shrink: 0;
  background: linear-gradient(
    90deg,
    var(--app-surface-card-mixed) 25%,
    color-mix(in srgb, var(--app-surface-card-mixed), rgba(128,128,128,0.12)) 50%,
    var(--app-surface-card-mixed) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
.skeleton-text-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--app-surface-card-mixed) 25%,
    color-mix(in srgb, var(--app-surface-card-mixed), rgba(128,128,128,0.12)) 50%,
    var(--app-surface-card-mixed) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
.skeleton-line-1 { width: 45%; }
.skeleton-line-2 { width: 30%; height: 12px; }
.skeleton-suffix {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(
    90deg,
    var(--app-surface-card-mixed) 25%,
    color-mix(in srgb, var(--app-surface-card-mixed), rgba(128,128,128,0.12)) 50%,
    var(--app-surface-card-mixed) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
@keyframes skeleton-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

/* 骨架屏淡入淡出 */
.skeleton-fade-enter-active {
  transition: opacity 0.2s ease;
}
.skeleton-fade-leave-active {
  transition: opacity 0.15s ease;
}
.skeleton-fade-enter-from,
.skeleton-fade-leave-to {
  opacity: 0;
}

/* 列表淡入动画 */
.list-fade-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.list-fade-leave-active {
  transition: opacity 0.1s ease;
}
.list-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.list-fade-leave-to {
  opacity: 0;
}
.modern-list :deep(.n-list-item) { padding: 12px 20px !important; transition: background var(--transition-fast); border-bottom: 1px solid var(--app-border-light); }
.modern-list :deep(.n-list-item:last-child) { border-bottom: none; }

.file-icon-box {
  width: 40px; height: 40px;
  border-radius: var(--card-border-radius, var(--button-border-radius, 10px));
  display: flex; align-items: center; justify-content: center;
  background: var(--app-surface-card-mixed);
  color: var(--text-secondary);
  border: 1px solid var(--app-border-light);
}
.file-icon-box.is-dir {
  background: var(--app-surface-card-mixed);
  color: var(--text-secondary);
  border: 1px solid var(--app-border-light);
}

.file-info .file-name { font-weight: 600; font-size: var(--text-xl); color: var(--text-primary); margin-bottom: 4px; }
.file-meta { font-size: var(--text-base); color: var(--text-tertiary); display: flex; align-items: center; gap: 8px; }

/* 底部页脚 */
.browser-footer { padding: 16px 4px; border-top: 1px solid var(--app-border-light); margin-top: 8px; }
.count-info { display: flex; align-items: center; gap: 8px; font-size: var(--text-md); color: var(--text-tertiary); }
.count-info b { color: var(--n-primary-color); }

.w-100 { width: 100%; }
</style>
