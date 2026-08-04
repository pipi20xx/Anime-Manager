<script setup lang="ts">
/**
 * FileBrowserView — 文件浏览器
 *
 * 功能对标旧前端 FileBrowserViewDesktop:
 * - 面包屑导航 + 收藏夹侧栏（服务端存储）
 * - 文件/文件夹列表 + 右键菜单 (复制/剪切/粘贴/删除/详情)
 * - 单文件识别（识别弹窗 + 重命名预览 + 哈希计算 + 审计日志）
 * - 整理当前目录（Ad-hoc 流式执行 + dry-run 预览 + 批量提交）
 * - 前往指定路径
 * - 骨架屏加载
 */
import { ref, computed, onMounted } from 'vue'
import { organizerApi, recognitionApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import RecognitionModal from './organizer/RecognitionModal.vue'
import ManualOrganizeModal from './organizer/ManualOrganizeModal.vue'
import ExecutionLogModal from './organizer/ExecutionLogModal.vue'

defineOptions({ name: 'FileBrowserView' })

const { success, error: showError, warning, info } = useNotification()
const { confirm } = useConfirm()

// --- 状态 ---
const currentPath = ref('/')
const items = ref<any[]>([])
const loading = ref(false)
const showSkeleton = ref(false)

// 收藏夹 (服务端存储)
const favorites = ref<{ name: string; path: string }[]>([])

// 剪贴板
const clipboard = ref<{ item: any; mode: 'copy' | 'move' } | null>(null)

// 上下文菜单
const contextMenu = ref({ show: false, x: 0, y: 0, item: null as any })

// 收藏夹抽屉
const showFavDrawer = ref(false)

// 信息 Modal
const showInfoModal = ref(false)
const fileInfo = ref<any>(null)

// 前往路径 Modal
const showGoToModal = ref(false)
const goToPathInput = ref('')

// 识别相关
const recognizingPath = ref('')
const selectedFile = ref<any>(null)
const recognitionData = ref<any>(null)
const showRecognitionModal = ref(false)
const previewPath = ref('')
const isRecogLoading = ref(false)
const isRenaming = ref(false)
const availableRules = ref<any[]>([])
const defaultTask = ref<any>(null)

// 整理目录 Modal
const showManualModal = ref(false)
const organizeTasks = ref<any[]>([])

// 执行日志 Modal
const showExecModal = ref(false)
const execLogs = ref<any[]>([])
const scanningStatus = ref('')
const isRunning = ref(false)
const isDryRun = ref(true)
const currentManualTask = ref<any>(null)

// --- 计算属性 ---
const breadcrumbParts = computed(() => {
  if (currentPath.value === '/') return []
  const parts = currentPath.value.split('/').filter(Boolean)
  return parts.map((name, index) => ({
    name,
    path: '/' + parts.slice(0, index + 1).join('/'),
  }))
})

const parentPath = computed(() => {
  if (currentPath.value === '/') return null
  const parts = currentPath.value.split('/').filter(Boolean)
  if (parts.length <= 1) return '/'
  return '/' + parts.slice(0, -1).join('/')
})

// --- 方法 ---
let skeletonTimer: ReturnType<typeof setTimeout> | null = null

async function fetchFiles(path?: string) {
  const targetPath = path ?? currentPath.value
  currentPath.value = targetPath
  localStorage.setItem('apm_file_browser_last_path', targetPath)
  loading.value = true

  if (skeletonTimer) clearTimeout(skeletonTimer)
  skeletonTimer = setTimeout(() => {
    if (loading.value) showSkeleton.value = true
  }, 200)

  try {
    const res = await organizerApi.listFiles({ path: targetPath })
    const resData = res?.data ?? res
    if (resData?.status === 'success' && resData?.data) {
      currentPath.value = resData.data.current_path || targetPath
      items.value = (resData.data.items || []).sort((a: any, b: any) => {
        if (a.is_dir && !b.is_dir) return -1
        if (!a.is_dir && b.is_dir) return 1
        return a.name.localeCompare(b.name)
      })
    } else {
      const rawItems = Array.isArray(resData) ? resData : (resData?.items || [])
      items.value = rawItems.sort((a: any, b: any) => {
        if (a.is_dir && !b.is_dir) return -1
        if (!a.is_dir && b.is_dir) return 1
        return a.name.localeCompare(b.name)
      })
    }
  } catch (e) {
    showError('加载文件列表失败')
  } finally {
    loading.value = false
    showSkeleton.value = false
    if (skeletonTimer) { clearTimeout(skeletonTimer); skeletonTimer = null }
  }
}

function navigateTo(path: string) {
  if (path === currentPath.value) return
  fetchFiles(path)
}

function goUp() {
  if (parentPath.value) fetchFiles(parentPath.value)
}

function jumpTo(path: string) {
  if (path === currentPath.value) return
  fetchFiles(path)
}

// 文件图标
function getFileIcon(item: any): string {
  if (item.is_dir) return 'mdi-folder'
  const ext = (item.extension || item.name || '').split('.').pop()?.toLowerCase() || ''
  const iconMap: Record<string, string> = {
    mp4: 'mdi-filmstrip', mkv: 'mdi-filmstrip', avi: 'mdi-filmstrip', mov: 'mdi-filmstrip',
    ts: 'mdi-filmstrip', rmvb: 'mdi-filmstrip', flv: 'mdi-filmstrip', wmv: 'mdi-filmstrip',
    mp3: 'mdi-music', flac: 'mdi-music', wav: 'mdi-music', aac: 'mdi-music',
    jpg: 'mdi-image', jpeg: 'mdi-image', png: 'mdi-image', gif: 'mdi-image', webp: 'mdi-image',
    nfo: 'mdi-information-outline', ass: 'mdi-subtitles', srt: 'mdi-subtitles', ssa: 'mdi-subtitles',
    strm: 'mdi-link-variant',
  }
  return iconMap[ext] || 'mdi-file-outline'
}

function formatSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatDate(timestamp: number): string {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString()
}

// --- 收藏夹 (服务端) ---
async function loadConfig() {
  try {
    const config = await configApi.getConfig()
    availableRules.value = config?.rename_rules || []
    if (config?.organize_tasks?.length > 0) {
      defaultTask.value = config.organize_tasks[0]
      organizeTasks.value = config.organize_tasks
    }
    favorites.value = config?.file_browser_favorites || []
  } catch (e) {
    // 静默失败
  }
}

async function addFavorite(path: string) {
  if (favorites.value.some(f => f.path === path)) {
    warning('该路径已在收藏夹中')
    return
  }
  const name = path.split('/').filter(Boolean).pop() || path
  const newFavorites = [...favorites.value, { name, path }]
  try {
    await configApi.saveConfig({ file_browser_favorites: newFavorites })
    favorites.value = newFavorites
    success('已添加到收藏夹')
  } catch (e) {
    showError('添加收藏失败')
  }
}

async function removeFavorite(path: string) {
  const newFavorites = favorites.value.filter(f => f.path !== path)
  try {
    await configApi.saveConfig({ file_browser_favorites: newFavorites })
    favorites.value = newFavorites
    success('已从收藏夹移除')
  } catch (e) {
    showError('移除收藏失败')
  }
}

function isCurrentFavorite(): boolean {
  return favorites.value.some(f => f.path === currentPath.value)
}

function toggleFavorite() {
  if (isCurrentFavorite()) {
    removeFavorite(currentPath.value)
  } else {
    addFavorite(currentPath.value)
  }
}

// --- 右键菜单 ---
function handleContextMenu(e: MouseEvent, item: any | null) {
  e.preventDefault()
  contextMenu.value = {
    show: true,
    x: e.clientX,
    y: e.clientY,
    item,
  }
}

function closeContextMenu() {
  contextMenu.value.show = false
}

function handleContextAction(action: string) {
  const item = contextMenu.value.item
  switch (action) {
    case 'copy': copyToClipboard(item, 'copy'); break
    case 'move': copyToClipboard(item, 'move'); break
    case 'copyPath': copyPath(item?.path || currentPath.value); break
    case 'delete': if (item) deleteItem(item.path); break
    case 'info': if (item) getFileInfo(item.path); break
    case 'paste': pasteItem(); break
  }
}

function copyToClipboard(item: any, mode: 'copy' | 'move') {
  clipboard.value = { item, mode }
  info(`已${mode === 'copy' ? '复制' : '剪切'}: ${item.name}`)
  closeContextMenu()
}

async function pasteItem() {
  if (!clipboard.value) return
  const { item, mode } = clipboard.value
  const dst = currentPath.value === '/' ? `/${item.name}` : `${currentPath.value}/${item.name}`
  if (item.path === dst) {
    warning('源路径与目标路径相同')
    return
  }
  try {
    if (mode === 'copy') {
      await organizerApi.copyFile({ src: item.path, dst })
      success('复制成功')
    } else {
      await organizerApi.moveFile({ src: item.path, dst })
      success('移动成功')
      clipboard.value = null
    }
    fetchFiles()
  } catch (e: any) {
    showError(e?.message || '操作失败')
  }
  closeContextMenu()
}

async function deleteItem(path: string) {
  const ok = await confirm({
    title: '确认删除',
    content: `确定要永久删除 "${path}" 吗？此操作不可撤销。`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    const res = await organizerApi.deleteFile({ path })
    const resData = res?.data ?? res
    if (resData?.status === 'success' || res?.ok) {
      success('删除成功')
      fetchFiles()
    } else {
      showError(resData?.detail || '删除失败')
    }
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
  closeContextMenu()
}

function copyPath(path: string) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(path).then(() => {
      success('路径已复制到剪贴板')
    }).catch(() => {
      fallbackCopyText(path)
    })
  } else {
    fallbackCopyText(path)
  }
  closeContextMenu()
}

function fallbackCopyText(text: string) {
  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.style.position = 'fixed'
  textArea.style.left = '-9999px'
  textArea.style.top = '0'
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()
  try {
    document.execCommand('copy')
    success('路径已复制到剪贴板')
  } catch {
    showError('复制失败，请手动复制')
  }
  document.body.removeChild(textArea)
}

async function getFileInfo(path: string) {
  try {
    const res = await organizerApi.getFileInfo({ path })
    const resData = res?.data ?? res
    fileInfo.value = resData?.data ?? resData
    showInfoModal.value = true
  } catch (e) {
    showError('获取文件信息失败')
  }
  closeContextMenu()
}

// --- 单文件识别 ---
async function recognizeFile(item: any, forcedParams: any = null) {
  selectedFile.value = item
  recognitionData.value = null
  previewPath.value = ''
  
  // 没有强制参数时，只打开弹窗，不自动识别
  if (!forcedParams) {
    showRecognitionModal.value = true
    return
  }
  
  // 有强制参数时，执行识别
  recognizingPath.value = item.path
  isRecogLoading.value = true
  showRecognitionModal.value = true
  try {
    const payload = {
      filename: item.path,
      forced_tmdb_id: forcedParams?.tmdb_id || undefined,
      forced_type: forcedParams?.type || undefined,
      forced_season: forcedParams?.season || undefined,
      forced_episode: forcedParams?.episode || undefined,
      anime_priority: forcedParams?.anime_priority,
      offline_priority: forcedParams?.offline_priority,
      bangumi_priority: forcedParams?.bangumi_priority,
      bangumi_failover: forcedParams?.bangumi_failover,
      series_fingerprint: forcedParams?.series_fingerprint,
      batch_enhancement: forcedParams?.batch_enhancement,
      force_filename: forcedParams?.force_filename,
    }
    const data = await recognitionApi.recognize(payload)
    recognitionData.value = data

    // 预览重命名
    if (availableRules.value.length > 0) {
      try {
        const previewData = await organizerApi.renamePreview({
          rule_id: availableRules.value[0].id,
          result_data: data,
        })
        if (previewData?.status === 'success') {
          previewPath.value = previewData.new_path
        } else {
          previewPath.value = '预览失败: ' + (previewData?.message || '规则不匹配')
        }
      } catch {
        previewPath.value = '预览失败'
      }
    } else {
      previewPath.value = '未配置规则'
    }
  } catch (e: any) {
    showError(e?.message || '识别出错')
  } finally {
    recognizingPath.value = ''
    isRecogLoading.value = false
  }
}

// --- 重新预览（切换重命名规则时） ---
async function handleRepreview(ruleId: string) {
  if (!recognitionData.value) return
  try {
    const previewData = await organizerApi.renamePreview({
      rule_id: ruleId,
      result_data: recognitionData.value,
    })
    if (previewData?.status === 'success') {
      previewPath.value = previewData.new_path
    } else {
      previewPath.value = '预览失败: ' + (previewData?.message || '规则不匹配')
    }
  } catch {
    previewPath.value = '预览失败'
  }
}

// --- 重命名 ---
async function handleRename() {
  if (!selectedFile.value || !previewPath.value || previewPath.value.startsWith('预览失败')) {
    warning('无效的预览路径')
    return
  }

  isRenaming.value = true
  try {
    const currentDir = selectedFile.value.path.substring(0, selectedFile.value.path.lastIndexOf('/'))
    const targetAbs = (currentDir || '.').replace(/\/+$/, '') + '/' + previewPath.value

    const response = await organizerApi.streamExecute({
      items: [{ source: selectedFile.value.path, target: targetAbs, action: 'move' }],
      conflict_mode: 'skip',
    })

    if (response.ok) {
      await readStream(response)
      success('重命名完成')
      setTimeout(() => fetchFiles(), 1000)
    } else {
      showError('执行失败')
    }
  } catch (e) {
    showError('重命名过程出错')
  } finally {
    isRenaming.value = false
    showRecognitionModal.value = false
  }
}

// --- 流式执行 ---
async function readStream(response: Response) {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const msg = JSON.parse(line)
        if (msg.type === 'scan') {
          scanningStatus.value = msg.path
        } else if (['item', 'skip', 'error', 'start'].includes(msg.type)) {
          execLogs.value.push(msg)
        } else if (msg.type === 'finish') {
          scanningStatus.value = ''
          success(`任务完成: 处理了 ${msg.count} 个文件`)
        }
      } catch {}
    }
  }
}

