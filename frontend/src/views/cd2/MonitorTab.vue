<script setup lang="ts">
/**
 * MonitorTab — CD2 传输监控状态展示
 * 只读快照：展示后台监控线程状态与当前监控中的任务，按需刷新。
 */
import { onMounted, ref } from 'vue'
import { cd2Api } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'MonitorTab' })

const { error: showError } = useNotification()

const loading = ref(false)
const status = ref<any>({})
// CD2 服务器运行状态 (GetRunningInfo / GetAllTasksCount / GetSystemInfo)
const serverLoading = ref(false)
const server = ref<any>({})

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

const formatUptime = (sec: number) => {
  if (!sec) return '-'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return d > 0 ? `${d} 天 ${h} 时` : h > 0 ? `${h} 时 ${m} 分` : `${m} 分`
}

const loadServerInfo = async () => {
  serverLoading.value = true
  try {
    server.value = await cd2Api.getServerInfo()
  } catch (e: any) {
    showError(e?.message || '获取服务器状态失败')
  } finally {
    serverLoading.value = false
  }
}

const operatorTypeText = (type: number) => {
  switch (type) {
    case 0: return '挂载'
    case 1: return '复制'
    case 2: return '备份'
    case 3: return '远程上传'
    default: return '未知'
  }
}

const loadStatus = async () => {
  loading.value = true
  try {
    status.value = await cd2Api.getMonitorStatus()
  } catch (e: any) {
    showError(e?.message || '获取监控状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadServerInfo()
})
</script>

<template>
  <!-- CD2 服务器状态 -->
  <v-card class="glass-card mb-4">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-server</v-icon>
      CD2 服务器状态
      <v-chip
        v-if="server.system?.is_login"
        size="x-small"
        variant="tonal"
        color="success"
        class="ml-2"
      >
        {{ server.system?.user_name || '已登录' }}
      </v-chip>
      <v-spacer />
      <v-btn
        icon="mdi-refresh"
        size="small"
        variant="text"
        :loading="serverLoading"
        title="刷新"
        @click="loadServerInfo"
      />
    </v-card-title>
    <v-divider />
    <v-card-text>
      <v-row>
        <v-col cols="6" sm="3">
          <div class="text-caption text-medium-emphasis">CPU 使用率</div>
          <div class="text-h6 font-weight-bold">{{ server.running?.cpu_usage ?? '-' }}%</div>
        </v-col>
        <v-col cols="6" sm="3">
          <div class="text-caption text-medium-emphasis">内存</div>
          <div class="text-h6 font-weight-bold">
            {{ server.running?.mem_used_mb ?? '-' }} <span class="text-caption">/ {{ server.running?.mem_total_mb ?? '-' }} MB</span>
          </div>
        </v-col>
        <v-col cols="6" sm="3">
          <div class="text-caption text-medium-emphasis">下载速度</div>
          <div class="text-h6 font-weight-bold text-primary">{{ formatSpeed(server.running?.download_speed || 0) }}</div>
        </v-col>
        <v-col cols="6" sm="3">
          <div class="text-caption text-medium-emphasis">上传速度</div>
          <div class="text-h6 font-weight-bold text-success">{{ formatSpeed(server.running?.upload_speed || 0) }}</div>
        </v-col>
      </v-row>
      <div class="d-flex align-center flex-wrap gap-2 mt-2">
        <v-chip size="small" variant="tonal" prepend-icon="mdi-download">
          下载任务 {{ server.tasks?.download_count ?? 0 }}
        </v-chip>
        <v-chip size="small" variant="tonal" prepend-icon="mdi-upload">
          上传任务 {{ server.tasks?.upload_count ?? 0 }}
        </v-chip>
        <v-chip size="small" variant="tonal" prepend-icon="mdi-content-copy">
          复制任务 {{ server.tasks?.copy_task_count ?? 0 }}
        </v-chip>
        <v-spacer />
        <span class="text-caption text-medium-emphasis">运行时长: {{ formatUptime(server.running?.uptime_sec || 0) }}</span>
      </div>
    </v-card-text>
  </v-card>

  <!-- 监控状态 -->
  <v-card class="glass-card mb-4">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-transfer</v-icon>
      传输监控状态
      <v-spacer />
      <v-btn
        color="primary"
        variant="tonal"
        size="small"
        prepend-icon="mdi-refresh"
        :loading="loading"
        @click="loadStatus"
      >
        刷新
      </v-btn>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="3">
          <div class="text-caption text-medium-emphasis">运行状态</div>
          <v-chip
            size="small"
            variant="tonal"
            :color="status.running ? 'success' : 'error'"
            class="mt-1"
          >
            {{ status.running ? '运行中' : '已停止' }}
          </v-chip>
        </v-col>
        <v-col cols="12" sm="3">
          <div class="text-caption text-medium-emphasis">是否启用</div>
          <v-chip
            size="small"
            variant="tonal"
            :color="status.enabled ? 'success' : 'grey'"
            class="mt-1"
          >
            {{ status.enabled ? '已启用' : '未启用' }}
          </v-chip>
        </v-col>
        <v-col cols="12" sm="3">
          <div class="text-caption text-medium-emphasis">轮询间隔</div>
          <div class="text-body-2 font-weight-medium mt-1">{{ status.interval ?? '-' }} 秒</div>
        </v-col>
        <v-col cols="12" sm="3">
          <div class="text-caption text-medium-emphasis">监控中任务数</div>
          <div class="text-body-2 font-weight-medium mt-1">{{ status.watching_count ?? 0 }}</div>
        </v-col>
      </v-row>
      <v-alert
        v-if="status.configured === false"
        type="warning"
        variant="tonal"
        density="compact"
        class="mt-4"
      >
        未配置 CloudDrive2 客户端，请先在「系统设置 → 下载器管理」中添加。
      </v-alert>
      <v-alert
        v-else-if="status.enabled === false"
        type="info"
        variant="tonal"
        density="compact"
        class="mt-4"
      >
        传输监控未开启，可在 CD2 客户端配置中打开「后台传输监控」。
      </v-alert>
    </v-card-text>
  </v-card>

  <!-- 监控中的任务快照 -->
  <v-card class="glass-card mb-4">
    <v-card-title>
      <v-icon class="mr-2">mdi-clipboard-clock-outline</v-icon>
      当前监控中的任务
    </v-card-title>
    <v-divider />
    <v-card-text>
      <div v-if="!status.watching?.length" class="text-center text-medium-emphasis pa-6">
        暂无监控中的传输任务
      </div>
      <v-list v-else class="py-0">
        <v-list-item v-for="item in status.watching" :key="item.path" class="px-2">
          <template #prepend>
            <v-icon>mdi-file-transfer-outline</v-icon>
          </template>
          <v-list-item-title class="text-body-2 text-truncate">{{ item.name }}</v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ item.path }}
          </v-list-item-subtitle>
          <template #append>
            <div class="d-flex align-center gap-2">
              <v-chip size="x-small" variant="tonal">{{ operatorTypeText(item.type) }}</v-chip>
              <v-chip size="x-small" variant="tonal" color="primary">{{ item.status }}</v-chip>
            </div>
          </template>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>
