<script setup lang="ts">
/**
 * ServiceStatusTab — 服务状态
 *
 * 功能: 系统服务列表、文件监控任务、运行时统计、规则统计
 *       队列可视化（自动刷新、文件列表、排序展示）
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { dataCenterApi, api } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'ServiceStatusTab' })

const { error: showError } = useNotification()

const loading = ref(false)
const autoRefresh = ref(true)
const servicesData = ref<any>({ services: [], monitors: [], observers_count: 0, workers_count: 0, queues_count: 0, rules: { custom_noise: { local: 0, remote: 0 }, custom_groups: { local: 0, remote: 0, builtin: 0 }, custom_render: { local: 0, remote: 0 }, privileged: { local: 0, remote: 0 } } })

// 队列弹窗
const queueModalVisible = ref(false)
const queueLoading = ref(false)
const queueItems = ref<string[]>([])
const queueModalData = ref<{ id: string; name: string; count: number; type: string } | null>(null)
const queueHasLoaded = ref(false)

// 定时器
let refreshTimer: ReturnType<typeof setInterval> | null = null
let queueRefreshTimer: ReturnType<typeof setInterval> | null = null

const runningServicesCount = computed(() =>
  servicesData.value.services.filter((s: any) => s.running && s.enabled).length
)

const runningMonitorsCount = computed(() =>
  servicesData.value.monitors.filter((m: any) => m.running).length
)

// 所有有队列的监控任务（运行中 + 已启用）
const queueMonitors = computed(() =>
  servicesData.value.monitors.filter((m: any) => m.running || m.enabled)
)

// 队列中总待处理文件数
const totalQueuedFiles = computed(() =>
  servicesData.value.monitors.reduce((sum: number, m: any) => sum + (m.queue_size || 0), 0)
)

async function fetchServicesStatus() {
  try {
    const data = await dataCenterApi.getServicesStatus()
    if (data) servicesData.value = data
  } catch (e) {
    // 静默失败，避免自动刷新时频繁弹错误
  } finally {
    loading.value = false
  }
}

async function fetchServicesStatusInitial() {
  loading.value = true
  await fetchServicesStatus()
}

async function showQueueModal(monitor: any) {
  queueModalData.value = { id: monitor.id, name: monitor.name, count: monitor.queue_size, type: monitor.type }
  queueItems.value = []
  queueHasLoaded.value = false
  queueModalVisible.value = true
  await fetchQueueItems()
  // 弹窗打开后自动刷新队列内容
  startQueueRefresh()
}

async function fetchQueueItems() {
  if (!queueModalData.value) return
  // 仅首次加载（队列为空且未加载过）时显示 loading，避免自动刷新闪烁
  const isFirstLoad = queueItems.value.length === 0 && !queueHasLoaded.value
  if (isFirstLoad) queueLoading.value = true
  try {
    const result = await api.get<any>(`/api/system/queue/${queueModalData.value.id}`)
    queueItems.value = result?.items || []
    queueModalData.value = { ...queueModalData.value!, count: result?.count ?? 0 }
    queueHasLoaded.value = true
  } catch (e) {
    console.error('获取队列内容失败', e)
  } finally {
    queueLoading.value = false
  }
}

function startQueueRefresh() {
  stopQueueRefresh()
  queueRefreshTimer = setInterval(fetchQueueItems, 2000)
}

function stopQueueRefresh() {
  if (queueRefreshTimer) {
    clearInterval(queueRefreshTimer)
    queueRefreshTimer = null
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (autoRefresh.value) {
    refreshTimer = setInterval(fetchServicesStatus, 3000)
  }
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

watch(autoRefresh, (val) => {
  if (val) startAutoRefresh()
  else stopAutoRefresh()
})

// 弹窗关闭时停止刷新
watch(queueModalVisible, (val) => {
  if (!val) stopQueueRefresh()
})

// 从路径中提取文件名
function basename(path: string): string {
  if (!path) return '-'
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

// 从路径中提取所在目录
function dirname(path: string): string {
  if (!path) return ''
  const parts = path.replace(/\\/g, '/').split('/')
  parts.pop()
  return parts.join('/')
}

function getStatusTag(service: any): { text: string; type: string } {
  if (!service.enabled) return { text: '已禁用', type: 'default' }
  if (service.running) return { text: '运行中', type: 'success' }
  return { text: '已停止', type: 'error' }
}

function getStatusColor(service: any): string {
  const status = getStatusTag(service)
  const colorMap: Record<string, string> = {
    success: 'success',
    warning: 'warning',
    error: 'error',
    default: 'grey',
  }
  return colorMap[status.type] || 'grey'
}

function formatNextRun(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  fetchServicesStatusInitial()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
  stopQueueRefresh()
})
</script>

<template>
  <div>
    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" size="32" />
    </div>

    <template v-else>
      <!-- 自动刷新开关 -->
      <div class="d-flex align-center justify-end mb-2">
        <span class="text-caption text-medium-emphasis mr-2">自动刷新</span>
        <v-switch v-model="autoRefresh" density="compact" hide-details color="primary" size="small" />
        <v-btn icon="mdi-refresh" variant="text" size="small" class="ml-1" @click="fetchServicesStatus" />
      </div>

      <!-- 系统服务 -->
      <div class="d-flex align-center justify-space-between mb-3">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-server-outline</v-icon>
          <span class="text-subtitle-1 font-weight-bold">系统服务</span>
        </div>
        <v-chip size="small" color="info" variant="tonal">
          {{ runningServicesCount }} / {{ servicesData.services.length }} 运行中
        </v-chip>
      </div>
      <div v-if="servicesData.services.length > 0" class="card-grid mb-4">
        <v-card
          v-for="service in servicesData.services"
          :key="service.id"
          class="glass-card"
          :class="service.running && service.enabled ? 'service-card--running' : service.enabled ? 'service-card--stopped' : 'service-card--disabled'"
        >
          <v-card-text class="pa-4">
            <div class="d-flex align-center justify-space-between mb-2">
              <span class="text-body-2 font-weight-bold">{{ service.name }}</span>
              <v-chip size="x-small" :color="getStatusColor(service)" variant="tonal">
                {{ getStatusTag(service).text }}
              </v-chip>
            </div>
            <div class="d-flex ga-4 mb-1">
              <span class="text-caption text-medium-emphasis">间隔: <span class="font-monospace">{{ service.interval }}</span></span>
              <span v-if="service.next_run" class="text-caption text-medium-emphasis">
                下次执行: <span class="font-monospace">{{ formatNextRun(service.next_run) }}</span>
              </span>
              <span v-if="service.last_run" class="text-caption text-medium-emphasis">
                上次同步: <span class="font-monospace">{{ formatNextRun(service.last_run) }}</span>
              </span>
            </div>
            <div class="text-caption text-medium-emphasis">{{ service.description }}</div>
          </v-card-text>
        </v-card>
      </div>
      <div v-else class="text-center text-medium-emphasis pa-4 mb-4">暂无服务数据</div>

      <!-- 文件监控任务 -->
      <template v-if="servicesData.monitors.length > 0">
        <div class="d-flex align-center justify-space-between mb-3">
          <div class="d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-eye-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">文件监控任务</span>
          </div>
          <div class="d-flex align-center ga-2">
            <v-chip v-if="totalQueuedFiles > 0" size="small" color="warning" variant="tonal">
              <v-icon start size="14">mdi-tray-alert</v-icon>
              {{ totalQueuedFiles }} 个文件排队中
            </v-chip>
            <v-chip size="small" color="success" variant="tonal">
              {{ runningMonitorsCount }} / {{ servicesData.monitors.length }} 活跃
            </v-chip>
          </div>
        </div>
        <div v-if="servicesData.monitors.length > 0" class="card-grid mb-4">
          <v-card
            v-for="monitor in servicesData.monitors"
            :key="monitor.id"
            class="glass-card"
            :class="monitor.running ? 'service-card--running' : 'service-card--disabled'"
          >
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between mb-1">
                <div class="d-flex align-center ga-2 min-width-0 flex-1-1-auto">
                  <v-chip size="x-small" color="info" variant="tonal" class="flex-shrink-0">
                    {{ monitor.type === 'organize' ? '整理' : 'STRM' }}
                  </v-chip>
                  <span class="text-body-2 font-weight-bold text-truncate">{{ monitor.name }}</span>
                </div>
                <v-chip size="x-small" :color="getStatusColor(monitor)" variant="tonal" class="flex-shrink-0">
                  {{ getStatusTag(monitor).text }}
                </v-chip>
              </div>
              <div class="d-flex align-center ga-1 flex-wrap mb-1">
                <v-chip size="x-small" color="grey" variant="tonal">{{ monitor.mode }}</v-chip>
                <v-chip v-if="monitor.type === 'strm' && monitor.webhook_enabled" size="x-small" color="info" variant="tonal">接受联动</v-chip>
                <v-chip v-if="monitor.type === 'organize' && monitor.check_emby_exists" size="x-small" color="info" variant="tonal">Emby检查</v-chip>
                <v-chip v-if="monitor.type === 'organize' && monitor.calculate_hash" size="x-small" color="error" variant="tonal">哈希计算</v-chip>
              </div>
              <div class="d-flex ga-4 mb-1">
                <span class="text-caption text-medium-emphasis">源目录: {{ monitor.source_dir || '-' }}</span>
                <span class="text-caption text-medium-emphasis">目标: {{ monitor.target_dir || '-' }}</span>
              </div>
              <!-- 队列状态条 (始终显示) -->
              <div v-if="monitor.running" class="mt-2 pt-2 queue-divider">
                <div class="d-flex align-center justify-space-between mb-1">
                  <div class="d-flex align-center ga-2">
                    <v-icon size="14" :color="monitor.queue_size > 0 ? 'warning' : 'success'">
                      {{ monitor.queue_size > 0 ? 'mdi-tray-pending' : 'mdi-tray' }}
                    </v-icon>
                    <span class="text-caption" :class="monitor.queue_size > 0 ? 'text-warning' : 'text-medium-emphasis'">
                      队列: {{ monitor.queue_size }} 个文件待处理
                    </span>
                  </div>
                  <v-btn size="x-small" variant="tonal" :color="monitor.queue_size > 0 ? 'warning' : 'info'" prepend-icon="mdi-format-list-numbered" @click="showQueueModal(monitor)">
                    查看队列
                  </v-btn>
                </div>
                <!-- 队列进度可视化条 -->
                <div v-if="monitor.queue_size > 0" class="queue-bar-wrapper">
                  <div class="queue-bar-fill" :style="{ width: Math.min(monitor.queue_size * 5, 100) + '%' }" />
                </div>
              </div>
            </v-card-text>
          </v-card>
        </div>
      </template>

      <!-- 运行时统计 -->
      <div class="d-flex align-center ga-2 mb-3">
        <v-icon color="primary" size="20">mdi-chart-bar</v-icon>
        <span class="text-subtitle-1 font-weight-bold">运行时统计</span>
      </div>
      <v-row class="mb-4">
        <v-col cols="4">
          <v-card class="glass-card text-center">
            <v-card-text class="pa-4">
              <div class="text-h5 font-weight-bold">{{ servicesData.observers_count }}</div>
              <div class="text-caption text-medium-emphasis">文件观察器</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="4">
          <v-card class="glass-card text-center">
            <v-card-text class="pa-4">
              <div class="text-h5 font-weight-bold">{{ servicesData.workers_count }}</div>
              <div class="text-caption text-medium-emphasis">工作线程</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="4">
          <v-card class="glass-card text-center">
            <v-card-text class="pa-4">
              <div class="text-h5 font-weight-bold">{{ servicesData.queues_count }}</div>
              <div class="text-caption text-medium-emphasis">任务队列</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- 规则统计 -->
      <div class="d-flex align-center ga-2 mb-3">
        <v-icon color="primary" size="20">mdi-ruler-square</v-icon>
        <span class="text-subtitle-1 font-weight-bold">规则统计</span>
      </div>
      <div class="card-grid card-grid--4">
        <v-card class="glass-card">
          <v-card-text class="pa-4">
            <div class="text-body-2 font-weight-bold mb-3">自定义识别词</div>
            <div class="d-flex justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_noise.local }} 条</v-chip>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-caption text-medium-emphasis">远程规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_noise.remote }} 条</v-chip>
            </div>
          </v-card-text>
        </v-card>
        <v-card class="glass-card">
          <v-card-text class="pa-4">
            <div class="text-body-2 font-weight-bold mb-3">自定义制作组</div>
            <div class="d-flex justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_groups.local }} 条</v-chip>
            </div>
            <div class="d-flex justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">远程规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_groups.remote }} 条</v-chip>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-caption text-medium-emphasis">内置规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_groups.builtin || 0 }} 条</v-chip>
            </div>
          </v-card-text>
        </v-card>
        <v-card class="glass-card">
          <v-card-text class="pa-4">
            <div class="text-body-2 font-weight-bold mb-3">自定义渲染词</div>
            <div class="d-flex justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_render.local }} 条</v-chip>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-caption text-medium-emphasis">远程规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.custom_render.remote }} 条</v-chip>
            </div>
          </v-card-text>
        </v-card>
        <v-card class="glass-card">
          <v-card-text class="pa-4">
            <div class="text-body-2 font-weight-bold mb-3">特权规则</div>
            <div class="d-flex justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.privileged.local }} 条</v-chip>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-caption text-medium-emphasis">远程规则</span>
              <v-chip size="x-small" color="info" variant="tonal">{{ servicesData.rules.privileged.remote }} 条</v-chip>
            </div>
          </v-card-text>
        </v-card>
      </div>
    </template>

    <!-- 队列内容弹窗 -->
    <v-dialog v-model="queueModalVisible" max-width="850">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <div class="d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-format-list-bulleted</v-icon>
            <span>{{ queueModalData?.name }} - 队列内容</span>
          </div>
          <v-chip size="small" :color="(queueModalData?.count || 0) > 0 ? 'warning' : 'success'" variant="tonal" class="ml-2">
            {{ queueModalData?.count || 0 }} 个文件
          </v-chip>
          <v-chip v-if="queueModalData?.type" size="x-small" color="info" variant="tonal" class="ml-1">
            {{ queueModalData.type === 'organize' ? '整理' : 'STRM' }}
          </v-chip>
          <v-spacer />
          <v-btn icon="mdi-refresh" variant="text" size="small" class="mr-1" @click="fetchQueueItems" />
          <v-btn icon="mdi-close" variant="text" size="small" @click="queueModalVisible = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-0">
          <div v-if="queueLoading && queueItems.length === 0" class="d-flex justify-center pa-8">
            <v-progress-circular indeterminate color="primary" size="32" />
          </div>
          <div v-else-if="queueItems.length > 0" class="queue-scroll">
            <div v-for="(item, index) in queueItems" :key="index" class="queue-item-row">
              <div class="queue-item-badge" :class="index === 0 ? 'queue-item-badge--active' : ''">
                {{ index + 1 }}
              </div>
              <div class="queue-item-content">
                <div class="queue-item-filename">{{ basename(item) }}</div>
                <div class="queue-item-dirpath">{{ dirname(item) }}</div>
              </div>
              <v-chip v-if="index === 0" size="x-small" color="primary" variant="tonal" class="queue-item-status">
                正在处理
              </v-chip>
              <v-icon v-else size="14" color="grey" class="queue-item-status-icon">mdi-clock-outline</v-icon>
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis pa-8">
            <v-icon size="40" color="grey" class="mb-2">mdi-tray</v-icon>
            <div>队列为空，没有等待处理的文件</div>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

