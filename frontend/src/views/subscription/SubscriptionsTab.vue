<script setup lang="ts">
/**
 * SubscriptionsTab — 追剧订阅
 *
 * 对标旧前端 SubscriptionManager:
 * - 海报卡片展示 + 状态指示
 * - 清空所有订阅 / Bangumi一键订阅 / 洗版规则 / 预设管理
 * - 更多操作: 搜寻补全 / 推送记录 / TMDB/Bangumi 跳转 / 删除
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { subscriptionApi, bangumiApi, clientsApi, api } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'
import SubDetailModal from './SubDetailModal.vue'
import SubEditModal from './SubEditModal.vue'
import JackettFillModal from './JackettFillModal.vue'
import PriorityRuleModal from './PriorityRuleModal.vue'
import SubscriptionTemplateModal from './SubscriptionTemplateModal.vue'
import RssDetectModal from './RssDetectModal.vue'

defineOptions({ name: 'SubscriptionsTab' })

const router = useRouter()
const navStore = useNavigationStore()
const { success, error: showError, warning, info: showInfo } = useNotification()
const { confirm } = useConfirm()

const subscriptions = ref<any[]>([])
const loading = ref(false)
const clients = ref<any[]>([])

// 弹窗状态
const showEditModal = ref(false)
const showDetailModal = ref(false)
const showFillModal = ref(false)
const showPriorityModal = ref(false)
const showTemplateModal = ref(false)
const showRssDetectModal = ref(false)
const currentSub = ref<any>(null)
const isNewSub = ref(false)

// 洗版策略 & 预设
const profiles = ref<any[]>([])
const templates = ref<any[]>([])

// Bangumi 一键订阅
const showQuickSubModal = ref(false)
const weeklyData = ref<any[]>([])
const quickSubLoading = ref(false)
const quickSubSubmitting = ref(false)
const selectedQuickIds = ref<number[]>([])
const quickSubTemplate = ref<number | null>(null)
const manualBgmId = ref('')
const manualItems = ref<any[]>([])

const clientNameMap = computed(() => {
  const map: Record<string, string> = {}
  clients.value.forEach(c => { map[c.id] = c.name })
  return map
})

async function fetchSubscriptions() {
  loading.value = true
  try {
    subscriptions.value = (await subscriptionApi.getSubscriptions()) || []
  } catch (e) { showError('加载订阅失败') }
  finally { loading.value = false }
}

async function fetchClients() {
  try { clients.value = (await clientsApi.getClients()) || [] } catch { /* */ }
}

async function fetchProfiles() {
  try {
    const data = await api.get<any[]>('/api/priority/profiles')
    profiles.value = data || []
  } catch { /* */ }
}

async function fetchTemplates() {
  try {
    const data = await subscriptionApi.getTemplates()
    templates.value = data || []
  } catch { /* */ }
}

function getUpgradeStatus(sub: any) {
  if (!sub.quality_profile_id) return null
  const p = profiles.value.find((x: any) => x.id === sub.quality_profile_id)
  if (!p) return null
  return { name: p.name, allowed: p.upgrade_allowed }
}

// --- CRUD ---
function openAddSub() {
  currentSub.value = null
  isNewSub.value = true
  showEditModal.value = true
}

function openEditSub(sub: any) {
  currentSub.value = sub
  isNewSub.value = false
  showEditModal.value = true
}

async function handleSaveSub(data: any) {
  try {
    await subscriptionApi.saveSubscription(data)
    success('订阅已保存')
    showEditModal.value = false
    fetchSubscriptions()
  } catch (e) { showError('保存失败') }
}

