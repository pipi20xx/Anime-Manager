<script setup lang="ts">
/**
 * MaintenanceTab — 维护中心
 *
 * 功能: 表清空(分类风险)
 * 智能记忆/Emby索引同步/BangumiData同步等操作已迁移至「任务计划」页统一管理
 */
import { ref, computed, onMounted } from 'vue'
import { dataCenterApi } from '@/api'
import { useNotification, useConfirm, formatDbSize } from '@/composables'

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const mtnLoading = ref(false)
const mtnTables = ref<any[]>([])

// --- 定向清理智能记忆 ---
const fpDialog = ref(false)
const fpTmdbId = ref('')
const fpMediaType = ref('')  // '' = 全部类型
const fpSearching = ref(false)
const fpDeleting = ref(false)
const fpSearched = ref(false)   // 是否已按当前条件查询过
const fpResults = ref<any[]>([])

const fpTypeItems = [
  { title: '全部类型', value: '' },
  { title: '剧集 (tv)', value: 'tv' },
  { title: '电影 (movie)', value: 'movie' },
]

const fpQueryKey = computed(() => `${fpTmdbId.value.trim()}|${fpMediaType.value}`)
// 防止结果与当前输入条件脱节：修改输入后需重新查询才能删除
const fpResultsStale = ref(false)

function openFpDialog() {
  fpDialog.value = true
  fpTmdbId.value = ''
  fpMediaType.value = ''
  fpResults.value = []
  fpSearched.value = false
  fpResultsStale.value = false
}

async function searchFingerprints() {
  const id = fpTmdbId.value.trim()
  if (!id) { showError('请先输入 TMDB ID'); return }
  fpSearching.value = true
  try {
    const res = await dataCenterApi.searchFingerprintsByTmdb({ tmdb_id: id, media_type: fpMediaType.value || undefined })
    fpResults.value = res?.items || []
    fpSearched.value = true
    fpResultsStale.value = false
    if (fpResults.value.length === 0) showError('未找到匹配的记忆记录')
  } catch (e) { showError('查询失败') } finally { fpSearching.value = false }
}

async function deleteFingerprints() {
  const id = fpTmdbId.value.trim()
  if (!id || fpResultsStale.value) return
  const typeLabel = fpTypeItems.find(i => i.value === fpMediaType.value)?.title || '全部类型'
  const ok = await confirm({
    title: '确认删除记忆',
    content: `将删除 TMDB ${typeLabel}:${id} 对应的 ${fpResults.value.length} 条智能记忆记录，删除后这些条目下次识别会重新进行云端搜索。此操作无法撤销。`,
    confirmColor: 'error',
  })
  if (!ok) return
  fpDeleting.value = true
  try {
    const res = await dataCenterApi.deleteFingerprintsByTmdb({ tmdb_id: id, media_type: fpMediaType.value || undefined })
    success(res?.message || `已删除 ${res?.deleted_count ?? 0} 条记忆记录`)
    fpResults.value = []
    fpSearched.value = false
  } catch (e) { showError('删除失败') } finally { fpDeleting.value = false }
}

function onFpInputChanged() { fpResultsStale.value = fpSearched.value }

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
  'public.rapid_upload_retry': 'CD2 秒传重试队列：秒传未命中的文件按间隔自动重试，可在整理管理-秒传管理中查看和维护',
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
  'public.bgm_user_mark': 'Bangumi 用户手动标记（季度番剧表"已整理"等）',
  'public.bangumi_raw_cache': 'Bangumi 原始 API 响应缓存',
  'public.emby_media_index': 'Emby 库索引',
  'public.custom_scheduled_jobs': '自定义定时任务（任务计划页创建的 cron/间隔任务）',
  'public.notification_records': '通知中心发送记录（Telegram 等渠道的消息渲染留档）',
  'public.webhook_events': '联动记录中心（Webhook 事件台账：CD2 联动成败、重放记录，并引用 task_records 保存全链路日志）',
}

type TableCategory = 'cache' | 'config' | 'core'
const tableCategories: Record<string, TableCategory> = {
  'metadata.media_title_index': 'cache', 'metadata.bgm_archive': 'cache', 'metadata.ref_genres': 'cache',
  'metadata.ref_companies': 'cache', 'metadata.ref_keywords': 'cache', 'public.discover_cache': 'cache',
  'public.calendar_subjects': 'cache', 'public.emby_media_index': 'cache', 'public.system_logs': 'cache',
  'public.feed_items': 'cache', 'public.download_history': 'cache', 'public.task_records': 'cache',
  'public.organize_history': 'cache', 'public.bangumi_data_item': 'cache', 'public.subscribed_episodes': 'cache',
  'public.rapid_upload_retry': 'cache', 'public.notification_records': 'cache', 'public.webhook_events': 'cache',
  'public.custom_scheduled_jobs': 'config',
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
  fetchMtnTables()
})
</script>