// --- 整理当前目录 ---
async function runManualOrganize(task: any) {
  currentManualTask.value = task
  showManualModal.value = false
  showExecModal.value = true
  isDryRun.value = true
  isRunning.value = true
  execLogs.value = []

  try {
    const response = await organizerApi.streamAdhoc(
      { ...task, source_dir: currentPath.value },
      { dry_run: true }
    )
    await readStream(response)
  } catch {
    showError('任务中断')
  } finally {
    isRunning.value = false
  }
}

async function runManualOrganizeBackground(task: any) {
  try {
    const data = await organizerApi.startBackground(
      { ...task, source_dir: currentPath.value },
      { dry_run: false }
    )
    if (data?.status === 'success') {
      success('后台整理任务已启动')
      showManualModal.value = false
    } else {
      showError(data?.message || '启动失败')
    }
  } catch {
    showError('网络错误')
  }
}

async function commitBatch() {
  const commitItems = execLogs.value.filter(l => l.type === 'item' && l.status === 'success')
  if (commitItems.length === 0) {
    warning('没有可执行的项目')
    return
  }

  isDryRun.value = false
  isRunning.value = true
  execLogs.value = []

  try {
    const response = await organizerApi.streamExecute({
      items: commitItems,
      conflict_mode: currentManualTask.value?.overwrite_mode ? 'overwrite' : 'skip',
    })
    if (response.ok) {
      await readStream(response)
      success('整理任务执行完毕')
      setTimeout(() => fetchFiles(), 500)
    } else {
      showError('执行请求失败')
    }
  } catch {
    showError('执行过程出错')
  } finally {
    isRunning.value = false
  }
}

