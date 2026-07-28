<script setup lang="ts">
/**
 * MaintenanceTab — 维护中心
 *
 * 功能: 智能记忆管理/Emby索引同步/BangumiData同步+预热/表清空(分类风险)
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { dataCenterApi, bangumiApi } from '@/api'
import { useNotification, useConfirm, useWebSocket, formatDbSize, formatTime, parseCount } from '@/composables'

const { success, error: showError, info } = useNotification()
const { confirm } = useConfirm()
const { on: onWsEvent, onReconnect } = useWebSocket()

const mtnLoading = ref(false)
const mtnTables = ref<any[]>([])
const mtnFingerprintLoading = ref(false)

// Emby 同步
const embySyncLoading = ref(false)
const services = ref<any[]>([])
const embyService = computed(() => services.value.find((s: any) => s.id === 'emby_index_sync') || null)
const bgmService = computed(() => services.value.find((s: any) => s.id === 'bgm_mapping_sync') || null)

// BangumiData 同步 + 预热
const bgmSyncLoading = ref(false)
const bgmWarmupLoading = ref(false)
const bgmWarmupStatus = ref<any>({ running: false, progress: {} })
const warmupPercent = computed(() => {
  const p = bgmWarmupStatus.value.progress
  if (!p || !p.total) return 0
  return Math.round((p.done / p.total) * 100)
})

// 表分类描述
const tableDescriptions: Record<string, string> = {
  'metadata.tmdb_deep_meta': 'TMDB 深度元数据（海报、剧情、演员等）',
  'metadata.media_title_index': '媒体标题加速索引',
  'metadata.ref_genres': '番剧类型字典',
  'metadata.ref_companies': '动画制作/发行公司资料',
  'metadata.ref_keywords': '番剧特征关键词库',
  'metadata.bgm_archive': 'Bangumi 归档数据',
  'metadata.recognition_corrections': '用户手动指定的识别修正映射',
  'metadata.user_genre_mapping': '用户自定义流派 ID 中文映射',
  'metadata.user_company_mapping': '用户自定义公司 ID 中文映射',
  'metadata.user_keyword_mapping': '用户自定义关键词 ID 中文映射',
  'metadata.user_language_mapping': '用户自定义语言代码中文映射',
  'metadata.user_country_mapping': '用户自定义国家代码中文映射',
  'public.system_logs': '系统操作审计日志',
  'public.feeds': 'RSS 订阅源地址与连接配置',
  'public.feed_items': 'RSS 抓取到的下载条目记录',
  'public.subscriptions': '番剧追剧任务配置',
  'public.subscribed_episodes': '已执行下载的剧集记录',
  'public.organize_history': '文件整理重命名的历史记录',
  'public.series_fingerprint': '智能记忆',
  'public.filter_rules': 'RSS 过滤规则',
  'public.rules': '识别引擎规则',
  'public.secondary_rules': '自动分类规则',
  'public.download_history': '下载器任务执行历史',
  'public.blacklist': '识别排除黑名单',
  'public.tmdb_blocklist': 'TMDB 主动屏蔽列表',
  'public.subscription_templates': '订阅预设模板',
  'public.discover_cache': '发现页临时数据缓存',
  'public.remote_rules': '远程社区规则',
  'public.calendar_subjects': '番剧放送时刻表数据',
  'public.quality_profiles': '下载质量偏好设置',
  'public.strm_tasks': 'STRM 生成任务记录',
  'public.health_check_configs': '健康检查配置',
  'public.users': '系统用户账户',
  'public.sessions': '用户登录会话',
  'public.task_records': '任务中心执行记录',
  'public.file_hashes': '文件哈希记录',
  'public.rss_detect_tasks': 'RSS 探测订阅任务',
  'public.bangumi_data_item': 'Bangumi 数据条目',
  'public.bangumi_raw_cache': 'Bangumi 原始 API 响应缓存',
  'public.emby_media_index': 'Emby 库索引',
}

type TableCategory = 'cache' | 'config' | 'core'
const tableCategories: Record<string, TableCategory> = {
  'metadata.media_title_index': 'cache', 'metadata.bgm_archive': 'cache', 'metadata.ref_genres': 'cache',
  'metadata.ref_companies': 'cache', 'metadata.ref_keywords': 'cache', 'public.discover_cache': 'cache',
  'public.calendar_subjects': 'cache', 'public.emby_media_index': 'cache', 'public.system_logs': 'cache',
  'public.feed_items': 'cache', 'public.download_history': 'cache', 'public.task_records': 'cache',
  'public.organize_history': 'cache', 'public.bangumi_data_item': 'cache', 'public.subscribed_episodes': 'cache',
  'metadata.recognition_corrections': 'config', 'metadata.user_genre_mapping': 'config',
  'metadata.user_company_mapping': 'config', 'metadata.user_keyword_mapping': 'config',
  'metadata.user_language_mapping': 'config', 'metadata.user_country_mapping': 'config',
  'public.feeds': 'config', 'public.filter_rules': 'config', 'public.rules': 'config',
  'public.secondary_rules': 'config', 'public.quality_profiles': 'config', 'public.subscription_templates': 'config',
  'public.blacklist': 'config', 'public.tmdb_blocklist': 'config', 'public.remote_rules': 'config',
  'public.health_check_configs': 'config', 'public.rss_detect_tasks': 'config', 'public.strm_tasks': 'config',
  'public.subscriptions': 'config',
  'metadata.tmdb_deep_meta': 'core', 'public.bangumi_raw_cache': 'core', 'public.series_fingerprint': 'core',
  'public.file_hashes': 'core', 'public.users': 'core', 'public.sessions': 'core',
}

const categoryMeta: Record<TableCategory, { label: string; color: string; bg: string; desc: string }> = {
  cache: { label: '缓存', color: '#2e7d32', bg: 'rgba(46,125,50,0.12)', desc: '可放心清空，清空后会自动重建或重新拉取' },
  config: { label: '配置', color: '#f57c00', bg: 'rgba(245,124,0,0.12)', desc: '清空后需要重新配置，请谨慎操作' },
  core: { label: '核心', color: '#c62828', bg: 'rgba(198,40,40,0.12)', desc: '核心数据，清空后不可恢复，极度危险' },
}

function getCategory(tableName: string): TableCategory { return tableCategories[tableName] || 'core' }

const groupedTables = computed(() => {
  const groups: Record<string, any[]> = { '缓存（可清空）': [], '配置（需谨慎）': [], '核心数据（危险）': [] }
  const groupKey: Record<TableCategory, string> = { cache: '缓存（可清空）', config: '配置（需谨慎）', core: '核心数据（危险）' }
  mtnTables.value.forEach(t => { groups[groupKey[getCategory(t.name)]].push(t) })
  Object.values(groups).forEach(g => g.sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0)))
  return groups
})

const groupOrder = ['缓存（可清空）', '配置（需谨慎）', '核心数据（危险）']

async function fetchMtnTables() {
  mtnLoading.value = true
  try {
    const res = await dataCenterApi.getDbTables()
    mtnTables.value = res?.tables || []
  } catch (e) { showError('获取表列表失败') } finally { mtnLoading.value = false }
}

async function fetchServices() {
  try {
    const data = await dataCenterApi.getServicesStatus() as any
    services.value = data?.services || []
  } catch (e) { /* ignore */ }
}

