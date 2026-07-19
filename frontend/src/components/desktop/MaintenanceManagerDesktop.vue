<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  NCard, NButton, NSpace, NIcon, NAlert, NGrid, NGridItem, NSpin, NStatistic, NProgress, useDialog, useMessage
} from 'naive-ui'
import {
  ServerIcon as DbIcon
} from '@heroicons/vue/24/outline'
import { useMaintenance } from '../../composables/components/useMaintenance'
import { useEventStream } from '../../composables/useEventStream'

const dialog = useDialog()
const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const fingerprintLoading = ref(false)

const clearFingerprints = () => {
  dialog.warning({
    title: '确认清空智能记忆',
    content: '这将删除所有智能记忆缓存。识别速度可能会暂时变慢，但不会影响已刮削的数据。',
    positiveText: '清空记忆',
    negativeText: '取消',
    onPositiveClick: async () => {
      fingerprintLoading.value = true
      try {
        const res = await fetch(`${API_BASE}/api/cache/clear_fingerprints`, { method: 'POST' })
        const data = await res.json()
        message.success(data.message)
      } finally {
        fingerprintLoading.value = false
      }
    }
  })
}

const cleanupInvalidFingerprints = () => {
  dialog.info({
    title: '智能清理无效记忆',
    content: '将清理过于简单、缺乏区分度的指纹记录（如只有季集模式的记录），保留有效的记忆。',
    positiveText: '智能清理',
    negativeText: '取消',
    onPositiveClick: async () => {
      fingerprintLoading.value = true
      try {
        const res = await fetch(`${API_BASE}/api/cache/cleanup_invalid_fingerprints`, { method: 'POST' })
        const data = await res.json()
        if (data.status === 'success') {
          message.success(data.message)
        } else {
          message.error('清理失败')
        }
      } finally {
        fingerprintLoading.value = false
      }
    }
  })
}

// ============ Emby 索引同步 & BangumiData 同步 ============
interface ServiceStatus {
  id: string
  name: string
  type: 'scheduler' | 'thread'
  enabled: boolean
  running: boolean
  interval: string
  next_run: string | null
  last_run: string | null
  description: string
}

const services = ref<ServiceStatus[]>([])
const embySyncLoading = ref(false)
const bgmSyncLoading = ref(false)

const embyService = computed(() => services.value.find(s => s.id === 'emby_index_sync') || null)
const bgmService = computed(() => services.value.find(s => s.id === 'bgm_mapping_sync') || null)

const fetchServices = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/system/services`)
    if (res.ok) {
      const data = await res.json()
      services.value = data.services || []
    }
  } catch (e) {
    console.error('获取服务状态失败', e)
  }
}

const formatTime = (isoString: string | null): string => {
  if (!isoString) return '—'
  try {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return '—'
  }
}

// 从 description 解析当前条目数（格式："...（当前 N 条）"）
const parseCount = (desc: string | undefined): number | null => {
  if (!desc) return null
  const match = desc.match(/当前\s*(\d+)\s*条/)
  return match ? parseInt(match[1], 10) : null
}

const handleEmbySync = async () => {
  embySyncLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/tmdb/emby/sync-index`, { method: 'POST' })
    const data = await res.json()
    if (res.ok && data.status === 'success') {
      message.success(`Emby 索引同步完成，共 ${data.count} 条`)
      await fetchServices()
    } else {
      message.error(data.detail || 'Emby 索引同步失败')
    }
  } catch (e) {
    message.error('请求失败')
  } finally {
    embySyncLoading.value = false
  }
}

const handleBgmSync = async () => {
  bgmSyncLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/bangumi/mapping/sync?force=true`, { method: 'POST' })
    const data = await res.json()
    if (res.ok && data.success) {
      message.success(data.message || `BangumiData 同步完成，共 ${data.count} 条`)
      await fetchServices()
    } else {
      message.error(data.message || data.detail || 'BangumiData 同步失败')
    }
  } catch (e) {
    message.error('请求失败')
  } finally {
    bgmSyncLoading.value = false
  }
}

// ============ Bangumi Subject 缓存预热 ============
const bgmWarmupLoading = ref(false)
const bgmWarmupStatus = ref<{ running: boolean; progress: any }>({ running: false, progress: {} })

const { on: onEvent, onReconnect } = useEventStream()
let _unsubscribeWarmup: (() => void) | null = null
let _unsubscribeReconnect: (() => void) | null = null

const warmupPercent = computed(() => {
  const p = bgmWarmupStatus.value.progress
  if (!p || !p.total) return 0
  return Math.round((p.done / p.total) * 100)
})

const fetchWarmupStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/bangumi/mapping/warmup/status`)
    if (res.ok) {
      const data = await res.json()
      bgmWarmupStatus.value = data
    }
  } catch (e) {
    console.error('获取预热状态失败', e)
  }
}

