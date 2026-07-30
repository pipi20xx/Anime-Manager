<script setup lang="ts">
/**
 * ServiceStatusTab — 服务状态
 *
 * 功能: 系统服务列表、文件监控任务、运行时统计、规则统计
 */
import { ref, computed, onMounted } from 'vue'
import { dataCenterApi, api } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'ServiceStatusTab' })

const { error: showError } = useNotification()

const loading = ref(false)
const servicesData = ref<any>({ services: [], monitors: [], observers_count: 0, workers_count: 0, queues_count: 0, rules: { custom_noise: { local: 0, remote: 0 }, custom_groups: { local: 0, remote: 0, builtin: 0 }, custom_render: { local: 0, remote: 0 }, privileged: { local: 0, remote: 0 } } })

// 队列弹窗
const queueModalVisible = ref(false)
const queueLoading = ref(false)
const queueItems = ref<string[]>([])
const queueModalData = ref<{ id: string; name: string; count: number } | null>(null)

const runningServicesCount = computed(() =>
  servicesData.value.services.filter((s: any) => s.running && s.enabled).length
)

const runningMonitorsCount = computed(() =>
  servicesData.value.monitors.filter((m: any) => m.running).length
)

async function fetchServicesStatus() {
  loading.value = true
  try {
    const data = await dataCenterApi.getServicesStatus()
    servicesData.value = data || servicesData.value
  } catch (e) {
    showError('获取服务状态失败')
  } finally {
    loading.value = false
  }
}

async function showQueueModal(monitor: any) {
  queueModalData.value = { id: monitor.id, name: monitor.name, count: monitor.queue_size }
  queueItems.value = []
  queueModalVisible.value = true
  queueLoading.value = true
  try {
    const result = await api.get<any>(`/api/system/queue/${monitor.id}`)
    queueItems.value = result?.items || []
    queueModalData.value = { ...queueModalData.value!, count: result?.count ?? monitor.queue_size }
  } catch (e) {
    console.error('获取队列内容失败', e)
  } finally {
    queueLoading.value = false
  }
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
  fetchServicesStatus()
})
</script>

<template>
  <div>
    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" size="32" />
    </div>

    <template v-else>
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
          <v-chip size="small" color="success" variant="tonal">
            {{ runningMonitorsCount }} / {{ servicesData.monitors.length }} 活跃
          </v-chip>
        </div>
        <div v-if="servicesData.monitors.length > 0" class="card-grid mb-4">
          <v-card
            v-for="monitor in servicesData.monitors"
            :key="monitor.id"
            class="glass-card"
            :class="monitor.running ? 'service-card--running' : 'service-card--disabled'"
          >
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between mb-2">
                <div class="d-flex align-center ga-2 flex-wrap">
                  <v-chip size="x-small" color="info" variant="tonal">
                    {{ monitor.type === 'organize' ? '整理' : 'STRM' }}
                  </v-chip>
                  <span class="text-body-2 font-weight-bold">{{ monitor.name }}</span>
                  <v-chip size="x-small" color="grey" variant="tonal">{{ monitor.mode }}</v-chip>
                  <v-chip v-if="monitor.type === 'strm' && monitor.webhook_enabled" size="x-small" color="info" variant="tonal">接受联动</v-chip>
                  <v-chip v-if="monitor.type === 'organize' && monitor.check_emby_exists" size="x-small" color="info" variant="tonal">Emby检查</v-chip>
                  <v-chip v-if="monitor.type === 'organize' && monitor.calculate_hash" size="x-small" color="error" variant="tonal">哈希计算</v-chip>
                </div>
                <v-chip size="x-small" :color="getStatusColor(monitor)" variant="tonal">
                  {{ getStatusTag(monitor).text }}
                </v-chip>
              </div>
              <div class="d-flex ga-4 mb-1">
                <span class="text-caption text-medium-emphasis">源目录: <code>{{ monitor.source_dir || '-' }}</code></span>
                <span class="text-caption text-medium-emphasis">目标: <code>{{ monitor.target_dir || '-' }}</code></span>
              </div>
              <div v-if="monitor.running && monitor.queue_size > 0" class="d-flex align-center justify-space-between mt-2 pt-2 queue-divider">
                <span class="text-caption text-info">队列中: {{ monitor.queue_size }} 个文件待处理</span>
                <v-btn size="x-small" variant="tonal" color="info" prepend-icon="mdi-format-list-numbered" @click="showQueueModal(monitor)">查看队列</v-btn>
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
    <v-dialog v-model="queueModalVisible" max-width="800">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center justify-space-between">
          <div class="d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-format-list-bulleted</v-icon>
            <span>{{ queueModalData?.name }} - 队列内容</span>
          </div>
          <v-chip size="small" color="info" variant="tonal">{{ queueModalData?.count || 0 }} 个文件</v-chip>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <div v-if="queueLoading" class="d-flex justify-center pa-4">
            <v-progress-circular indeterminate color="primary" size="24" />
          </div>
          <div v-else-if="queueItems.length > 0" class="queue-scroll">
            <div v-for="(item, index) in queueItems" :key="index" class="d-flex align-center ga-3 pa-2 queue-item">
              <span class="text-caption text-medium-emphasis queue-item-index">{{ index + 1 }}</span>
              <code class="text-caption">{{ item }}</code>
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis pa-4">队列为空</div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>
