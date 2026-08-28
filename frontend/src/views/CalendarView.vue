<script setup lang="ts">
/**
 * CalendarView — 追剧日历
 *
 * 功能对标旧前端 CalendarViewDesktop:
 * - 基于追踪番剧的日历视图（选中日期展示当天播出的番剧）
 * - 追踪管理弹窗（正在追踪 / 从放送表导入 / 手动添加 / 推送设置）
 * - 单个/批量刷新追踪项
 * - 清理过期追踪项
 * - 编辑追踪项（标题/季号）
 * - 每日播报配置 + 订阅智能提醒配置
 * - 测试推送播报
 */
import { ref, computed, onMounted } from 'vue'
import { calendarApi, bangumiApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'CalendarView' })

const { success, error: showError, warning, info } = useNotification()
const { confirm } = useConfirm()
const navStore = useNavigationStore()

// --- 数据 ---
const loading = ref(false)
const trackingList = ref<any[]>([])
const bangumiRaw = ref<any[]>([])

// --- 日期选择 ---
const selectedDate = ref<number>(Date.now())

const formatDateStr = (ts: number) => {
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 日期选择器需要 YYYY-MM-DD 格式的字符串
const selectedDateStr = computed({
  get() {
    return formatDateStr(selectedDate.value)
  },
  set(val: string) {
    if (val) {
      selectedDate.value = new Date(val).getTime()
    }
  },
})

const selectedDateLabel = computed(() => {
  const d = new Date(selectedDate.value)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(d)
  target.setHours(0, 0, 0, 0)
  const diff = Math.round((target.getTime() - today.getTime()) / 86400000)
  let label = ''
  if (diff === 0) label = '今天'
  else if (diff === -1) label = '昨天'
  else if (diff === 1) label = '明天'
  else label = `周${['日', '一', '二', '三', '四', '五', '六'][d.getDay()]}`
  return `${d.getMonth() + 1}月${d.getDate()}日 ${label}`
})

// 仅展示所选日期的番剧卡片
const selectedDateItems = computed(() => {
  const dateStr = formatDateStr(selectedDate.value)
  const items: any[] = []

  trackingList.value.forEach(sub => {
    if (sub.episodes_cache && Array.isArray(sub.episodes_cache)) {
      const matches = sub.episodes_cache.filter((ep: any) => ep.air_date === dateStr)
      if (matches.length > 0) {
        items.push({
          id: sub.id,
          tmdbId: sub.tmdb_id,
          mediaType: sub.media_type || 'tv',
          title: sub.title,
          season: sub.season,
          posterPath: sub.poster_path || null,
          episodes: matches.map((m: any) => ({
            ep: m.episode,
            title: m.name,
            isFinale: m.episode_type === 'finale'
          }))
        })
      }
    }
  })
  return items
})

// 使用统一的 getImg 函数（自动附加 token 和处理代理路径）

function openCardDetail(item: any) {
  if (!item.tmdbId) return
  navStore.openTmdbDetail(item.tmdbId, item.mediaType || 'tv')
}

// --- 追踪管理弹窗 ---
const showManageModal = ref(false)
const manageTab = ref('list')

// --- 编辑追踪项 ---
const showEditModal = ref(false)
const editingId = ref<number | null>(null)
const editBuffer = ref({ title: '', season: 1 })

// --- 手动添加 ---
const newSubject = ref({ tmdb_id: '', media_type: 'tv', title: '', season: 1 })

// --- 推送配置 ---
const calendarConfig = ref({
  daily_push_enabled: false,
  push_time: '09:00',
  pin_message: false,
  bgm_push_enabled: false,
  bgm_push_time: '09:00',
  bgm_pin_message: false,
})

const subscriptionNotifyConfig = ref({
  enabled: true,
  interval: 60,
  notify_on_new_episode: true,
  daily_summary: false,
  summary_time: '08:00',
})

const isTestingPush = ref(false)
const isTestingBgmPush = ref(false)
const importingBatch = ref(false)

// 已导入的 bangumi ID 集合（用于从放送表导入时标记已导入项）
const importedIds = computed(() => {
  const ids = new Set<number>()
  trackingList.value.forEach((t: any) => {
    if (t.bgm_id) ids.add(t.bgm_id)
  })
  return ids
})

// --- 方法 ---
async function fetchData() {
  loading.value = true
  try {
    const [trackRes, bgmRes, configRes] = await Promise.allSettled([
      calendarApi.getSubjects(),
      bangumiApi.getCalendar(),
      configApi.getConfig(),
    ])

    if (trackRes.status === 'fulfilled') {
      trackingList.value = trackRes.value || []
    }
    if (bgmRes.status === 'fulfilled') {
      const bgmData = bgmRes.value
      bangumiRaw.value = bgmData?.status === 'success' ? (bgmData.data || []) : (Array.isArray(bgmData) ? bgmData : [])
    }
    if (configRes.status === 'fulfilled') {
      const configData = configRes.value || {}
      calendarConfig.value = {
        daily_push_enabled: configData.calendar_daily_push || false,
        push_time: configData.calendar_push_time || '09:00',
        pin_message: configData.calendar_pin_message || false,
        bgm_push_enabled: configData.bgm_schedule_daily_push || false,
        bgm_push_time: configData.bgm_schedule_push_time || '09:00',
        bgm_pin_message: configData.bgm_schedule_pin_message || false,
      }
      subscriptionNotifyConfig.value = {
        enabled: configData.subscription_notify_enabled ?? true,
        interval: configData.subscription_notify_interval || 60,
        notify_on_new_episode: configData.subscription_notify_on_new_episode ?? true,
        daily_summary: configData.subscription_daily_summary || false,
        summary_time: configData.subscription_summary_time || '08:00',
      }
    }
  } catch (e) {
    showError('加载日历数据失败')
  } finally {
    loading.value = false
  }
}

async function saveCalendarConfig() {
  try {
    await configApi.saveConfig({
      calendar_daily_push: calendarConfig.value.daily_push_enabled,
      calendar_push_time: calendarConfig.value.push_time,
      calendar_pin_message: calendarConfig.value.pin_message,
      bgm_schedule_daily_push: calendarConfig.value.bgm_push_enabled,
      bgm_schedule_push_time: calendarConfig.value.bgm_push_time,
      bgm_schedule_pin_message: calendarConfig.value.bgm_pin_message,
    })
    success('推送设置已更新')
  } catch (e) {
    showError('保存设置失败')
  }
}

async function saveSubscriptionNotifyConfig() {
  try {
    await configApi.saveConfig({
      subscription_notify_enabled: subscriptionNotifyConfig.value.enabled,
      subscription_notify_interval: subscriptionNotifyConfig.value.interval,
      subscription_notify_on_new_episode: subscriptionNotifyConfig.value.notify_on_new_episode,
      subscription_daily_summary: subscriptionNotifyConfig.value.daily_summary,
      subscription_summary_time: subscriptionNotifyConfig.value.summary_time,
    })
    success('订阅提醒设置已更新')
  } catch (e) {
    showError('保存设置失败')
  }
}

async function testCalendarPush() {
  isTestingPush.value = true
  try {
    const data = await calendarApi.testPush()
    if (data?.success) {
      success(data.message || '测试推送已发送')
    } else {
      showError(data?.message || '推送失败')
    }
  } catch (e) {
    showError('推送请求失败')
  } finally {
    isTestingPush.value = false
  }
}

async function testBgmPush() {
  isTestingBgmPush.value = true
  try {
    const data = await calendarApi.testBgmSchedulePush()
    if (data?.success) {
      success(data.message || '测试推送已发送')
    } else {
      showError(data?.message || '推送失败')
    }
  } catch (e) {
    showError('推送请求失败')
  } finally {
    isTestingBgmPush.value = false
  }
}

async function handleAutoImport(bgmItem: any) {
  const ok = await confirm({
    title: '确认导入',
    content: `确定要导入《${bgmItem.title}》到追踪日历吗？`,
    confirmColor: 'primary',
  })
  if (!ok) return
  info(`正在为《${bgmItem.title}》同步数据...`)
  try {
    const data = await calendarApi.importBangumi(bgmItem.id)
    if (data?.success) {
      success(data.message || '导入成功')
      fetchData()
    } else {
      showError(data?.message || '导入失败')
    }
  } catch (e) {
    showError('导入失败')
  }
}

async function handleBatchImport() {
  const allIds = bangumiRaw.value.flatMap((day: any) => day.items.map((item: any) => item.id))
  if (allIds.length === 0) return

  importingBatch.value = true
  info(`正在批量导入 ${allIds.length} 个项目，请稍候...`)
  try {
    const data = await calendarApi.batchImportBangumi(allIds)
    success(`批量操作完成：成功 ${data?.success || 0} 个，失败 ${data?.failed || 0} 个`)
    fetchData()
  } catch (e) {
    showError('批量导入失败')
  } finally {
    importingBatch.value = false
  }
}

function startEdit(sub: any) {
  editingId.value = sub.id
  editBuffer.value = { title: sub.title, season: sub.season }
  showEditModal.value = true
}

async function saveEdit() {
  if (editingId.value === null) return
  try {
    const data = await calendarApi.updateSubject(editingId.value, editBuffer.value)
    if (data?.success) {
      success('更新成功')
      showEditModal.value = false
      fetchData()
    } else {
      showError(data?.message || '更新失败')
    }
  } catch (e) {
    showError('更新失败')
  }
}

async function handleAddSubject() {
  if (!newSubject.value.tmdb_id) {
    warning('请输入 TMDB ID')
    return
  }
  try {
    const data = await calendarApi.addSubject(newSubject.value)
    if (data?.success) {
      success('添加成功')
      fetchData()
      newSubject.value = { tmdb_id: '', media_type: 'tv', title: '', season: 1 }
    } else {
      showError(data?.message || '添加失败')
    }
  } catch (e) {
    showError('添加失败')
  }
}

async function refreshSubject(sub: any) {
  const ok = await confirm({
    title: '确认刷新',
    content: `确定要刷新「${sub.title}」的放送数据吗？`,
  })
  if (!ok) return
  try {
    const data = await calendarApi.refreshSubject(sub.id)
    if (data?.success) {
      success('已同步最新放送日期')
      fetchData()
    } else {
      showError(data?.message || '同步失败')
    }
  } catch (e) {
    showError('同步失败')
  }
}

async function refreshAllSubjects() {
  if (trackingList.value.length === 0) {
    info('没有需要刷新的追踪项')
    return
  }
  loading.value = true
  info(`正在刷新 ${trackingList.value.length} 个追踪项...`)
  try {
    const data = await calendarApi.refreshAllSubjects()
    if (data?.success) {
      success(data.message || '刷新完成')
      fetchData()
    } else {
      showError(data?.message || '批量刷新失败')
    }
  } catch (e) {
    showError('批量刷新失败')
  } finally {
    loading.value = false
  }
}

async function deleteSubject(sub: any) {
  const ok = await confirm({
    title: '确认删除',
    content: `确定要从日历中移除「${sub.title}」吗？`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await calendarApi.deleteSubject(sub.id)
    success('已删除')
    fetchData()
  } catch (e) {
    showError('删除失败')
  }
}

async function clearExpiredSubjects() {
  const ok = await confirm({
    title: '确认清理',
    content: '确定要清理所有已过期的追踪项吗？',
    confirmColor: 'warning',
  })
  if (!ok) return
  try {
    const data = await calendarApi.clearExpired()
    if (data?.success) {
      if (data.deleted_count > 0) {
        success(data.message || `已清理 ${data.deleted_count} 个过期项`)
      } else {
        info(data.message || '没有过期项需要清理')
      }
      fetchData()
    }
  } catch (e) {
    showError('清理失败')
  }
}

function getEpisodeRange(episodes: any[]): string {
  if (!episodes || !Array.isArray(episodes) || episodes.length === 0) {
    return '无数据'
  }
  const epNumbers = episodes.map(ep => ep.episode).filter(ep => ep !== undefined && ep !== null).sort((a, b) => a - b)
  if (epNumbers.length === 0) return '无数据'
  if (epNumbers.length === 1) return `第 ${epNumbers[0]} 集`
  return `${epNumbers[0]}-${epNumbers[epNumbers.length - 1]} 集`
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6 calendar-view">
    <div class="d-flex align-center justify-end mb-4">
      <div class="d-flex align-center ga-3">
        <v-text-field
          v-model="selectedDateStr"
          type="date"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 180px"
        />
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-format-list-bulleted" @click="showManageModal = true">
          追踪管理
        </v-btn>
      </div>
    </div>

    <!-- 加载状态 -->
    <template v-if="loading">
      <div class="track-card-grid">
        <v-skeleton-loader v-for="i in 4" :key="i" type="card" />
      </div>
    </template>

    <template v-else>
      <!-- 所选日期标签 -->
      <div class="text-h6 font-weight-bold mb-4">{{ selectedDateLabel }}</div>

      <!-- 番剧卡片网格 -->
      <div v-if="selectedDateItems.length > 0" class="track-card-grid">
        <v-card
          v-for="item in selectedDateItems"
          :key="item.id"
          class="glass-card track-card cursor-pointer"
          @click="openCardDetail(item)"
        >
          <!-- 海报 -->
          <div class="track-card__poster">
            <v-img
              v-if="item.posterPath"
              :src="getImg(item.posterPath)"
              cover
            >
              <template #placeholder>
                <v-skeleton-loader type="image" />
              </template>
            </v-img>
            <div v-else class="track-card__placeholder">
              <span>{{ item.title.charAt(0) }}</span>
            </div>
          </div>

          <!-- 信息 -->
          <div class="track-card__info">
            <div class="track-card__title">{{ item.title }}</div>
            <div class="d-flex flex-wrap ga-1 justify-center">
              <v-chip
                v-for="ep in item.episodes"
                :key="ep.ep"
                size="x-small"
                :color="ep.isFinale ? 'error' : 'primary'"
                variant="tonal"
              >
                第{{ item.season }}季 第{{ ep.ep }}话
              </v-chip>
              <v-chip v-if="item.episodes.some((e: any) => e.isFinale)" size="x-small" color="error" variant="flat">
                END
              </v-chip>
            </div>
          </div>
        </v-card>
      </div>

      <!-- 空状态 - 单日无更新 -->
      <div v-else-if="trackingList.length > 0" class="text-center pa-12">
        <div style="font-size: 48px;">📺</div>
        <div class="text-body-1 text-medium-emphasis mt-3">该日无更新</div>
      </div>

      <!-- 全局空状态 -->
      <div v-else class="text-center pa-12">
        <v-icon size="64" color="primary" class="mb-4">mdi-calendar-blank</v-icon>
        <div class="text-h6 font-weight-medium mb-2">还没有追踪任何番剧</div>
        <div class="text-body-2 text-medium-emphasis mb-4">点击"追踪管理"添加追踪番剧</div>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-plus" @click="showManageModal = true">添加追踪番剧</v-btn>
      </div>
    </template>

    <!-- 追踪管理弹窗 -->
    <v-dialog v-model="showManageModal" max-width="900" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-calendar-month</v-icon>
          追踪管理
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showManageModal = false" />
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4" style="min-height: 400px">
          <v-tabs v-model="manageTab" color="primary" class="mb-4">
            <v-tab value="list">正在追踪</v-tab>
            <v-tab value="discover">从放送表导入</v-tab>
            <v-tab value="add">手动添加</v-tab>
            <v-tab value="settings">推送设置</v-tab>
          </v-tabs>

          <v-window v-model="manageTab">
            <!-- 正在追踪 -->
            <v-window-item value="list">
              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-caption text-medium-emphasis">共 {{ trackingList.length }} 个追踪项</span>
                <div class="d-flex ga-2">
                  <v-btn color="warning" variant="tonal" size="small" prepend-icon="mdi-broom" @click="clearExpiredSubjects">清理过期</v-btn>
                  <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-refresh" @click="refreshAllSubjects">全部刷新</v-btn>
                </div>
              </div>

              <div v-if="trackingList.length > 0" class="cal-manage-grid">
                <v-card
                  v-for="sub in trackingList"
                  :key="sub.id"
                  class="glass-card media-card cursor-pointer"
                  @click="startEdit(sub)"
                >
                  <!-- 海报 -->
                  <div class="media-card__poster">
                    <v-img
                      v-if="sub.poster_path"
                      :src="getImg(sub.poster_path)"
                      cover
                    >
                      <template #placeholder>
                        <v-skeleton-loader type="image" />
                      </template>
                    </v-img>
                    <div v-else class="media-card__poster-placeholder">
                      <v-icon size="36" color="primary">mdi-television-classic</v-icon>
                    </div>
                    <span class="media-card__type media-card__type--tmdb-tv">S{{ sub.season }}</span>
                  </div>
                  <!-- 信息区 -->
                  <div class="media-card__info">
                    <div class="media-card__title" :title="sub.title">{{ sub.title }}</div>
                    <div
                      class="media-card__subtitle"
                      :class="{ 'text-error': getEpisodeRange(sub.episodes_cache) === '无数据' }"
                    >
                      {{ getEpisodeRange(sub.episodes_cache) }}
                    </div>
                  </div>
                  <!-- 操作按钮 -->
                  <div class="media-card__actions" @click.stop>
                    <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-refresh" @click="refreshSubject(sub)">刷新</v-btn>
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteSubject(sub)">删除</v-btn>
                  </div>
                </v-card>
              </div>
              <div v-else class="text-center pa-8">
                <v-icon size="64" color="primary" class="mb-4">mdi-calendar-remove</v-icon>
                <div class="text-h6 font-weight-medium">暂无追踪条目</div>
                <div class="text-body-2 text-medium-emphasis mt-2">通过"从放送表导入"或"手动添加"添加追踪番剧</div>
              </div>
            </v-window-item>

            <!-- 从放送表导入 -->
            <v-window-item value="discover">
              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-caption text-medium-emphasis">点击下方番剧可自动同步至日历</span>
                <v-btn variant="tonal" color="primary" size="small" :loading="importingBatch" prepend-icon="mdi-download" @click="handleBatchImport">
                  导入全周番剧
                </v-btn>
              </div>
              <template v-if="bangumiRaw.length > 0">
                <div v-for="day in bangumiRaw" :key="day.weekday.id" class="mb-4">
                  <div class="text-subtitle-2 font-weight-bold mb-2 text-primary">
                    周{{ ['日','一','二','三','四','五','六'][day.weekday.id] }}
                  </div>
                  <v-chip-group column>
                    <v-chip
                      v-for="item in day.items"
                      :key="item.id"
                      size="small"
                      variant="outlined"
                      color="primary"
                      :disabled="importedIds.has(item.id)"
                      @click="handleAutoImport(item)"
                    >
                      {{ item.title }}
                      <v-icon v-if="importedIds.has(item.id)" end size="x-small" color="success">mdi-check-circle</v-icon>
                    </v-chip>
                  </v-chip-group>
                </div>
              </template>
              <div v-else class="text-center pa-6 text-medium-emphasis">暂无放送表数据</div>
            </v-window-item>

            <!-- 手动添加 -->
            <v-window-item value="add">
              <v-select
                v-model="newSubject.media_type"
                :items="[{ title: '剧集 (TV)', value: 'tv' }, { title: '电影 (Movie)', value: 'movie' }]"
                label="媒体类型"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="newSubject.tmdb_id"
                label="TMDB ID"
                placeholder="例如: 1399"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="newSubject.title"
                label="标题"
                placeholder="日历显示的标题"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model.number="newSubject.season"
                label="季号"
                type="number"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
              <v-btn variant="tonal" color="primary" block prepend-icon="mdi-plus" @click="handleAddSubject">保存追踪</v-btn>
            </v-window-item>

            <!-- 推送设置 -->
            <v-window-item value="settings">
              <!-- 每日播报设置 -->
              <div class="d-flex align-center ga-2 mb-4">
                <v-icon color="primary">mdi-bell-outline</v-icon>
                <span class="text-subtitle-1 font-weight-bold">每日播报设置</span>
              </div>

              <div class="d-flex align-center ga-3 mb-3">
                <v-switch
                  v-model="calendarConfig.daily_push_enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="saveCalendarConfig"
                />
                <span class="text-body-2">启用每日播报</span>
              </div>

              <div :style="{ opacity: calendarConfig.daily_push_enabled ? 1 : 0.5 }" class="mb-3">
                <v-text-field
                  v-model="calendarConfig.push_time"
                  label="推送时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                  :disabled="!calendarConfig.daily_push_enabled"
                  @change="saveCalendarConfig"
                />
              </div>

              <div class="d-flex align-center ga-3 mb-3" :style="{ opacity: calendarConfig.daily_push_enabled ? 1 : 0.5 }">
                <v-switch
                  v-model="calendarConfig.pin_message"
                  color="primary"
                  hide-details
                  density="compact"
                  :disabled="!calendarConfig.daily_push_enabled"
                  @update:model-value="saveCalendarConfig"
                />
                <div>
                  <span class="text-body-2">消息置顶</span>
                  <div class="text-caption text-medium-emphasis">将播报消息置顶显示</div>
                </div>
              </div>

              <v-btn variant="tonal" color="primary" prepend-icon="mdi-send" :loading="isTestingPush" class="mb-4" @click="testCalendarPush">
                发送测试播报
              </v-btn>

              <v-alert type="info" density="compact" class="mb-6" variant="tonal">
                系统将在设定时间通过 Telegram 推送今日播出清单。
              </v-alert>

              <v-divider class="my-4" />

              <!-- BGM 放送表每日推送 -->
              <div class="d-flex align-center ga-2 mb-4">
                <v-icon color="primary">mdi-calendar-clock-outline</v-icon>
                <span class="text-subtitle-1 font-weight-bold">BGM 放送表每日推送</span>
              </div>

              <div class="d-flex align-center ga-3 mb-3">
                <v-switch
                  v-model="calendarConfig.bgm_push_enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="saveCalendarConfig"
                />
                <span class="text-body-2">启用每日推送</span>
              </div>

              <div :style="{ opacity: calendarConfig.bgm_push_enabled ? 1 : 0.5 }" class="mb-3">
                <v-text-field
                  v-model="calendarConfig.bgm_push_time"
                  label="推送时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                  :disabled="!calendarConfig.bgm_push_enabled"
                  @change="saveCalendarConfig"
                />
              </div>

              <div class="d-flex align-center ga-3 mb-3" :style="{ opacity: calendarConfig.bgm_push_enabled ? 1 : 0.5 }">
                <v-switch
                  v-model="calendarConfig.bgm_pin_message"
                  color="primary"
                  hide-details
                  density="compact"
                  :disabled="!calendarConfig.bgm_push_enabled"
                  @update:model-value="saveCalendarConfig"
                />
                <div>
                  <span class="text-body-2">消息置顶</span>
                  <div class="text-caption text-medium-emphasis">将放送表消息置顶显示</div>
                </div>
              </div>

              <v-btn variant="tonal" color="primary" prepend-icon="mdi-send" :loading="isTestingBgmPush" class="mb-4" @click="testBgmPush">
                发送测试推送
              </v-btn>

              <v-alert type="info" density="compact" class="mb-6" variant="tonal">
                推送 BGM（Bangumi）「播出时间表」中当天放送的全部番剧清单（含播出时间与平台），数据与番剧探索页一致；与上面的每日播报不同，这里不限于你追踪的条目。
              </v-alert>

              <v-divider class="my-4" />

              <!-- 订阅智能提醒 -->
              <div class="d-flex align-center ga-2 mb-4">
                <v-icon color="primary">mdi-bell-ring-outline</v-icon>
                <span class="text-subtitle-1 font-weight-bold">订阅智能提醒</span>
              </div>

              <div class="d-flex align-center ga-3 mb-3">
                <v-switch
                  v-model="subscriptionNotifyConfig.enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="saveSubscriptionNotifyConfig"
                />
                <span class="text-body-2">启用订阅提醒</span>
              </div>

              <div :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }" class="mb-3">
                <v-text-field
                  v-model.number="subscriptionNotifyConfig.interval"
                  label="检查间隔 (分钟)"
                  type="number"
                  variant="outlined"
                  density="compact"
                  :disabled="!subscriptionNotifyConfig.enabled"
                  @change="saveSubscriptionNotifyConfig"
                />
              </div>

              <div class="d-flex align-center ga-3 mb-3" :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }">
                <v-switch
                  v-model="subscriptionNotifyConfig.notify_on_new_episode"
                  color="primary"
                  hide-details
                  density="compact"
                  :disabled="!subscriptionNotifyConfig.enabled"
                  @update:model-value="saveSubscriptionNotifyConfig"
                />
                <div>
                  <span class="text-body-2">新集通知</span>
                  <div class="text-caption text-medium-emphasis">订阅番剧的新集播出后立即逐集提醒（仅提醒播出，与下载状态无关）</div>
                </div>
              </div>

              <div class="d-flex align-center ga-3 mb-3" :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }">
                <v-switch
                  v-model="subscriptionNotifyConfig.daily_summary"
                  color="primary"
                  hide-details
                  density="compact"
                  :disabled="!subscriptionNotifyConfig.enabled"
                  @update:model-value="saveSubscriptionNotifyConfig"
                />
                <div>
                  <span class="text-body-2">每日摘要</span>
                  <div class="text-caption text-medium-emphasis">每天在指定时间推送一条「今日有哪些订阅番剧播出」的清单，当天无播出则不推送</div>
                </div>
              </div>

              <div
                :style="{ opacity: subscriptionNotifyConfig.enabled && subscriptionNotifyConfig.daily_summary ? 1 : 0.5 }"
                class="mb-3"
              >
                <v-text-field
                  v-model="subscriptionNotifyConfig.summary_time"
                  label="摘要时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                  :disabled="!subscriptionNotifyConfig.enabled || !subscriptionNotifyConfig.daily_summary"
                  @change="saveSubscriptionNotifyConfig"
                />
              </div>

              <v-alert type="info" density="compact" variant="tonal">
                订阅提醒只针对「追剧订阅」里启用的番剧：新集通知按集即时提醒播出，每日摘要每天定时汇总当日播出清单。通知通过 Telegram 发送，与「日历每日播报」（基于日历追踪条目）相互独立。
              </v-alert>
            </v-window-item>
          </v-window>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- 编辑追踪项弹窗 -->
    <v-dialog v-model="showEditModal" max-width="450">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-pencil</v-icon>
          {{ editBuffer.title ? `编辑 - ${editBuffer.title}` : '编辑追踪项' }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showEditModal = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field
            v-model="editBuffer.title"
            label="标题"
            variant="outlined"
            density="compact"
            class="mb-3"
          />
          <v-text-field
            v-model.number="editBuffer.season"
            label="季号"
            type="number"
            variant="outlined"
            density="compact"
          />
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showEditModal = false">取消</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="saveEdit">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