const subscribeWarmupProgress = () => {
  if (!_unsubscribeWarmup) {
    _unsubscribeWarmup = onEvent('warmup_progress', (data: any) => {
      bgmWarmupStatus.value = data
      if (!data.running && bgmWarmupLoading.value) {
        bgmWarmupLoading.value = false
        const p = data.progress || {}
        if (p.success !== undefined) {
          message.success(`预热完成: 成功 ${p.success} | 跳过 ${p.skipped || 0} | 失败 ${p.failed || 0}`)
        }
      }
    })
  }
  // 重连后重新拉取预热状态
  if (!_unsubscribeReconnect) {
    _unsubscribeReconnect = onReconnect(() => {
      fetchWarmupStatus().then(() => {
        bgmWarmupLoading.value = bgmWarmupStatus.value.running
      })
    })
  }
}

const unsubscribeWarmupProgress = () => {
  if (_unsubscribeWarmup) {
    _unsubscribeWarmup()
    _unsubscribeWarmup = null
  }
  if (_unsubscribeReconnect) {
    _unsubscribeReconnect()
    _unsubscribeReconnect = null
  }
}

const handleBgmWarmup = () => {
  dialog.warning({
    title: '预热 Subject 缓存',
    content: '将遍历所有 BangumiData 条目预热详情缓存：完结番剧写入永久缓存，所有番剧写入 7 天展示缓存。预热后访问季度番剧表/详情页可直接命中缓存。任务在后台执行，可能耗时较长，可通过实时日志查看进度。是否继续？',
    positiveText: '开始预热',
    negativeText: '取消',
    onPositiveClick: async () => {
      bgmWarmupLoading.value = true
      try {
        const res = await fetch(`${API_BASE}/api/bangumi/mapping/warmup?force=false`, { method: 'POST' })
        const data = await res.json()
        if (res.ok && data.success) {
          message.info('预热任务已在后台启动')
          subscribeWarmupProgress()
        } else {
          message.error(data.message || '启动预热失败')
          bgmWarmupLoading.value = false
        }
      } catch (e) {
        message.error('请求失败')
        bgmWarmupLoading.value = false
      }
    }
  })
}

const {
  loading,
  maintenanceLoading,
  groupedTables,
  groupOrder,
  tableDescriptions,
  categoryMeta,
  getCategory,
  formatSize,
  handleTruncate
} = useMaintenance()

/** 根据分类获取清空按钮类型 */
const getTruncateButtonType = (tableName: string) => {
  const cat = getCategory(tableName)
  if (cat === 'cache') return 'warning'
  if (cat === 'config') return 'error'
  return 'error'
}

/** 核心数据表的二次确认 */
const handleTruncateWithConfirm = (tableName: string) => {
  const cat = getCategory(tableName)
  const meta = categoryMeta[cat]
  if (cat === 'core') {
    dialog.error({
      title: '⚠️ 极度危险操作',
      content: `这是【${meta.label}】类表。${meta.desc}\n\n确认要清空数据库表 [${tableName}] 吗？此操作将永久删除表中所有数据，无法撤销。`,
      positiveText: '我已知晓风险，确认清空',
      negativeText: '取消',
      onPositiveClick: () => handleTruncate(tableName)
    })
  } else if (cat === 'config') {
    dialog.warning({
      title: '危险操作',
      content: `这是【${meta.label}】类表。${meta.desc}\n\n确认要清空数据库表 [${tableName}] 吗？`,
      positiveText: '确认清空',
      negativeText: '取消',
      onPositiveClick: () => handleTruncate(tableName)
    })
  } else {
    dialog.warning({
      title: '确认清空',
      content: `确认要清空数据库表 [${tableName}] 吗？此为缓存表，清空后会自动重建。`,
      positiveText: '确认清空',
      negativeText: '取消',
      onPositiveClick: () => handleTruncate(tableName)
    })
  }
}