async function clearFingerprints() {
  const ok = await confirm({ title: '确认清空智能记忆', content: '这将删除所有智能记忆缓存。识别速度可能会暂时变慢，但不会影响已刮削的数据。', confirmColor: 'warning' })
  if (!ok) return
  mtnFingerprintLoading.value = true
  try {
    const data = await dataCenterApi.clearFingerprints() as any
    success(data?.message || '智能记忆已清空')
  } catch (e) { showError('操作失败') } finally { mtnFingerprintLoading.value = false }
}

async function cleanupInvalidFingerprints() {
  const ok = await confirm({ title: '智能清理无效记忆', content: '将清理过于简单、缺乏区分度的指纹记录，保留有效的记忆。' })
  if (!ok) return
  mtnFingerprintLoading.value = true
  try {
    const data = await dataCenterApi.cleanupInvalidFingerprints() as any
    if (data?.status === 'success') success(data.message)
    else showError('清理失败')
  } catch (e) { showError('操作失败') } finally { mtnFingerprintLoading.value = false }
}

async function handleEmbySync() {
  embySyncLoading.value = true
  try {
    const data = await dataCenterApi.syncEmbyIndex() as any
    if (data?.status === 'success') { success(`Emby 索引同步完成，共 ${data.count} 条`); fetchServices() }
    else showError(data?.detail || 'Emby 索引同步失败')
  } catch (e: any) { showError(e?.message || '请求失败') } finally { embySyncLoading.value = false }
}

