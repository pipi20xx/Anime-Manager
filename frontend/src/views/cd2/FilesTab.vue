<script setup lang="ts">
/**
 * FilesTab — CD2 文件浏览与操作
 * 浏览 CD2 云端目录（GetSubFiles），右键/⋮ 菜单操作：打开、重命名、移动、复制、删除。
 * 工具栏支持新建文件夹、上传小文件（CreateFile + WriteToFile 分块）。
 * 进入支持离线下载的目录（如 /115open）后，可通过「离线下载管理」按钮
 * 查看当前目录的离线任务、提交新任务、删除与重启。
 * 全部直接使用 CD2 内部路径（如 /115open/xxx）。
 */
import { computed, onMounted, ref } from 'vue'
import { cd2Api, recognitionApi, organizerApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import RecognitionModal from '../organizer/RecognitionModal.vue'

defineOptions({ name: 'FilesTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const currentPath = ref('/')
const entries = ref<any[]>([])
// 当前目录是否支持离线下载（由后端根据子项 canOfflineDownload 判定）
const canOffline = ref(false)

const breadcrumbs = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  const crumbs = [{ name: '根目录', path: '/' }]
  let acc = ''
  for (const p of parts) {
    acc += `/${p}`
    crumbs.push({ name: p, path: acc })
  }
  return crumbs
})

const formatSize = (bytes: number, isDir: boolean) => {
  if (isDir) return '-'
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

const formatSpeed = (bytesPerSec: number) => {
  if (!bytesPerSec || bytesPerSec < 1) return '0 B/s'
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  let i = 0
  let v = bytesPerSec
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(1)} ${units[i]}`
}

const formatTime = (ts: number) => {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

const navigate = (path: string) => {
  currentPath.value = path
  loadEntries()
}

const loadEntries = async (forceRefresh = false) => {
  loading.value = true
  try {
    const res = await cd2Api.browseFiles(currentPath.value, forceRefresh)
    entries.value = res.entries || []
    canOffline.value = !!res.can_offline
  } catch (e: any) {
    showError(e?.message || '列目录失败')
  } finally {
    loading.value = false
  }
}

// ---------- 右键菜单 ----------
const menuState = ref(false)
const menuX = ref(0)
const menuY = ref(0)
const menuTarget = ref<any>(null)

const openMenu = (e: MouseEvent, entry: any) => {
  menuTarget.value = entry
  menuX.value = e.clientX
  menuY.value = e.clientY
  menuState.value = true
}

const menuAction = (action: string) => {
  menuState.value = false
  const entry = menuTarget.value
  if (!entry) return
  if (action === 'open') navigate(entry.path)
  else if (action === 'rename') openRenameModal(entry)
  else if (action === 'recognize') recognizeFile(entry)
  else if (action === 'move') openTransferModal('move', entry)
  else if (action === 'copy') openTransferModal('copy', entry)
  else if (action === 'delete') deleteEntry(entry)
}

// ---------- 新建文件夹 ----------
const showCreateModal = ref(false)
const newFolderName = ref('')

const openCreateModal = () => {
  newFolderName.value = ''
  showCreateModal.value = true
}

const submitCreate = async () => {
  if (!newFolderName.value.trim()) return
  try {
    await cd2Api.createFolder({ parent_path: currentPath.value, name: newFolderName.value.trim() })
    success('创建成功')
    showCreateModal.value = false
    await loadEntries()
  } catch (e: any) {
    showError(e?.message || '创建失败')
  }
}

// ---------- 重命名 ----------
const showRenameModal = ref(false)
const renameOldName = ref('')
const renamePath = ref('')
const renameNewName = ref('')

const openRenameModal = (entry: any) => {
  renamePath.value = entry.path
  renameOldName.value = entry.name
  renameNewName.value = entry.name
  showRenameModal.value = true
}

const submitRename = async () => {
  if (!renameNewName.value.trim() || renameNewName.value === renameOldName.value) return
  try {
    await cd2Api.renamePath({ path: renamePath.value, new_name: renameNewName.value.trim() })
    success('重命名成功')
    showRenameModal.value = false
    await loadEntries(true)
  } catch (e: any) {
    showError(e?.message || '重命名失败')
  }
}

// ---------- 移动/复制（单个文件） ----------
const showTransferModal = ref(false)
const transferAction = ref<'move' | 'copy'>('move')
const transferTarget = ref<any>(null)
const transferDest = ref('/')
const transferConflict = ref(1)

const openTransferModal = (action: 'move' | 'copy', entry: any) => {
  transferAction.value = action
  transferTarget.value = entry
  transferDest.value = currentPath.value === '/' ? '/' : currentPath.value
  transferConflict.value = 1
  showTransferModal.value = true
}

const submitTransfer = async () => {
  if (!transferTarget.value) return
  try {
    const res = await cd2Api.transferPaths({
      paths: [transferTarget.value.path],
      dest_dir: transferDest.value,
      action: transferAction.value,
      conflict_policy: transferConflict.value,
    })
    success(res?.message || '操作成功')
    showTransferModal.value = false
    await loadEntries(true)
  } catch (e: any) {
    showError(e?.message || '操作失败')
  }
}

// ---------- 删除（单个文件） ----------
const deleteEntry = async (entry: any) => {
  const ok = await confirm(`确定删除「${entry.name}」吗？（删除到回收站）`)
  if (!ok) return
  try {
    await cd2Api.deletePaths({ paths: [entry.path] })
    success('删除成功')
    await loadEntries(true)
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

// ---------- 上传（Remote Upload 协议，支持大文件） ----------
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadFileName = ref('')
const uploadCancelled = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const triggerUpload = () => fileInput.value?.click()

const onFilePicked = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploading.value = true
  uploadCancelled.value = false
  uploadProgress.value = 0
  uploadFileName.value = file.name
  try {
    // 优先走 Remote Upload 协议（无大小限制）；启动失败回退旧 multipart 上传
    let uploadId = ''
    try {
      const start = await cd2Api.remoteUploadStart({ path: currentPath.value, file_name: file.name, size: file.size })
      uploadId = start.upload_id
    } catch (startErr) {
      console.warn('远程上传启动失败，回退普通上传:', startErr)
    }

    if (uploadId) {
      await runRemoteUpload(file, uploadId)
    } else {
      const res = await cd2Api.uploadFile(currentPath.value, file)
      success(res?.message || '上传成功')
      uploadProgress.value = 100
    }
    await loadEntries(true)
  } catch (e: any) {
    if (!uploadCancelled.value) showError(e?.message || '上传失败')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

const runRemoteUpload = async (file: File, uploadId: string) => {
  let served = 0
  while (true) {
    if (uploadCancelled.value) {
      await cd2Api.remoteUploadCancel(uploadId).catch(() => {})
      return
    }
    const job = await cd2Api.remoteUploadNext(uploadId)
    if (job.type === 'read' || job.type === 'hash_read') {
      // 按需切片回传，全程不在内存中持有整个文件
      const blob = file.slice(job.offset, job.offset + job.length)
      const buf = await blob.arrayBuffer()
      await cd2Api.remoteUploadData(uploadId, job.request_id, buf)
      if (job.type === 'read') {
        served = Math.max(served, job.offset + job.length)
        uploadProgress.value = file.size ? Math.min(100, Math.round((served / file.size) * 100)) : 100
      }
    } else if (job.type === 'done') {
      if (job.status === 5) success(`上传完成: ${file.name}`)
      else if (job.status === 6) success(`秒传完成 (服务器已存在): ${file.name}`)
      else throw new Error(job.error || `上传未完成 (${job.status_text})`)
      uploadProgress.value = 100
      return
    }
    // 'none' = 轮询超时无任务，继续
  }
}

const cancelUpload = () => {
  uploadCancelled.value = true
}

// ---------- 单文件识别 → 重命名（复用识别管线，重命名走 CD2 gRPC） ----------
const showRecognitionModal = ref(false)
const selectedFile = ref<any>(null)
const recognitionData = ref<any>(null)
const previewPath = ref('')
const recognizingPath = ref('')
const isRecogLoading = ref(false)
const isRenaming = ref(false)
const availableRules = ref<any[]>([])
let rulesLoaded = false

const loadRules = async () => {
  if (rulesLoaded) return
  try {
    const config = await configApi.getConfig()
    availableRules.value = config?.rename_rules || []
    rulesLoaded = true
  } catch {
    // 规则加载失败不阻断识别，仅预览时提示
  }
}

const recognizeFile = async (entry: any, forcedParams: any = null) => {
  selectedFile.value = entry
  recognitionData.value = null
  previewPath.value = ''
  loadRules()

  // 无强制参数时只打开弹窗，由用户在弹窗内确认后识别
  if (!forcedParams) {
    showRecognitionModal.value = true
    return
  }

  recognizingPath.value = entry.path
  isRecogLoading.value = true
  showRecognitionModal.value = true
  try {
    const payload = {
      filename: entry.path,
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
    await handleRepreview(availableRules.value[0]?.id)
  } catch (e: any) {
    showError(e?.message || '识别出错')
  } finally {
    recognizingPath.value = ''
    isRecogLoading.value = false
  }
}

const handleRepreview = async (ruleId: string) => {
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

const handleRename = async () => {
  if (!selectedFile.value || !previewPath.value || previewPath.value.startsWith('预览失败')) {
    showError('无效的预览路径')
    return
  }
  // 完整预览路径交给后端：含子目录时自动逐级建目录并移动，纯文件名变化时原位重命名
  isRenaming.value = true
  try {
    const res = await cd2Api.organizeRename({
      path: selectedFile.value.path,
      new_relative_path: previewPath.value,
    })
    success(`已整理至: ${res?.final_path || previewPath.value}`)
    showRecognitionModal.value = false
    await loadEntries(true)
  } catch (e: any) {
    showError(e?.message || '重命名失败')
  } finally {
    isRenaming.value = false
  }
}

// ---------- 离线下载管理（弹框） ----------
const showOfflineModal = ref(false)
const offlineLoading = ref(false)
const offlineTasks = ref<any[]>([])
const offlineQuota = ref<{ total?: number; used?: number; left?: number }>({})
const restartingHash = ref('')
const newTaskUrls = ref('')
const addingTask = ref(false)
const showAddTask = ref(false)
// 删除确认弹框（含"同时删除云端文件"选项）
const deletingTask = ref<any>(null)
const showDeleteModal = ref(false)
const deleteFiles = ref(false)
const deleting = ref(false)
// 清空（ClearOfflineFiles: All=0; Finished=1; Error=2; Downloading=3）
const CLEAR_FILTERS = [
  { title: '全部', value: 0 },
  { title: '已完成', value: 1 },
  { title: '错误', value: 2 },
  { title: '下载中', value: 3 },
]
const showClearModal = ref(false)
const clearFilter = ref<number>(2)
const deleteFilesOnClear = ref(false)
const clearing = ref(false)

const clearFilterCount = computed(() => {
  const codes: Record<number, number[]> = { 0: [0, 1, 2, 3, 4], 1: [2], 2: [3], 3: [1] }
  const match = codes[clearFilter.value] || []
  return offlineTasks.value.filter((t) => match.includes(t.status_code)).length
})

const clearFilterTitle = computed(() => CLEAR_FILTERS.find((f) => f.value === clearFilter.value)?.title || '')

const offlineStatusColor = (code: number) => {
  switch (code) {
    case 2: return 'success'
    case 3: return 'error'
    case 1: return 'primary'
    default: return 'grey'
  }
}

const openOfflineModal = () => {
  showOfflineModal.value = true
  loadOfflineTasks()
}

const loadOfflineTasks = async () => {
  offlineLoading.value = true
  try {
    const res = await cd2Api.getOfflineTasks(currentPath.value)
    offlineTasks.value = res.tasks || []
    offlineQuota.value = res.quota || {}
  } catch (e: any) {
    showError(e?.message || '获取离线任务失败')
  } finally {
    offlineLoading.value = false
  }
}

const submitOfflineTask = async () => {
  if (!newTaskUrls.value.trim()) return
  addingTask.value = true
  try {
    await cd2Api.addOfflineUrls({ urls: newTaskUrls.value.trim(), to_folder: currentPath.value })
    success('离线任务已提交')
    newTaskUrls.value = ''
    showAddTask.value = false
    await loadOfflineTasks()
  } catch (e: any) {
    showError(e?.message || '提交失败')
  } finally {
    addingTask.value = false
  }
}

const openClearModal = () => {
  clearFilter.value = 2
  deleteFilesOnClear.value = false
  showClearModal.value = true
}

const submitClear = async () => {
  clearing.value = true
  try {
    await cd2Api.clearOfflineTasks({
      filter: clearFilter.value,
      path: currentPath.value,
      delete_files: deleteFilesOnClear.value,
    })
    success('清空完成')
    showClearModal.value = false
    await loadOfflineTasks()
  } catch (e: any) {
    showError(e?.message || '清空失败')
  } finally {
    clearing.value = false
  }
}

const restartOfflineTask = async (task: any) => {
  const ok = await confirm(`确定重启任务「${task.name || task.info_hash}」吗？`)
  if (!ok) return
  restartingHash.value = task.info_hash
  try {
    await cd2Api.restartOfflineTask({ info_hash: task.info_hash, url: task.url, parent_id: task.parent_id || '', path: currentPath.value })
    success('任务已重启')
    await loadOfflineTasks()
  } catch (e: any) {
    showError(e?.message || '重启失败')
  } finally {
    restartingHash.value = ''
  }
}

const openDeleteModal = (task: any) => {
  deletingTask.value = task
  deleteFiles.value = false
  showDeleteModal.value = true
}

const confirmDeleteTask = async () => {
  const task = deletingTask.value
  if (!task) return
  deleting.value = true
  try {
    await cd2Api.deleteOfflineTasks({
      info_hashes: [task.info_hash],
      path: currentPath.value,
      delete_files: deleteFiles.value,
    })
    success(`已删除任务「${task.name || task.info_hash}」`)
    showDeleteModal.value = false
    deletingTask.value = null
    await loadOfflineTasks()
  } catch (e: any) {
    showError(e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(() => loadEntries())
</script>

<template>
  <!-- 面包屑 + 工具栏 -->
  <v-card class="glass-card mb-4">
    <v-card-text class="pb-2">
      <div class="d-flex align-center flex-wrap gap-1">
        <v-icon size="small" class="mr-1">mdi-folder-outline</v-icon>
        <template v-for="(crumb, i) in breadcrumbs" :key="crumb.path">
          <v-btn
            variant="text"
            size="small"
            density="compact"
            class="text-none px-1"
            :color="i === breadcrumbs.length - 1 ? 'primary' : undefined"
            @click="navigate(crumb.path)"
          >
            {{ crumb.name }}
          </v-btn>
          <v-icon v-if="i < breadcrumbs.length - 1" size="x-small">mdi-chevron-right</v-icon>
        </template>
        <v-spacer />
        <span class="text-caption text-medium-emphasis mr-2">{{ entries.length }} 项</span>
        <v-btn
          v-if="canOffline && currentPath !== '/'"
          color="primary"
          variant="tonal"
          size="small"
          prepend-icon="mdi-magnet"
          class="mr-1"
          @click="openOfflineModal"
        >
          离线下载管理
        </v-btn>
        <v-btn
          icon="mdi-upload"
          size="small"
          variant="text"
          title="上传文件"
          :loading="uploading"
          @click="triggerUpload"
        />
        <v-btn icon="mdi-folder-plus-outline" size="small" variant="text" title="新建文件夹" @click="openCreateModal" />
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" title="刷新" @click="loadEntries()" />
        <v-btn icon="mdi-sync" size="small" variant="text" :loading="loading" title="强制刷新 (绕过缓存)" @click="loadEntries(true)" />
        <input ref="fileInput" type="file" hidden @change="onFilePicked" />
      </div>
    </v-card-text>
  </v-card>

  <!-- 上传进度 -->
  <v-card v-if="uploading" class="glass-card mb-4">
    <v-card-text class="d-flex align-center py-3">
      <v-icon class="mr-3">mdi-upload</v-icon>
      <div class="flex-grow-1" style="min-width: 0">
        <div class="text-body-2 text-truncate">{{ uploadFileName }}</div>
        <v-progress-linear :model-value="uploadProgress" height="6" rounded color="primary" class="mt-1" />
      </div>
      <span class="text-caption mx-3">{{ uploadProgress }}%</span>
      <v-btn icon="mdi-close" size="small" variant="text" title="取消上传" @click="cancelUpload" />
    </v-card-text>
  </v-card>

  <!-- 文件列表 -->
  <v-card class="glass-card mb-4">
    <v-card-text class="pa-0">
      <div v-if="loading && !entries.length" class="d-flex justify-center pa-8">
        <v-progress-circular indeterminate color="primary" />
      </div>

      <div v-else-if="!entries.length" class="text-center text-medium-emphasis pa-8">
        此目录为空
      </div>

      <v-list v-else class="py-0">
        <v-list-item
          v-for="entry in entries"
          :key="entry.path"
          class="file-list-item"
          @click="entry.is_dir && navigate(entry.path)"
          @contextmenu.prevent="openMenu($event, entry)"
        >
          <template #prepend>
            <v-icon :color="entry.is_dir ? 'amber-darken-2' : 'grey-lighten-1'">
              {{ entry.is_dir ? 'mdi-folder' : 'mdi-file-outline' }}
            </v-icon>
          </template>

          <v-list-item-title class="text-body-2 d-flex align-center">
            <span class="text-truncate" style="max-width: 60%">{{ entry.name }}</span>
            <v-chip v-if="entry.is_forbidden" size="x-small" variant="tonal" color="warning" class="ml-2">
              受限
            </v-chip>
          </v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ formatSize(entry.size, entry.is_dir) }} · {{ formatTime(entry.write_time) }}
          </v-list-item-subtitle>

          <template #append>
            <v-btn
              icon="mdi-dots-vertical"
              size="small"
              variant="text"
              title="操作菜单"
              @click.stop="openMenu($event, entry)"
            />
          </template>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>

  <!-- 右键/操作菜单 -->
  <v-menu v-model="menuState" :target="[menuX, menuY]" absolute close-on-content-click>
    <v-list density="compact" min-width="160">
      <template v-if="menuTarget">
        <v-list-item
          v-if="menuTarget.is_dir"
          prepend-icon="mdi-folder-open-outline"
          title="打开"
          @click="menuAction('open')"
        />
        <v-list-item
          v-if="!menuTarget.is_dir"
          prepend-icon="mdi-head-cog-outline"
          title="识别"
          @click="menuAction('recognize')"
        />
        <v-list-item prepend-icon="mdi-pencil-outline" title="重命名" @click="menuAction('rename')" />
        <v-list-item prepend-icon="mdi-folder-move-outline" title="移动到..." @click="menuAction('move')" />
        <v-list-item prepend-icon="mdi-content-copy" title="复制到..." @click="menuAction('copy')" />
        <v-divider class="my-1" />
        <v-list-item
          prepend-icon="mdi-delete-outline"
          title="删除"
          base-color="error"
          @click="menuAction('delete')"
        />
      </template>
    </v-list>
  </v-menu>

  <!-- 新建文件夹 -->
  <v-dialog v-model="showCreateModal" max-width="440">
    <v-card>
      <v-card-title class="d-flex align-center">
        新建文件夹
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showCreateModal = false" />
      </v-card-title>
      <v-card-text>
        <v-text-field
          v-model="newFolderName"
          label="文件夹名称"
          variant="outlined"
          density="compact"
          hide-details
          class="mb-2"
          autofocus
          @keyup.enter="submitCreate"
        />
        <div class="text-caption text-medium-emphasis">位置: {{ currentPath }}</div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showCreateModal = false">取消</v-btn>
        <v-btn color="primary" @click="submitCreate">创建</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 重命名 -->
  <v-dialog v-model="showRenameModal" max-width="440">
    <v-card>
      <v-card-title class="d-flex align-center">
        重命名
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showRenameModal = false" />
      </v-card-title>
      <v-card-text>
        <v-text-field
          v-model="renameNewName"
          label="新名称"
          variant="outlined"
          density="compact"
          hide-details
          class="mb-2"
          autofocus
          @keyup.enter="submitRename"
        />
        <div class="text-caption text-medium-emphasis text-truncate">原路径: {{ renamePath }}</div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showRenameModal = false">取消</v-btn>
        <v-btn color="primary" @click="submitRename">确定</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 移动/复制 -->
  <v-dialog v-model="showTransferModal" max-width="480">
    <v-card>
      <v-card-title class="d-flex align-center">
        {{ transferAction === 'move' ? '移动' : '复制' }}「{{ transferTarget?.name }}」
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showTransferModal = false" />
      </v-card-title>
      <v-card-text>
        <v-text-field
          v-model="transferDest"
          label="目标目录 (CD2 路径)"
          placeholder="/115open/media"
          variant="outlined"
          density="compact"
          hide-details
          class="mb-3"
        />
        <v-select
          v-model="transferConflict"
          label="同名冲突处理"
          variant="outlined"
          density="compact"
          hide-details
          :items="[
            { title: '自动重命名', value: 1 },
            { title: '覆盖', value: 0 },
            { title: '跳过', value: 2 },
          ]"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showTransferModal = false">取消</v-btn>
        <v-btn color="primary" @click="submitTransfer">
          {{ transferAction === 'move' ? '移动' : '复制' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 离线下载管理 -->
  <v-dialog v-model="showOfflineModal" max-width="860" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center flex-wrap gap-2">
        <v-icon class="mr-2">mdi-magnet</v-icon>
        离线下载管理
        <v-chip size="x-small" variant="tonal" class="ml-2">{{ currentPath }}</v-chip>
        <v-chip v-if="offlineQuota.total" size="x-small" variant="tonal" color="primary" class="ml-1">
          配额 {{ offlineQuota.used ?? 0 }} / {{ offlineQuota.total }}
        </v-chip>
        <v-spacer />
        <v-btn
          variant="tonal"
          size="small"
          prepend-icon="mdi-broom"
          :disabled="!offlineTasks.length"
          @click="openClearModal"
        >
          清空
        </v-btn>
        <v-btn
          color="primary"
          variant="tonal"
          size="small"
          :prepend-icon="showAddTask ? 'mdi-chevron-up' : 'mdi-plus'"
          @click="showAddTask = !showAddTask"
        >
          添加任务
        </v-btn>
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="offlineLoading" title="刷新" @click="loadOfflineTasks" />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showOfflineModal = false" />
      </v-card-title>
      <v-divider />

      <!-- 提交新任务 -->
      <div v-if="showAddTask" class="px-4 pt-3">
        <v-textarea
          v-model="newTaskUrls"
          label="离线下载链接（磁力链/ed2k，多个链接换行分隔）"
          variant="outlined"
          density="compact"
          rows="3"
          hide-details
        />
        <div class="d-flex align-center mt-2 mb-1">
          <span class="text-caption text-medium-emphasis">将下载到: {{ currentPath }}</span>
          <v-spacer />
          <v-btn color="primary" size="small" :loading="addingTask" @click="submitOfflineTask">提交</v-btn>
        </div>
        <v-divider class="mt-2" />
      </div>

      <v-card-text class="pa-3" style="min-height: 200px; max-height: 60vh; overflow-y: auto">
        <div v-if="offlineLoading && !offlineTasks.length" class="d-flex justify-center pa-8">
          <v-progress-circular indeterminate color="primary" />
        </div>
        <div v-else-if="!offlineTasks.length" class="text-center text-medium-emphasis pa-8">
          当前目录下暂无离线任务
        </div>

        <!-- 卡片式任务列表 -->
        <v-row v-else dense>
          <v-col v-for="task in offlineTasks" :key="task.info_hash || task.url" cols="12" sm="6" md="4">
            <v-card class="glass-card d-flex flex-column" height="100%">
              <v-card-text class="pa-3 d-flex flex-column flex-grow-1">
                <div class="d-flex align-center mb-2">
                  <v-chip size="x-small" variant="tonal" :color="offlineStatusColor(task.status_code)">
                    {{ task.status }}
                  </v-chip>
                  <v-spacer />
                  <v-btn
                    v-if="task.status_code === 3"
                    icon="mdi-restart"
                    size="x-small"
                    variant="text"
                    color="primary"
                    :loading="restartingHash === task.info_hash"
                    title="重启任务"
                    @click="restartOfflineTask(task)"
                  />
                  <v-btn
                    icon="mdi-delete-outline"
                    size="x-small"
                    variant="text"
                    color="error"
                    title="删除任务"
                    @click="openDeleteModal(task)"
                  />
                </div>

                <div
                  class="text-body-2 font-weight-medium mb-2 offline-task-name"
                  :title="task.name || task.info_hash"
                >
                  {{ task.name || task.info_hash || '未知任务' }}
                </div>

                <v-progress-linear
                  :model-value="task.progress"
                  :color="offlineStatusColor(task.status_code)"
                  height="6"
                  rounded
                  class="mb-2"
                />

                <div class="text-caption text-medium-emphasis mt-auto">
                  {{ formatSize(task.size, false) }} · {{ task.progress }}% · Peers: {{ task.peers }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ formatTime(task.add_time) }}
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>

  <!-- 删除任务确认（含同时删除云端文件选项） -->
  <v-dialog v-model="showDeleteModal" max-width="460">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon color="error" class="mr-2">mdi-delete-outline</v-icon>
        删除离线任务
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showDeleteModal = false" />
      </v-card-title>
      <v-card-text>
        <div class="text-body-2 mb-2 text-truncate">
          {{ deletingTask?.name || deletingTask?.info_hash || '未知任务' }}
        </div>
        <v-switch
          v-model="deleteFiles"
          label="同时删除云端已下载的文件"
          density="compact"
          hide-details
          color="error"
          inset
        />
        <v-alert type="warning" variant="tonal" density="compact" class="mt-2">
          删除操作不可恢复，请确认后再执行。
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showDeleteModal = false">取消</v-btn>
        <v-btn color="error" :loading="deleting" @click="confirmDeleteTask">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 清空任务确认（四选一 + 同时删除云端文件） -->
  <v-dialog v-model="showClearModal" max-width="460">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon color="warning" class="mr-2">mdi-broom</v-icon>
        清空离线任务
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="showClearModal = false" />
      </v-card-title>
      <v-card-text>
        <v-select
          v-model="clearFilter"
          label="清空类型"
          variant="outlined"
          density="compact"
          hide-details
          :items="CLEAR_FILTERS"
          class="mb-3"
        />
        <v-switch
          v-model="deleteFilesOnClear"
          label="同时删除云端已下载的文件"
          density="compact"
          hide-details
          color="error"
          inset
        />
        <v-alert type="warning" variant="tonal" density="compact" class="mt-2">
          确定清空 {{ clearFilterCount }} 个「{{ clearFilterTitle }}」下载任务？此操作不可恢复！
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showClearModal = false">取消</v-btn>
        <v-btn color="error" :loading="clearing" @click="submitClear">清空</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 单文件识别弹窗（复用原文件浏览组件，重命名走 CD2 gRPC） -->
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
</template>

<style scoped>
.offline-task-name {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
  line-height: 1.4;
}

/* 与原文件浏览一致：去掉 prepend 后的占位 spacer，固定图标与文字间距 */
.file-list-item :deep(.v-list-item__spacer) {
  display: none !important;
}
.file-list-item :deep(.v-list-item__prepend) {
  margin-inline-end: 8px !important;
}
</style>