onMounted(() => {
  fetchServices()
  subscribeWarmupProgress()
  // 检查是否有正在运行的预热任务（页面刷新后恢复状态）
  fetchWarmupStatus().then(() => {
    if (bgmWarmupStatus.value.running) {
      bgmWarmupLoading.value = true
    }
  })
})

onUnmounted(() => {
  unsubscribeWarmupProgress()
})
</script>

<template>
  <div class="maintenance-manager">
    <!-- 智能记忆管理 -->
    <n-card bordered size="small" class="fingerprint-card" style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>智能记忆管理</span>
        </div>
      </template>
      <n-alert type="info" style="margin-bottom: 16px;">
        智能记忆用于加速重复文件的识别。无效记录（如只有季集模式的简单指纹）可能导致不同剧集误匹配。
      </n-alert>
      <n-space>
        <n-button type="info" secondary :loading="fingerprintLoading" @click="cleanupInvalidFingerprints">
          智能清理无效记忆
        </n-button>
        <n-button type="warning" secondary :loading="fingerprintLoading" @click="clearFingerprints">
          清空全部记忆
        </n-button>
      </n-space>
    </n-card>

    <!-- Emby 索引同步 -->
    <n-card bordered size="small" class="sync-card" style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>Emby 索引同步</span>
        </div>
      </template>
      <n-alert type="info" style="margin-bottom: 16px;">
        同步 Emby 库索引以加速 TMDB ID 查询。建议在 Emby 媒体库有较大变动后手动触发一次同步。
      </n-alert>
      <div class="sync-status-row">
        <div class="sync-stats">
          <n-statistic label="当前条目数" :value="parseCount(embyService?.description) ?? '—'" />
          <n-statistic label="上次同步" :value="formatTime(embyService?.last_run ?? null)" />
          <n-statistic label="下次同步" :value="formatTime(embyService?.next_run ?? null)" />
        </div>
        <n-button type="primary" :loading="embySyncLoading" @click="handleEmbySync">
          立即同步
        </n-button>
      </div>
    </n-card>

    <!-- BangumiData 同步 -->
    <n-card bordered size="small" class="sync-card" style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>BangumiData 同步</span>
        </div>
      </template>
      <n-alert type="info" style="margin-bottom: 16px;">
        同步 BangumiData 条目表用于番剧识别。数据源为 bangumi-data 项目，包含 Bangumi ID 到 TMDB/MAL/AniList/AniDB 的映射。
      </n-alert>
      <div class="sync-status-row">
        <div class="sync-stats">
          <n-statistic label="当前条目数" :value="parseCount(bgmService?.description) ?? '—'" />
          <n-statistic label="上次同步" :value="formatTime(bgmService?.last_run ?? null)" />
          <n-statistic label="下次同步" :value="formatTime(bgmService?.next_run ?? null)" />
        </div>
        <n-space>
          <n-button type="primary" :loading="bgmSyncLoading" :disabled="bgmWarmupLoading" @click="handleBgmSync">
            立即同步
          </n-button>
          <n-button type="info" secondary :loading="bgmWarmupLoading" :disabled="bgmSyncLoading" @click="handleBgmWarmup">
            预热 Subject 缓存
          </n-button>
        </n-space>
      </div>

      <!-- 预热进度 -->
      <div v-if="bgmWarmupLoading || (!bgmWarmupStatus.running && bgmWarmupStatus.progress?.total)" class="warmup-progress">
        <div class="warmup-header">
          <span class="warmup-label">Subject 缓存预热</span>
          <span class="warmup-stats" v-if="bgmWarmupStatus.progress?.total">
            {{ bgmWarmupStatus.progress.done }} / {{ bgmWarmupStatus.progress.total }}
            （成功 {{ bgmWarmupStatus.progress.success }} | 跳过 {{ bgmWarmupStatus.progress.skipped || 0 }} | 失败 {{ bgmWarmupStatus.progress.failed || 0 }}）
          </span>
        </div>
        <n-progress
          type="line"
          :percentage="warmupPercent"
          :status="bgmWarmupStatus.running ? 'default' : (bgmWarmupStatus.progress?.failed ? 'warning' : 'success')"
          :show-indicator="true"
        />
      </div>
    </n-card>

    <n-alert type="warning" title="危险区域" style="margin-bottom: 20px;">
      以下操作将永久删除数据库表中的所有数据（TRUNCATE）。表已按风险等级分组：<b style="color: #2e7d32">缓存</b>可放心清空，<b style="color: #f57c00">配置</b>需谨慎，<b style="color: #c62828">核心</b>极度危险。
    </n-alert>

    <n-spin :show="loading">
      <div v-for="groupName in groupOrder" :key="groupName" class="schema-group">
        <template v-if="groupedTables[groupName]?.length">
          <div class="group-header">
            <n-icon size="20"><DbIcon /></n-icon>
            <h3>{{ groupName }}</h3>
            <span class="group-count">{{ groupedTables[groupName].length }} 张表</span>
          </div>

          <n-grid x-gap="12" y-gap="12" cols="1 s:2 m:3 l:4" responsive="screen">
            <n-grid-item v-for="table in groupedTables[groupName]" :key="table.name">
              <n-card bordered size="small" class="table-card" :data-app-instance="'maintenance-card'">
                <div class="table-info">
                  <div class="table-name-row">
                    <span class="table-name" :title="table.name">{{ table.name.split('.')[1] }}</span>
                    <span
                      class="category-badge"
                      :style="{ color: categoryMeta[getCategory(table.name)].color, backgroundColor: categoryMeta[getCategory(table.name)].bg }"
                    >
                      {{ categoryMeta[getCategory(table.name)].label }}
                    </span>
                  </div>
                  <div class="table-desc">{{ tableDescriptions[table.name] || '暂无说明' }}</div>
                  <div class="table-stats">
                    <div class="stat-cell">
                      <span class="stat-label">行数</span>
                      <span class="stat-value" :style="{ color: table.count > 0 ? '#f57c00' : '#0288d1' }">{{ table.count }}</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-cell">
                      <span class="stat-label">占用</span>
                      <span class="stat-value stat-size">{{ formatSize(table.size_bytes) }}</span>
                    </div>
                  </div>
                </div>
                <div class="actions">
                  <n-button
                    block
                    secondary
                    :type="getTruncateButtonType(table.name)"
                    size="small"
                    :loading="maintenanceLoading[table.name]"
                    @click="handleTruncateWithConfirm(table.name)"
                  >
                    清空数据
                  </n-button>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.maintenance-manager { width: 100%; }