async function handleBgmSync() {
  bgmSyncLoading.value = true
  try {
    const data = await bangumiApi.syncMapping(true) as any
    if (data?.success) { success(data.message || `BangumiData 同步完成`); fetchServices() }
    else showError(data?.message || data?.detail || 'BangumiData 同步失败')
  } catch (e: any) { showError(e?.message || '请求失败') } finally { bgmSyncLoading.value = false }
}

async function handleBgmWarmup() {
  const ok = await confirm({ title: '预热 Subject 缓存', content: '将遍历所有 BangumiData 条目预热详情缓存。任务在后台执行，可能耗时较长。是否继续？' })
  if (!ok) return
  bgmWarmupLoading.value = true
  try {
    const data = await bangumiApi.warmup(false) as any
    if (data?.success) info('预热任务已在后台启动')
    else { showError(data?.message || '启动预热失败'); bgmWarmupLoading.value = false }
  } catch (e) { showError('请求失败'); bgmWarmupLoading.value = false }
}

async function fetchWarmupStatus() {
  try { bgmWarmupStatus.value = await bangumiApi.getWarmupStatus() } catch (e) { /* ignore */ }
}

// WS 预热进度
let wsUnsubWarmup: (() => void) | null = null
let wsUnsubReconnect: (() => void) | null = null

function subscribeWarmupProgress() {
  if (!wsUnsubWarmup) {
    wsUnsubWarmup = onWsEvent('warmup_progress', (data: any) => {
      bgmWarmupStatus.value = data
      if (!data.running && bgmWarmupLoading.value) {
        bgmWarmupLoading.value = false
        const p = data.progress || {}
        if (p.success !== undefined) success(`预热完成: 成功 ${p.success} | 跳过 ${p.skipped || 0} | 失败 ${p.failed || 0}`)
      }
    })
  }
  if (!wsUnsubReconnect) {
    wsUnsubReconnect = onReconnect(() => { fetchWarmupStatus().then(() => { bgmWarmupLoading.value = bgmWarmupStatus.value.running }) })
  }
}

function unsubscribeWarmupProgress() {
  if (wsUnsubWarmup) { wsUnsubWarmup(); wsUnsubWarmup = null }
  if (wsUnsubReconnect) { wsUnsubReconnect(); wsUnsubReconnect = null }
}

async function handleMtnTruncate(tableName: string) {
  const cat = getCategory(tableName)
  const meta = categoryMeta[cat]
  if (cat === 'core') {
    const ok = await confirm({ title: '⚠️ 极度危险操作', content: `这是【${meta.label}】类表。${meta.desc}\n\n确认要清空数据库表 [${tableName}] 吗？此操作将永久删除表中所有数据，无法撤销。`, confirmColor: 'error' })
    if (!ok) return
  } else if (cat === 'config') {
    const ok = await confirm({ title: '危险操作', content: `这是【${meta.label}】类表。${meta.desc}\n\n确认要清空数据库表 [${tableName}] 吗？`, confirmColor: 'warning' })
    if (!ok) return
  } else {
    const ok = await confirm({ title: '确认清空', content: `确认要清空数据库表 [${tableName}] 吗？此为缓存表，清空后会自动重建。`, confirmColor: 'warning' })
    if (!ok) return
  }
  try { await dataCenterApi.truncateDbTable(tableName); success('清理成功'); fetchMtnTables() } catch (e) { showError('清理失败') }
}