<template>
  <!-- 定向清理智能记忆 -->
  <v-card class="glass-card mb-4">
    <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
      <v-icon color="primary" size="20">mdi-brain-delete-outline</v-icon>
      <span class="text-subtitle-1 font-weight-bold">定向清理智能记忆</span>
    </v-card-title>
    <v-divider />
    <v-card-text class="pa-4">
      <div class="text-caption text-medium-emphasis">
        当某个 TMDB 条目已在 TMDB 上被删除/失效时，其智能记忆记录实际上已无用。
        输入 TMDB ID 和类型可定向查询并删除对应的记忆（指纹）记录，无需在记忆库中逐条查找。
      </div>
      <v-btn class="mt-3" color="error" variant="tonal" prepend-icon="mdi-target" @click="openFpDialog">定向清理</v-btn>
    </v-card-text>
  </v-card>

  <!-- 定向清理智能记忆弹窗 -->
  <v-dialog v-model="fpDialog" max-width="680" scrollable>
    <v-card class="glass-card">
      <v-card-title class="d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-brain-delete-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">定向清理智能记忆</span>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-row dense class="mt-1">
          <v-col cols="12" sm="7">
            <v-text-field
              v-model="fpTmdbId"
              label="TMDB ID"
              variant="outlined"
              density="compact"
              placeholder="如 123456"
              hide-details
              :disabled="fpDeleting"
              @update:model-value="onFpInputChanged"
              @keyup.enter="searchFingerprints"
            />
          </v-col>
          <v-col cols="12" sm="5">
            <v-select
              v-model="fpMediaType"
              :items="fpTypeItems"
              label="类型"
              variant="outlined"
              density="compact"
              hide-details
              :disabled="fpDeleting"
              @update:model-value="onFpInputChanged"
            />
          </v-col>
        </v-row>

        <div class="d-flex ga-3 mt-3">
          <v-btn color="primary" variant="tonal" :loading="fpSearching" :disabled="!fpTmdbId.trim() || fpDeleting" prepend-icon="mdi-magnify" @click="searchFingerprints">查询匹配记录</v-btn>
          <v-spacer />
          <v-btn
            color="error"
            :loading="fpDeleting"
            :disabled="!fpSearched || fpResultsStale || fpResults.length === 0"
            prepend-icon="mdi-delete-outline"
            @click="deleteFingerprints"
          >删除匹配记录 ({{ fpResults.length }})</v-btn>
        </div>

        <v-alert v-if="fpSearched && fpResults.length === 0" type="info" density="compact" variant="tonal" class="mt-4">
          没有匹配的记忆记录
        </v-alert>

        <template v-if="fpResults.length > 0">
          <div class="text-caption text-medium-emphasis mt-4 mb-1">匹配到 {{ fpResults.length }} 条记录：</div>
          <v-list density="compact" class="fp-result-list">
            <v-list-item v-for="item in fpResults" :key="item.fingerprint">
              <template #prepend>
                <v-icon size="18" color="primary">mdi-fingerprint</v-icon>
              </template>
              <v-tooltip activator="parent" location="top" max-width="640" scroll-strategy="close">
                <span class="fp-tooltip-text">{{ item.fingerprint }}</span>
              </v-tooltip>
              <template #title>
                <span class="text-body-2 fp-ellipsis">{{ item.fingerprint }}</span>
              </template>
              <template #subtitle>
                <span class="text-caption fp-ellipsis" :title="`${item.title || '未知标题'} · ${item.type === 'movie' ? '电影' : '剧集'} · ID ${item.tmdb_id}`">
                  {{ item.title || '未知标题' }} · {{ item.type === 'movie' ? '电影' : '剧集' }} · ID {{ item.tmdb_id }}
                </span>
              </template>
            </v-list-item>
          </v-list>
        </template>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-3">
        <v-spacer />
        <v-btn variant="text" :disabled="fpDeleting" @click="fpDialog = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

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

<style scoped>
.fp-result-list {
  max-height: 320px;
  overflow-y: auto;
}

.fp-ellipsis {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style>
/* tooltip 内容不受 scoped 限制（渲染在全局 overlay 层），超长指纹需可换行查看 */
.fp-tooltip-text {
  display: block;
  white-space: normal;
  word-break: break-all;
  line-height: 1.6;
}
</style>