.fingerprint-card, .sync-card { background: var(--app-surface-card-mixed); }
.card-header { display: flex; align-items: center; gap: 8px; color: var(--n-primary-color); font-weight: 600; }
.schema-group { margin-bottom: 32px; }
.group-header { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  margin-bottom: 16px; 
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border-light);
  color: var(--n-primary-color);
}
.group-header h3 { margin: 0; font-size: 16px; letter-spacing: 1px; }
.group-count {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: normal;
  margin-left: 4px;
}

.table-card {
  height: 100%;
  transition: all var(--transition-normal);
  background: var(--app-surface-card-mixed);
}
.table-card:hover {
  border-color: var(--n-primary-color) !important;
  transform: translateY(-2px);
}
.table-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.table-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.table-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.table-name {
  font-weight: bold;
  font-size: 14px;
  word-break: break-all;
  color: var(--n-primary-color);
}
.category-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  letter-spacing: 0.5px;
}
.table-stats {
  display: flex;
  align-items: stretch;
  gap: 0;
  margin-top: auto;
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg-surface, rgba(0,0,0,0.03));
}
.stat-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6px 4px;
  gap: 2px;
}
.stat-label {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: 0.5px;
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  font-family: var(--code-font, 'JetBrains Mono', monospace);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-size {
  color: var(--n-primary-color);
}
.stat-divider {
  width: 1px;
  background: var(--app-border-light, rgba(0,0,0,0.08));
  flex-shrink: 0;
}
.table-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
}
.actions { margin-top: auto; padding-top: 16px; }

/* 同步卡片状态行 */
.sync-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.sync-stats {
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
}

/* 预热进度 */
.warmup-progress {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}
.warmup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}
.warmup-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--n-primary-color);
}
.warmup-stats {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>