function getTruncateBtnColor(tableName: string): string {
  const cat = getCategory(tableName)
  if (cat === 'cache') return 'warning'
  return 'error'
}

onMounted(() => {
  fetchServices()
  fetchMtnTables()
  subscribeWarmupProgress()
  fetchWarmupStatus().then(() => { if (bgmWarmupStatus.value.running) bgmWarmupLoading.value = true })
})

onUnmounted(() => {
  unsubscribeWarmupProgress()
})
</script>

<template>
  <!-- 智能记忆管理 -->
  <v-card class="glass-card pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-bold text-primary mb-3">智能记忆管理</div>
    <v-alert type="info" density="compact" variant="tonal" class="mb-3">智能记忆用于加速重复文件的识别。无效记录可能导致不同剧集误匹配。</v-alert>
    <div class="d-flex ga-2">
      <v-btn variant="tonal" color="info" prepend-icon="mdi-broom" :loading="mtnFingerprintLoading" @click="cleanupInvalidFingerprints">智能清理无效记忆</v-btn>
      <v-btn variant="tonal" color="warning" prepend-icon="mdi-delete-sweep-outline" :loading="mtnFingerprintLoading" @click="clearFingerprints">清空全部记忆</v-btn>
    </div>
  </v-card>

  <!-- Emby 索引同步 -->
  <v-card class="glass-card pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-bold text-primary mb-3">Emby 索引同步</div>
    <v-alert type="info" density="compact" variant="tonal" class="mb-3">同步 Emby 库索引以加速 TMDB ID 查询。建议在 Emby 媒体库有较大变动后手动触发一次同步。</v-alert>
    <div class="d-flex align-center justify-space-between flex-wrap ga-3">
      <div class="d-flex ga-6">
        <div><div class="text-caption text-medium-emphasis">当前条目数</div><div class="text-h6 font-weight-bold">{{ parseCount(embyService?.description) ?? '—' }}</div></div>
        <div><div class="text-caption text-medium-emphasis">上次同步</div><div class="text-body-2">{{ formatTime(embyService?.last_run ?? null) }}</div></div>
        <div><div class="text-caption text-medium-emphasis">下次同步</div><div class="text-body-2">{{ formatTime(embyService?.next_run ?? null) }}</div></div>
      </div>
      <v-btn color="primary" variant="flat" prepend-icon="mdi-sync" :loading="embySyncLoading" @click="handleEmbySync">立即同步</v-btn>
    </div>
  </v-card>

  <!-- BangumiData 同步 -->
  <v-card class="glass-card pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-bold text-primary mb-3">BangumiData 同步</div>
    <v-alert type="info" density="compact" variant="tonal" class="mb-3">同步 BangumiData 条目表用于番剧识别。数据源为 bangumi-data 项目。</v-alert>
    <div class="d-flex align-center justify-space-between flex-wrap ga-3">
      <div class="d-flex ga-6">
        <div><div class="text-caption text-medium-emphasis">当前条目数</div><div class="text-h6 font-weight-bold">{{ parseCount(bgmService?.description) ?? '—' }}</div></div>
        <div><div class="text-caption text-medium-emphasis">上次同步</div><div class="text-body-2">{{ formatTime(bgmService?.last_run ?? null) }}</div></div>
        <div><div class="text-caption text-medium-emphasis">下次同步</div><div class="text-body-2">{{ formatTime(bgmService?.next_run ?? null) }}</div></div>
      </div>
      <div class="d-flex ga-2">
        <v-btn color="primary" variant="flat" prepend-icon="mdi-sync" :loading="bgmSyncLoading" :disabled="bgmWarmupLoading" @click="handleBgmSync">立即同步</v-btn>
        <v-btn variant="tonal" color="info" prepend-icon="mdi-fire" :loading="bgmWarmupLoading" :disabled="bgmSyncLoading" @click="handleBgmWarmup">预热 Subject 缓存</v-btn>
      </div>
    </div>
    <!-- 预热进度 -->
    <div v-if="bgmWarmupLoading || (!bgmWarmupStatus.running && bgmWarmupStatus.progress?.total)" class="mt-4 pa-3 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.04)">
      <div class="d-flex justify-space-between align-center mb-2">
        <span class="text-body-2 font-weight-medium text-primary">Subject 缓存预热</span>
        <span v-if="bgmWarmupStatus.progress?.total" class="text-caption text-medium-emphasis">
          {{ bgmWarmupStatus.progress.done }} / {{ bgmWarmupStatus.progress.total }}（成功 {{ bgmWarmupStatus.progress.success }} | 跳过 {{ bgmWarmupStatus.progress.skipped || 0 }} | 失败 {{ bgmWarmupStatus.progress.failed || 0 }}）
        </span>
      </div>
      <v-progress-linear :model-value="warmupPercent" :color="bgmWarmupStatus.running ? 'primary' : 'success'" height="6" rounded />
    </div>
  </v-card>

  <!-- 数据库表维护 -->
  <v-alert type="warning" density="compact" variant="tonal" class="mb-4">
    以下操作将永久删除数据库表中的所有数据（TRUNCATE）。表已按风险等级分组：<b style="color:#2e7d32">缓存</b>可放心清空，<b style="color:#f57c00">配置</b>需谨慎，<b style="color:#c62828">核心</b>极度危险。
  </v-alert>

  <v-skeleton-loader v-if="mtnLoading" type="card@3" />
  <template v-else>
    <div v-for="groupName in groupOrder" :key="groupName" class="mb-6">
      <template v-if="groupedTables[groupName]?.length">
        <div class="text-subtitle-1 font-weight-bold text-primary mb-3 d-flex align-center ga-2">
          <v-icon size="20">mdi-database-outline</v-icon>
          {{ groupName }}
          <span class="text-caption text-medium-emphasis font-weight-normal">({{ groupedTables[groupName].length }} 张表)</span>
        </div>
        <v-row>
          <v-col v-for="table in groupedTables[groupName]" :key="table.name" cols="12" sm="6" md="4" lg="3">
            <v-card class="glass-card pa-3" style="height:100%;display:flex;flex-direction:column">
              <div class="d-flex align-center justify-space-between mb-2">
                <span class="font-weight-bold text-primary text-truncate">{{ table.name.split('.')[1] }}</span>
                <span class="category-badge" :style="{ color: categoryMeta[getCategory(table.name)].color, backgroundColor: categoryMeta[getCategory(table.name)].bg }">{{ categoryMeta[getCategory(table.name)].label }}</span>
              </div>
              <div class="text-caption text-medium-emphasis mb-2" style="flex:1">{{ tableDescriptions[table.name] || '暂无说明' }}</div>
              <div class="d-flex ga-3 mb-2">
                <div><span class="text-caption text-medium-emphasis">行数</span><div class="font-weight-bold" :style="{ color: table.count > 0 ? '#f57c00' : '#0288d1' }">{{ table.count }}</div></div>
                <div><span class="text-caption text-medium-emphasis">占用</span><div class="font-weight-bold text-primary">{{ formatDbSize(table.size_bytes) }}</div></div>
              </div>
              <v-btn block :color="getTruncateBtnColor(table.name)" variant="tonal" size="small" prepend-icon="mdi-delete-outline" @click="handleMtnTruncate(table.name)">清空数据</v-btn>
            </v-card>
          </v-col>
        </v-row>
      </template>
    </div>
  </template>
</template>