async function deleteSubscription(sub: any) {
  const ok = await confirm({ title: '确认删除', content: `确定要删除「${sub.title}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.deleteSubscription(sub.id)
    success('订阅已删除')
    fetchSubscriptions()
  } catch (e) { showError('删除失败') }
}

async function clearAllSubscriptions() {
  const ok = await confirm({ title: '确认清空', content: '该操作将彻底移除所有订阅任务，确定要继续吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.clearAllSubscriptions()
    success('已在后台启动清空任务')
    fetchSubscriptions()
  } catch (e) { showError('操作失败') }
}

function openDetail(sub: any) {
  currentSub.value = sub
  showDetailModal.value = true
}

function openFill(sub: any) {
  currentSub.value = sub
  showFillModal.value = true
}

// --- 外部跳转 ---
function goToExternal(sub: any, type: 'tmdb' | 'bgm') {
  if (type === 'tmdb' && sub.tmdb_id) {
    const url = sub.media_type === 'movie'
      ? `https://www.themoviedb.org/movie/${sub.tmdb_id}`
      : `https://www.themoviedb.org/tv/${sub.tmdb_id}`
    window.open(url, '_blank')
  } else if (type === 'bgm' && sub.bangumi_id) {
    window.open(`https://bangumi.tv/subject/${sub.bangumi_id}`, '_blank')
  }
}

// --- Bangumi 一键订阅 ---
async function openQuickSub() {
  showQuickSubModal.value = true
  selectedQuickIds.value = []
  manualItems.value = []
  manualBgmId.value = ''
  await fetchWeeklyData()
}

async function fetchWeeklyData() {
  quickSubLoading.value = true
  try {
    const [calData, subData] = await Promise.all([
      bangumiApi.getCalendar(),
      subscriptionApi.getSubscriptions(),
    ])
    const rawDays = calData?.data || []
    // 标记已订阅状态
    const subs = (subData as any[]) || []
    weeklyData.value = rawDays.map((day: any) => ({
      ...day,
      items: (day.items || []).map((item: any) => ({
        ...item,
        isSubscribed: subs.some((s: any) => String(s.bangumi_id) === String(item.id)),
      })),
    }))
    // 设置默认模板
    const defaultTmpl = templates.value.find((t: any) => t.is_default)
    if (defaultTmpl) quickSubTemplate.value = defaultTmpl.id
    else if (templates.value.length > 0 && !quickSubTemplate.value) quickSubTemplate.value = templates.value[0].id
  } catch { showError('加载放送表失败') }
  finally { quickSubLoading.value = false }
}

async function handleBatchSubscribe() {
  if (selectedQuickIds.value.length === 0) { warning('请选择要订阅的番剧'); return }
  quickSubSubmitting.value = true
  try {
    await bangumiApi.batchSubscribe({
      subject_ids: selectedQuickIds.value,
      template_id: quickSubTemplate.value,
    })
    success(`已订阅 ${selectedQuickIds.value.length} 个番剧`)
    showQuickSubModal.value = false
    fetchSubscriptions()
  } catch (e) { showError('批量订阅失败') }
  finally { quickSubSubmitting.value = false }
}

function goToBangumiDetail(id: number | string) {
  navStore.openBangumiDetail(id)
}

function toggleQuickId(id: number) {
  const idx = selectedQuickIds.value.indexOf(id)
  if (idx >= 0) selectedQuickIds.value.splice(idx, 1)
  else selectedQuickIds.value.push(id)
}

function selectAll() {
  const allUnsubbed: number[] = []
  for (const day of weeklyData.value) {
    for (const item of (day.items || [])) {
      if (!item.isSubscribed) allUnsubbed.push(item.id)
    }
  }
  for (const item of manualItems.value) {
    if (!item.isSubscribed && !allUnsubbed.includes(item.id)) allUnsubbed.push(item.id)
  }
  selectedQuickIds.value = allUnsubbed
}

async function addManualItem() {
  if (!manualBgmId.value) return
  const id = parseInt(manualBgmId.value)
  if (isNaN(id)) { warning('请输入有效的 Bangumi ID'); return }
  // 检查是否已添加
  if (manualItems.value.some(i => i.id === id)) { warning('该条目已添加'); return }
  try {
    const data = await bangumiApi.getSubject(id)
    const isSubbed = subscriptions.value.some((s: any) => s.bangumi_id && String(s.bangumi_id) === String(id))
    manualItems.value.push({
      id,
      title: data.name_cn || data.name || `BGM-${id}`,
      image: data.images?.common || data.image,
      isSubscribed: isSubbed,
    })
    if (!isSubbed && !selectedQuickIds.value.includes(id)) selectedQuickIds.value.push(id)
    manualBgmId.value = ''
  } catch { showError('获取 Bangumi 条目信息失败') }
}

function removeManualItem(id: number) {
  manualItems.value = manualItems.value.filter(i => i.id !== id)
  const idx = selectedQuickIds.value.indexOf(id)
  if (idx >= 0) selectedQuickIds.value.splice(idx, 1)
}

onMounted(() => {
  fetchSubscriptions()
  fetchClients()
  fetchProfiles()
  fetchTemplates()
})

defineExpose({ fetchSubscriptions })
</script>

<template>
  <div>
    <!-- 操作栏 -->
    <div class="d-flex justify-end mb-4 ga-2 flex-wrap">
      <v-btn variant="tonal" color="error" size="small" prepend-icon="mdi-delete-sweep-outline" @click="clearAllSubscriptions">清空所有订阅</v-btn>
      <v-btn variant="tonal" color="info" size="small" prepend-icon="mdi-star-outline" @click="openQuickSub">Bangumi一键订阅</v-btn>
      <v-btn variant="tonal" color="info" size="small" prepend-icon="mdi-radar" @click="showRssDetectModal = true">自动RSS订阅管理</v-btn>
      <v-btn variant="tonal" color="info" size="small" prepend-icon="mdi-cog-outline" @click="showPriorityModal = true">洗版规则</v-btn>
      <v-btn variant="tonal" color="info" size="small" prepend-icon="mdi-file-document-outline" @click="showTemplateModal = true">订阅预设管理</v-btn>
      <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-plus" @click="openAddSub">添加新订阅</v-btn>
    </div>

    <v-skeleton-loader v-if="loading" type="card@4" />

    <v-row v-else-if="subscriptions.length > 0">
      <v-col v-for="sub in subscriptions" :key="sub.id" cols="6" sm="6" md="3" lg="3" xl="2" class="d-flex">
        <v-card class="glass-card hover-lift sub-card w-100" @click="openEditSub(sub)">
          <!-- 海报 -->
          <div class="sub-poster-box">
            <v-img
              v-if="sub.poster_path"
              :src="getImg(sub.poster_path)"
              cover
              class="rounded-t"
            />
            <div v-else class="sub-poster-placeholder d-flex align-center justify-center">
              <v-icon size="40" color="grey">mdi-television-classic</v-icon>
            </div>
            <!-- 类型/集数标识 -->
            <div class="sub-type-badge">
              <template v-if="sub.media_type === 'tv'">TV</template>
              <template v-else>电影</template>
            </div>
            <!-- 集数范围标识 -->
            <div v-if="sub.media_type === 'tv'" class="sub-ep-badge">
              S{{ sub.season === 0 ? 'All' : sub.season }} · E{{ sub.start_episode || 1 }}{{ sub.end_episode > 0 ? '-' + sub.end_episode : '+' }}
            </div>
            <!-- 启用状态角标 -->
            <div class="sub-status-badge" :class="sub.enabled !== false ? 'active' : 'inactive'">
              {{ sub.enabled !== false ? '启用' : '未启用' }}
            </div>
            <!-- 已推送角标 -->
            <div v-if="sub.media_type === 'tv'" class="sub-pushed-badge">
              <v-icon size="12" class="mr-1">mdi-send-outline</v-icon>{{ sub.pushed_count ?? 0 }}/{{ sub.end_episode > 0 ? sub.end_episode - (sub.start_episode || 1) + 1 : '?' }}
            </div>
            <div v-else-if="sub.pushed_count > 0" class="sub-pushed-badge">
              <v-icon size="12" class="mr-1">mdi-check-circle-outline</v-icon>已推送
            </div>
            <!-- 洗版标签 -->
            <div v-if="getUpgradeStatus(sub)" class="sub-upgrade-tag">
              <v-icon size="12" :color="getUpgradeStatus(sub)?.allowed ? 'primary' : 'grey'">mdi-arrow-up-bold</v-icon>
            </div>
          </div>

          <!-- 信息区 -->
          <div class="pa-2">
            <div class="d-flex align-center">
              <div class="text-body-2 font-weight-bold text-truncate flex-grow-1" :title="sub.title">{{ sub.title }}</div>
              <!-- 更多菜单 -->
              <v-menu>
                <template #activator="{ props: menuProps }">
                  <v-btn icon="mdi-dots-vertical" size="x-small" variant="text" v-bind="menuProps" @click.stop class="flex-shrink-0" />
                </template>
                <v-list density="compact" min-width="160">
                  <v-list-item prepend-icon="mdi-magnify" @click.stop="openFill(sub)">搜寻补全缺失集数</v-list-item>
                  <v-list-item prepend-icon="mdi-history" @click.stop="openDetail(sub)">查看推送记录</v-list-item>
                  <v-list-item prepend-icon="mdi-open-in-new" @click.stop="goToExternal(sub, 'tmdb')">在 TMDB 中查看</v-list-item>
                  <v-list-item v-if="sub.bangumi_id" prepend-icon="mdi-open-in-new" @click.stop="goToExternal(sub, 'bgm')">在 Bangumi 中查看</v-list-item>
                  <v-divider />
                  <v-list-item prepend-icon="mdi-delete-outline" base-color="error" @click.stop="deleteSubscription(sub)">删除订阅</v-list-item>
                </v-list>
              </v-menu>
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-rss-off</v-icon>
      <div class="text-h6 font-weight-medium">暂无订阅</div>
      <div class="text-body-2 text-medium-emphasis mt-2">点击"添加新订阅"或"Bangumi一键订阅"开始追剧</div>
    </div>

    <!-- 订阅编辑弹窗 -->
    <SubEditModal
      v-model:show="showEditModal"
      :sub-data="currentSub"
      :is-new="isNewSub"
      :clients="clients"
      :templates="templates"
      :profiles="profiles"
      @save="handleSaveSub"
    />

    <!-- 洗版规则弹窗 -->
    <PriorityRuleModal v-model:show="showPriorityModal" />

    <!-- 预设管理弹窗 -->
    <SubscriptionTemplateModal v-model:show="showTemplateModal" />

    <!-- 搜寻补全弹窗 -->
    <JackettFillModal
      v-model:show="showFillModal"
      :sub-id="currentSub?.id"
      :sub-title="currentSub?.title || ''"
      @finish="fetchSubscriptions"
    />

    <!-- 推送记录弹窗 -->
    <SubDetailModal
      v-model:show="showDetailModal"
      :sub="currentSub"
    />

    <!-- 自动RSS订阅管理弹窗 -->
    <RssDetectModal
      v-model:show="showRssDetectModal"
      @finish="fetchSubscriptions"
    />

    <!-- Bangumi 一键订阅弹窗 -->
    <v-dialog v-model="showQuickSubModal" max-width="1000" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="info">mdi-star-outline</v-icon>
          Bangumi 一键订阅
          <div class="text-caption text-medium-emphasis ml-2">快速同步全周放送列表</div>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showQuickSubModal = false" />
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4">
          <!-- 工具栏 -->
          <v-row class="mb-4" dense>
            <v-col cols="12" sm="4">
              <v-select
                v-model="quickSubTemplate"
                label="套用预设"
                :items="templates.map((t: any) => ({ title: t.name, value: t.id }))"
                clearable
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
            <v-col cols="12" sm="5">
              <v-text-field
                v-model="manualBgmId"
                label="手动添加 Bangumi ID"
                placeholder="输入 Bangumi 条目 ID"
                variant="outlined"
                density="compact"
                hide-details
                append-inner-icon="mdi-plus"
                @click:append-inner="addManualItem"
                @keyup.enter="addManualItem"
              />
            </v-col>
            <v-col cols="12" sm="3" class="d-flex align-center ga-2">
              <v-btn variant="tonal" prepend-icon="mdi-select-all" height="40" @click="selectAll">全选</v-btn>
              <v-btn variant="tonal" prepend-icon="mdi-select-off" height="40" @click="selectedQuickIds = []">取消全选</v-btn>
            </v-col>
          </v-row>

          <!-- 手动添加的条目 -->
          <div v-if="manualItems.length > 0" class="mb-4">
            <div class="text-caption text-medium-emphasis mb-2">手动添加</div>
            <v-chip-group multiple column>
              <v-chip
                v-for="item in manualItems"
                :key="'manual-' + item.id"
                :variant="selectedQuickIds.includes(item.id) ? 'flat' : 'outlined'"
                color="primary"
                size="small"
                filter
                closable
                @click="toggleQuickId(item.id)"
                @click:close="removeManualItem(item.id)"
              >
                {{ item.title }}
              </v-chip>
            </v-chip-group>
          </div>

          <v-skeleton-loader v-if="quickSubLoading" type="card@3" />

          <template v-else-if="weeklyData.length > 0">
            <div v-for="day in weeklyData" :key="day.weekday?.id || day.name" class="mb-4">
              <div class="text-subtitle-2 font-weight-bold mb-2 text-primary">
                {{ day.weekday?.cn || day.name }}
                <span v-if="day.is_today" class="text-caption text-info ml-1">今天</span>
              </div>
              <v-chip-group multiple column>
                <v-chip
                  v-for="item in (day.items || [])"
                  :key="item.id"
                  :variant="selectedQuickIds.includes(item.id) ? 'flat' : 'outlined'"
                  color="primary"
                  size="small"
                  filter
                  :disabled="item.isSubscribed"
                  @click="item.isSubscribed ? goToBangumiDetail(item.id) : toggleQuickId(item.id)"
                >
                  {{ item.title || item.name }}
                  <v-icon v-if="item.isSubscribed" end size="x-small" color="success">mdi-check-circle</v-icon>
                </v-chip>
              </v-chip-group>
            </div>
          </template>

          <div v-else class="text-center pa-6 text-medium-emphasis">加载放送表失败</div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <div class="text-caption text-medium-emphasis">已选 {{ selectedQuickIds.length }} 个</div>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showQuickSubModal = false">取消</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-check" :loading="quickSubSubmitting" :disabled="selectedQuickIds.length === 0" @click="handleBatchSubscribe">
            确认批量订阅 ({{ selectedQuickIds.length }})
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.sub-card {
  cursor: pointer;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.sub-poster-box {
  position: relative;
  aspect-ratio: 2/3;
  background: rgba(var(--v-theme-on-surface), 0.04);
  overflow: hidden;
}
.sub-poster-box .v-img {
  width: 100%;
  height: 100%;
}
.sub-poster-placeholder {
  width: 100%;
  height: 100%;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.sub-type-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  line-height: 1.6;
  background: var(--am-badge-overlay-bg);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: var(--am-badge-accent);
}
.sub-ep-badge {
  position: absolute;
  top: 32px;
  left: 6px;
  z-index: 2;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  line-height: 1.5;
  background: var(--am-badge-overlay-bg);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: #fff;
}
.sub-status-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.3px;
  line-height: 1.5;
  background: var(--am-badge-overlay-bg);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.sub-status-badge.active {
  color: #4caf50;
}
.sub-status-badge.inactive {
  color: #f44336;
}
.sub-upgrade-tag {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  padding: 2px 6px;
  border-radius: 4px;
  z-index: 2;
}
.sub-pushed-badge {
  position: absolute;
  bottom: 6px;
  right: 6px;
  z-index: 2;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.5;
  letter-spacing: 0.3px;
  background: var(--am-badge-overlay-bg);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: var(--am-badge-accent);
  display: flex;
  align-items: center;
  white-space: nowrap;
}
</style>
