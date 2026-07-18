<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  NCard, NButton, NSpace, NIcon, NAlert, NGrid, NGridItem, NTag, NSpin, NStatistic, useDialog, useMessage
} from 'naive-ui'
import {
  ServerIcon as DbIcon
} from '@heroicons/vue/24/outline'
import { useMaintenance } from '../../composables/components/useMaintenance'

const dialog = useDialog()
const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const fingerprintLoading = ref(false)

const handleTruncateWithConfirm = (tableName: string) => {
  dialog.error({
    title: '危险操作',
    content: `确认要清空数据库表 [${tableName}] 吗？此操作将永久删除表中所有数据，无法撤销。`,
    positiveText: '确认清空',
    negativeText: '取消',
    onPositiveClick: () => handleTruncate(tableName)
  })
}

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

const {
  loading,
  maintenanceLoading,
  groupedTables,
  tableDescriptions,
  handleTruncate
} = useMaintenance()

const getTagStyle = (count: number) => {
  return count > 0
    ? { color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' }
    : { color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }
}

onMounted(() => {
  fetchServices()
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
        <n-button type="primary" :loading="bgmSyncLoading" @click="handleBgmSync">
          立即同步
        </n-button>
      </div>
    </n-card>

    <n-alert type="warning" title="危险区域" style="margin-bottom: 20px;">
      以下操作将永久删除数据库表中的所有数据（TRUNCATE）。执行后无法撤销，请务必确认操作目标。
    </n-alert>

    <n-spin :show="loading">
      <div v-for="(groupTables, schema) in groupedTables" :key="schema" class="schema-group">
        <div class="group-header">
          <n-icon size="20"><DbIcon /></n-icon>
          <h3>命名空间: {{ schema.toUpperCase() }}</h3>
        </div>
        
        <n-grid x-gap="12" y-gap="12" cols="1 s:2 m:3 l:4" responsive="screen">
          <n-grid-item v-for="table in groupTables" :key="table.name">
            <n-card bordered size="small" class="table-card" :data-app-instance="'maintenance-card'">
              <div class="table-info">
                <div class="table-name" :title="table.name">{{ table.name.split('.')[1] }}</div>
                <div class="table-desc">{{ tableDescriptions[table.name] || '暂无说明' }}</div>
                <n-tag size="small" round :bordered="false" :style="getTagStyle(table.count)" style="align-self: flex-start;">
                  {{ table.count }} 行数据
                </n-tag>
              </div>
              <div class="actions">
                <n-button 
                  block 
                  secondary 
                  type="error" 
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
.table-name {
  font-weight: bold;
  font-size: 14px;
  word-break: break-all;
  color: var(--n-primary-color);
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
</style>