// --- 前往指定路径 ---
function goToPath() {
  const path = goToPathInput.value.trim()
  if (!path) {
    warning('请输入有效路径')
    return
  }
  let targetPath = path
  if (!targetPath.startsWith('/')) {
    targetPath = '/' + targetPath
  }
  fetchFiles(targetPath)
  showGoToModal.value = false
  goToPathInput.value = ''
}

onMounted(() => {
  loadConfig()
  const lastPath = localStorage.getItem('apm_file_browser_last_path')
  fetchFiles(lastPath || '/')
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-4 d-flex align-center justify-space-between flex-wrap ga-3">
      <div>
        <h1 class="page-title text-h5 font-weight-bold">文件浏览</h1>
        <div class="page-subtitle text-body-2 text-medium-emphasis mt-1">文件资源管理器</div>
      </div>
      <v-btn color="primary" variant="flat" prepend-icon="mdi-folder-sync-outline" @click="showManualModal = true">
        整理当前目录
      </v-btn>
    </div>

    <!-- 主内容区（全宽） -->
    <!-- 工具栏 -->
    <v-card class="glass-card mb-3">
      <div class="pa-3 d-flex align-center justify-space-between flex-wrap ga-2">
        <!-- 面包屑 -->
        <div class="d-flex align-center ga-2">
          <v-btn icon="mdi-arrow-up" size="small" variant="tonal" :disabled="!parentPath" @click="goUp" />
          <v-breadcrumbs :items="[{ title: '根目录', href: '/' }, ...breadcrumbParts.map(p => ({ title: p.name, href: p.path }))]" density="compact">
            <template #divider>/</template>
            <template #item="{ item: bItem }">
              <v-breadcrumbs-item class="cursor-pointer text-body-2" @click="jumpTo(bItem.href || '')">
                {{ bItem.title }}
              </v-breadcrumbs-item>
            </template>
          </v-breadcrumbs>
        </div>

        <!-- 操作按钮 -->
        <div class="d-flex ga-1 flex-wrap">
          <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-bookmark-box-multiple-outline" @click="showFavDrawer = true">
            收藏夹
            <v-badge v-if="favorites.length > 0" :content="favorites.length" color="primary" offset-x="-6" offset-y="0" inline />
          </v-btn>
          <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-content-copy" @click="copyPath(currentPath)">复制路径</v-btn>
          <v-btn
            size="small"
            variant="tonal"
            :prepend-icon="isCurrentFavorite() ? 'mdi-star' : 'mdi-star-outline'"
            :color="isCurrentFavorite() ? 'warning' : 'primary'"
            @click="toggleFavorite"
          >
            {{ isCurrentFavorite() ? '已收藏' : '收藏' }}
          </v-btn>
          <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-folder-marker" @click="showGoToModal = true">前往路径</v-btn>
        </div>
      </div>
    </v-card>

    <!-- 文件列表 -->
    <v-card class="glass-card file-list-card">
      <!-- 加载进度条 -->
      <div v-if="loading" class="loading-bar">
        <div class="loading-bar-inner"></div>
      </div>

      <!-- 骨架屏 -->
      <template v-if="showSkeleton">
        <div class="pa-4">
          <v-skeleton-loader v-for="i in 8" :key="i" type="list-item" class="mb-2" />
        </div>
      </template>

      <!-- 文件列表 -->
      <template v-else>
        <v-list density="comfortable" class="pa-0" @contextmenu.prevent="handleContextMenu($event, null)">
          <v-list-item
            v-for="item in items"
            :key="item.path"
            class="file-list-item"
            @click="item.is_dir && navigateTo(item.path)"
            @contextmenu.prevent.stop="handleContextMenu($event, item)"
          >
            <template #prepend>
              <v-icon
                :icon="getFileIcon(item)"
                :color="item.is_dir ? 'primary' : undefined"
                size="20"
              />
            </template>

            <v-list-item-title class="text-body-2 font-weight-medium">{{ item.name }}</v-list-item-title>
            <v-list-item-subtitle class="text-caption text-medium-emphasis">
              {{ formatSize(item.size) }} · {{ formatDate(item.mtime) }}
            </v-list-item-subtitle>

            <template #append>
              <v-btn
                v-if="!item.is_dir"
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-head-cog-outline"
                :loading="recognizingPath === item.path"
                @click.stop="recognizeFile(item)"
              >
                识别
              </v-btn>
              <v-icon v-else color="medium-emphasis">mdi-chevron-right</v-icon>
            </template>
          </v-list-item>

          <v-list-item v-if="items.length === 0" disabled>
            <v-list-item-title class="text-center text-body-2 text-medium-emphasis py-8">
              当前目录为空
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </template>

      <!-- 底部信息 -->
      <v-divider />
      <div class="pa-3 text-caption text-medium-emphasis d-flex align-center ga-2">
        <v-icon size="14">mdi-file-outline</v-icon>
        共 {{ items.length }} 项内容
      </div>
    </v-card>

    <!-- 收藏夹弹窗 -->
    <v-dialog v-model="showFavDrawer" max-width="360" transition="dialog-slide-transition">
      <v-card class="glass-card" rounded="xl">
        <div class="pa-3 d-flex align-center justify-space-between">
          <div class="d-flex align-center ga-2">
            <v-icon size="18" color="primary">mdi-star-outline</v-icon>
            <span class="section-title text-subtitle-2 font-weight-bold">收藏夹</span>
          </div>
          <v-btn icon="mdi-close" size="small" variant="text" @click="showFavDrawer = false" />
        </div>
        <v-divider />
        <v-list density="compact" class="pa-2" max-height="60vh">
          <v-list-item
            v-for="fav in favorites"
            :key="fav.path"
            density="compact"
            rounded="lg"
            :active="fav.path === currentPath"
            @click="jumpTo(fav.path); showFavDrawer = false"
          >
            <template #prepend>
              <v-icon size="18" color="primary">mdi-folder-outline</v-icon>
            </template>
            <v-list-item-title class="text-body-2 text-truncate">{{ fav.name }}</v-list-item-title>
            <v-list-item-subtitle class="text-caption text-medium-emphasis text-truncate">{{ fav.path }}</v-list-item-subtitle>
            <template #append>
              <v-btn
                icon="mdi-close"
                size="x-small"
                variant="text"
                density="compact"
                @click.stop="removeFavorite(fav.path)"
              />
            </template>
          </v-list-item>
          <v-list-item v-if="favorites.length === 0" disabled>
            <v-list-item-title class="text-caption text-medium-emphasis">暂无收藏</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-card>
    </v-dialog>

    <!-- 右键菜单 -->
    <v-menu
      v-model="contextMenu.show"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      absolute
      :close-on-content-click="true"
    >
      <v-list density="compact" min-width="160">
        <v-list-item v-if="contextMenu.item" @click="handleContextAction('copy')">
          <template #prepend><v-icon size="18">mdi-content-copy</v-icon></template>
          <v-list-item-title class="text-body-2">复制</v-list-item-title>
        </v-list-item>
        <v-list-item v-if="contextMenu.item" @click="handleContextAction('move')">
          <template #prepend><v-icon size="18">mdi-content-cut</v-icon></template>
          <v-list-item-title class="text-body-2">剪切</v-list-item-title>
        </v-list-item>
        <v-list-item @click="handleContextAction('copyPath')">
          <template #prepend><v-icon size="18">mdi-link-variant</v-icon></template>
          <v-list-item-title class="text-body-2">复制路径</v-list-item-title>
        </v-list-item>
        <v-list-item v-if="contextMenu.item" @click="handleContextAction('delete')">
          <template #prepend><v-icon size="18" color="error">mdi-delete-outline</v-icon></template>
          <v-list-item-title class="text-body-2 text-error">删除</v-list-item-title>
        </v-list-item>
        <v-list-item v-if="contextMenu.item" @click="handleContextAction('info')">
          <template #prepend><v-icon size="18">mdi-information-outline</v-icon></template>
          <v-list-item-title class="text-body-2">详情</v-list-item-title>
        </v-list-item>
        <v-divider v-if="clipboard" />
        <v-list-item v-if="clipboard" @click="handleContextAction('paste')">
          <template #prepend><v-icon size="18">mdi-content-paste</v-icon></template>
          <v-list-item-title class="text-body-2">粘贴: {{ clipboard.item.name }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>

    <!-- 文件详情 Modal -->
    <v-dialog v-model="showInfoModal" max-width="500">
      <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start>mdi-information-outline</v-icon>
项目详情
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showInfoModal = false" />
</v-card-title>
        <v-divider />
        <v-card-text class="pa-4" v-if="fileInfo">
          <div class="kv-row">
            <span class="kv-label">名称</span>
            <span class="kv-value">{{ fileInfo.name }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-label">路径</span>
            <span class="kv-value kv-value--mono text-caption">{{ fileInfo.path }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-label">类型</span>
            <span class="kv-value">{{ fileInfo.is_dir ? '文件夹' : '文件' }}</span>
          </div>
          <div v-if="!fileInfo.is_dir" class="kv-row">
            <span class="kv-label">大小</span>
            <span class="kv-value">{{ formatSize(fileInfo.size) }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-label">修改时间</span>
            <span class="kv-value">{{ formatDate(fileInfo.mtime) }}</span>
          </div>
          <div v-if="fileInfo.ctime" class="kv-row">
            <span class="kv-label">创建时间</span>
            <span class="kv-value">{{ formatDate(fileInfo.ctime) }}</span>
          </div>
          <div v-if="fileInfo.mode" class="kv-row">
            <span class="kv-label">权限</span>
            <span class="kv-value kv-value--mono">{{ fileInfo.mode }}</span>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showInfoModal = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 前往路径 Modal -->
    <v-dialog v-model="showGoToModal" max-width="500">
      <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start>mdi-folder-marker</v-icon>
前往指定路径
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showGoToModal = false" />
</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field
            v-model="goToPathInput"
            placeholder="请输入路径，如 /mnt/media/anime"
            prepend-inner-icon="mdi-folder-outline"
            density="comfortable"
            hide-details
            @keydown.enter="goToPath"
          />
          <div class="text-caption text-medium-emphasis mt-2">提示：路径以 / 开头，支持直接粘贴完整路径</div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showGoToModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-arrow-right" @click="goToPath">前往</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 单文件识别弹窗 -->
    <RecognitionModal
      v-model="showRecognitionModal"
      :file="selectedFile"
      :data="recognitionData"
      :preview-path="previewPath"
      :loading="isRecogLoading"
      :is-renaming="isRenaming"
      :available-rules="availableRules"
      @recognize="(params: any) => recognizeFile(selectedFile, params)"
      @rename="handleRename"
      @repreview="handleRepreview"
    />

    <!-- 整理当前目录弹窗 -->
    <ManualOrganizeModal
      v-model="showManualModal"
      :current-path="currentPath"
      :available-rules="availableRules"
      :default-task="defaultTask"
      @run="runManualOrganize"
      @run-background="runManualOrganizeBackground"
    />

    <!-- 执行日志弹窗 -->
    <ExecutionLogModal
      v-model="showExecModal"
      :is-dry-run="isDryRun"
      :is-running="isRunning"
      :logs="execLogs"
      :scanning-status="scanningStatus"
      :target-dir="currentManualTask?.target_dir || ''"
      @commit="commitBatch"
    />
  </v-container>
</template>

<style scoped>
.file-list-card {
  position: relative;
  overflow: hidden;
}
.file-list-item :deep(.v-list-item__spacer) {
  display: none !important;
}
.file-list-item :deep(.v-list-item__prepend) {
  margin-inline-end: 8px !important;
}
</style>
