<script setup lang="ts">
/**
 * RapidRetryTab — CD2 秒传管理
 *
 * 展示秒传重试队列（rapid_upload_retry 表）：
 * - 状态筛选（等待中/传输中/已完成/失败）
 * - 每条记录：文件、云端目标、重试进度、下次重试时间、最近消息
 * - 操作：立即重试 / 删除 / 清空已结束记录
 * - 30 秒自动刷新（队列由后台推进）
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { organizerApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'RapidRetryTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const recordList = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref<string>('all')

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchList(isRefresh = true) {
  if (loading.value) return
  loading.value = true
  try {
    const statusParam = statusFilter.value !== 'all' ? statusFilter.value : undefined
    const data = await organizerApi.getRapidRetryList({ limit: 200, status: statusParam })
    recordList.value = Array.isArray(data) ? data : (data?.items || data?.data || [])
  } catch (e) {
    // 静默
  } finally {
    loading.value = false
  }
}

function filterByStatus(status?: string) {
  statusFilter.value = status || 'all'
  fetchList()
}

async function retryRecord(item: any) {
  const ok = await confirm({
    title: '确认立即重试',
    content: `将立即对「${basename(item.local_path)}」重新尝试秒传${item.status === 'failed' ? '（重置已试次数）' : ''}，进度稍后自动刷新。`,
    confirmText: '立即重试',
  })
  if (!ok) return
  try {
    const data = await organizerApi.retryRapidRetry(item.id)
    if (data?.success) {
      success(data.message || '已触发立即重试')
    } else {
      showError(data?.message || '触发失败')
    }
  } catch (e: any) {
    showError('触发失败: ' + (e.message || ''))
  }
  fetchList()
}

async function deleteRecord(item: any) {
  const ok = await confirm({
    title: '确认删除',
    content: `确定删除「${basename(item.local_path)}」的重试记录吗？不会影响磁盘文件和已上传的云端文件。`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    const data = await organizerApi.deleteRapidRetry(item.id)
    if (data?.success) {
      success('已删除')
      recordList.value = recordList.value.filter((r: any) => r.id !== item.id)
    } else {
      showError(data?.message || '删除失败')
    }
  } catch (e: any) {
    showError('删除失败: ' + (e.message || ''))
  }
}

async function clearFinished() {
  const ok = await confirm({
    title: '确认清空',
    content: '确定清除所有已完成和失败的秒传重试记录吗？等待中的记录不受影响。',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    const data = await organizerApi.clearFinishedRapidRetry()
    if (data?.success) {
      success(data.message || '已清空')
    } else {
      showError(data?.message || '清空失败')
    }
  } catch (e: any) {
    showError('清空失败: ' + (e.message || ''))
  }
  fetchList()
}

// --- 辅助函数 ---
function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'warning',
    running: 'info',
    done: 'success',
    failed: 'error',
  }
  return map[status] || 'default'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '传输中',
    done: '已完成',
    failed: '已失败',
  }
  return map[status] || status || '-'
}

function modeLabel(mode: string): string {
  const map: Record<string, string> = {
    rapid_then_upload: '秒传优先·回退上传',
    rapid_only: '仅秒传',
  }
  return map[mode] || mode || '-'
}

function actionLabel(type: string): string {
  return type === 'cd2_copy' ? '复制' : '移动'
}

function basename(path: string): string {
  if (!path) return '-'
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

function formatTime(timeStr: string): string {
  if (!timeStr) return '-'
  return String(timeStr).replace('T', ' ').split('.')[0]
}

onMounted(() => {
  fetchList()
  pollTimer = setInterval(() => fetchList(), 30000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

defineExpose({ fetchList })
</script>

<template>
  <div>
    <!-- 筛选栏 -->
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <v-chip :color="statusFilter === 'all' ? 'primary' : undefined" :variant="statusFilter === 'all' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterByStatus()">全部</v-chip>
      <v-chip :color="statusFilter === 'pending' ? 'warning' : undefined" :variant="statusFilter === 'pending' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterByStatus('pending')">等待中</v-chip>
      <v-chip :color="statusFilter === 'running' ? 'info' : undefined" :variant="statusFilter === 'running' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterByStatus('running')">传输中</v-chip>
      <v-chip :color="statusFilter === 'done' ? 'success' : undefined" :variant="statusFilter === 'done' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterByStatus('done')">已完成</v-chip>
      <v-chip :color="statusFilter === 'failed' ? 'error' : undefined" :variant="statusFilter === 'failed' ? 'flat' : 'outlined'" size="small" label class="cursor-pointer history-filter-chip" @click="filterByStatus('failed')">已失败</v-chip>
      <v-spacer />
      <v-btn variant="tonal" size="small" prepend-icon="mdi-refresh" :loading="loading" @click="fetchList()">刷新</v-btn>
      <v-btn variant="tonal" color="error" size="small" prepend-icon="mdi-delete-sweep-outline" @click="clearFinished">清空已结束</v-btn>
    </div>

    <v-skeleton-loader v-if="loading && recordList.length === 0" type="list-item@5" />

    <div v-else-if="recordList.length > 0">
      <v-card
        v-for="item in recordList"
        :key="item.id"
        class="org-history-item glass-card mb-3 pa-4"
      >
        <!-- 1. Header: 文件名 + 状态 -->
        <div class="d-flex align-center justify-space-between ga-2">
          <span class="text-subtitle-1 font-weight-bold text-truncate">{{ basename(item.local_path) }}</span>
          <v-chip size="small" :color="statusColor(item.status)" variant="tonal" class="flex-shrink-0">
            {{ statusLabel(item.status) }}
          </v-chip>
        </div>

        <!-- 最近消息 -->
        <v-alert
          v-if="item.message"
          :type="item.status === 'failed' ? 'error' : 'info'"
          density="compact"
          variant="tonal"
          class="mt-2"
          :text="item.message"
        />

        <!-- 2. 路径 -->
        <div class="org-path-container mt-3">
          <div class="org-path-item">
            <span class="org-path-label">本地源</span>
            <v-icon size="14" class="mr-1">mdi-folder-outline</v-icon>
            <span class="org-path-text" :title="item.local_path">{{ item.local_path }}</span>
          </div>
          <div class="org-path-divider">
            <v-icon size="14" color="primary">mdi-arrow-down</v-icon>
          </div>
          <div class="org-path-item">
            <span class="org-path-label">云端目标</span>
            <v-icon size="14" class="mr-1" color="primary">mdi-cloud-check-outline</v-icon>
            <span class="org-path-text org-path-target" :title="item.cloud_path">{{ item.cloud_path }}</span>
          </div>
        </div>

        <!-- 3. Footer: 详情 + 操作 -->
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mt-3">
          <div class="d-flex align-center ga-2 flex-wrap min-width-0">
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--action">
              {{ actionLabel(item.action_type) }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--size">
              {{ modeLabel(item.rapid_mode) }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--time">
              已试 {{ item.attempts || 0 }}/{{ item.max_retries }} 次
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--time" v-if="item.status === 'pending'">
              下次重试 {{ formatTime(item.next_retry_at) }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="meta-tag meta-tag--time" v-if="item.created_at">
              入队 {{ formatTime(item.created_at) }}
            </v-chip>
          </div>
          <div class="d-flex align-center ga-1 flex-shrink-0">
            <v-btn
              v-if="item.status === 'pending' || item.status === 'failed'"
              size="small"
              variant="tonal"
              color="warning"
              prepend-icon="mdi-flash"
              @click="retryRecord(item)"
            >立即重试</v-btn>
            <v-btn
              v-if="item.status !== 'running'"
              size="small"
              variant="tonal"
              color="error"
              prepend-icon="mdi-delete-outline"
              @click="deleteRecord(item)"
            >删除</v-btn>
          </div>
        </div>
      </v-card>

      <div class="text-caption text-medium-emphasis text-center pa-4">
        共 {{ recordList.length }} 条记录，每 30 秒自动刷新
      </div>
    </div>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-flash-alert-outline</v-icon>
      <div class="text-h6 font-weight-medium">队列为空</div>
      <div class="text-body-2 text-medium-emphasis mt-2">
        开启秒传模式的整理任务未命中时，文件会进入这里等待自动重试
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-filter-chip {
  height: 40px !important;
}
</style>
