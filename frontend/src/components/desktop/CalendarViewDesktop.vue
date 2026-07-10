<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppTimeField from '../AppTimeField.vue'
import AppGlassModal from '../AppGlassModal.vue'
import AppGlassCard from '../AppGlassCard.vue'
import { ref, computed } from 'vue'
import {
  NSpace, NIcon, NSpin, NText, NButton, NModal, NInput,
  NAvatar, NTabs, NTabPane, useDialog,
  NForm, NFormItem, NInputNumber, NTooltip, NDivider, NEmpty, NButtonGroup,
  NSwitch, NDatePicker, NCard, NGrid, NGi, NImage
} from 'naive-ui'
import {
  CalendarMonthOutlined as CalendarIcon,
  ChevronLeftOutlined as PrevIcon,
  ChevronRightOutlined as NextIcon,
  ImportExportOutlined as ImportIcon,
  DeleteOutlined as DeleteIcon,
  RefreshOutlined as RefreshIcon,
  NotificationsActiveOutlined as NotifyIcon,
  SendOutlined as SendIcon
} from '@vicons/material'
import { useCalendar } from '../../composables/views/useCalendar'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { openTmdbDetail } from '../../store/navigationStore'
import { appearanceConfig } from '../../store/appearanceStore'
import { isDarkMode } from '../../store/themeStore'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''
const dialog = useDialog()

const handleDeleteSubject = (sub: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要从日历中移除「${sub.title}」吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => deleteSubject(sub.id)
  })
}

const getImg = (path: string) => {
  if (!path) return ''
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
  }
  if (!path.startsWith('http')) {
    return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  }
  return path
}

const {
  loading,
  trackingList,
  bangumiRaw,
  viewDate,
  showManageModal,
  editingId,
  editBuffer,
  newSubject,
  importingBatch,
  calendarGrid,
  calendarConfig,
  subscriptionNotifyConfig,
  isTestingPush,
  getEpisodeRange,
  fetchData,
  saveCalendarConfig,
  saveSubscriptionNotifyConfig,
  testCalendarPush,
  handleAutoImport,
  handleBatchImport,
  startEdit,
  saveEdit,
  handleAddSubject,
  refreshSubject,
  refreshAllSubjects,
  deleteSubject,
  clearExpiredSubjects
} = useCalendar()

const selectedDate = ref<number>(Date.now())

const handleDateChange = (timestamp: number) => {
  if (!timestamp) return
  selectedDate.value = timestamp
}

const formatDateStr = (ts: number) => {
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

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

// 所选日期的展示标签
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

const goToToday = () => {
  selectedDate.value = Date.now()
}

// 输入框外观 themeOverrides - 跟随「输入框外观」设置
// 用于 NDatePicker / NInput / NInputNumber 等原生 Naive UI 输入组件
// NInput 直接接收平铺字段；NDatePicker / NInputNumber 内部嵌套 Input，需用 peers 结构
const inputThemeOverrides = computed(() => {
  // 依赖 isDarkMode 确保主题切换时重算
  const _dark = isDarkMode.value
  const cfg = appearanceConfig.value.input
  const rootStyle = getComputedStyle(document.documentElement)
  const baseColor = rootStyle.getPropertyValue('--app-surface-card').trim()
  const alpha = cfg.enabled ? cfg.bg_opacity : 1
  const rgba = hexToRgba(baseColor, alpha)
  const radius = `${cfg.enabled ? cfg.border_radius : 8}px`
  // 保留 Naive UI 原生边框视觉：普通 / hover / focus 三态
  const border = '1px solid var(--border-medium)'
  const borderHover = '1px solid var(--text-muted)'
  const borderFocus = '1px solid var(--n-primary-color)'
  return {
    color: rgba,
    colorFocus: rgba,
    border,
    borderHover,
    borderFocus,
    borderRadius: radius
  }
})

// NDatePicker / NInputNumber 等嵌套 Input 的组件使用 peers 结构
const inputPeerThemeOverrides = computed(() => ({
  peers: { Input: inputThemeOverrides.value }
}))

function hexToRgba(hex: string, alpha: number): string {
  const match = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i)
  if (!match) return `rgba(30, 30, 46, ${alpha})`
  const r = parseInt(match[1], 16)
  const g = parseInt(match[2], 16)
  const b = parseInt(match[3], 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const openCardDetail = (item: any) => {
  if (!item.tmdbId) return
  openTmdbDetail(item.tmdbId, item.mediaType || 'tv', {
    id: item.tmdbId,
    title: item.title,
    poster_path: item.posterPath
  })
}

// 点击卡片打开编辑弹框
const showCardEditModal = ref(false)

const openCardEdit = (sub: any) => {
  startEdit(sub)
  showCardEditModal.value = true
}

const handleCardEditSave = async (id: number) => {
  await saveEdit(id)
  showCardEditModal.value = false
}
</script>

<template>
  <div class="calendar-view">
    <div class="page-header">
      <div>
        <h1>追剧日历</h1>
        <div class="subtitle">番剧播出时间追踪与订阅管理</div>
      </div>

      <n-space align="center">
        <n-date-picker
          v-model:value="selectedDate"
          type="date"
          :clearable="false"
          :theme-overrides="inputPeerThemeOverrides"
          style="width: 160px"
          size="small"
          @update:value="handleDateChange"
        />
        <n-button v-bind="getButtonStyle('secondary')" size="small" @click="showManageModal = true">
          追踪管理
        </n-button>
      </n-space>
    </div>

    <n-spin :show="loading" class="calendar-spin">
      <div class="card-grid-container">
        <div class="selected-date-label">{{ selectedDateLabel }}</div>

        <div v-if="selectedDateItems.length > 0" class="track-card-grid">
          <n-card v-for="item in selectedDateItems" :key="item.id" hoverable class="track-card" content-style="padding: 0;" :data-app-instance="'track-card'" @click="openCardDetail(item)">
            <div class="card-poster">
              <img
                v-if="item.posterPath"
                :src="getImg(item.posterPath)"
                :alt="item.title"
                class="poster-img"
                @error="$event.target.style.display = 'none'"
              />
              <div v-else class="placeholder-poster">{{ item.title.charAt(0) }}</div>
            </div>

            <div class="card-info">
              <div class="card-title" :title="item.title">{{ item.title }}</div>
              <div class="ep-tags">
                <template v-for="ep in item.episodes" :key="ep.ep">
                  <span class="ep-tag" :class="{ 'ep-finale': ep.isFinale }">
                    第{{ item.season }}季 第{{ ep.ep }}话
                  </span>
                  <span v-if="ep.isFinale" class="finale-badge">END</span>
                </template>
              </div>
            </div>
          </n-card>
        </div>

        <div v-else class="empty-day">
          <div class="mascot-placeholder">📺</div>
          <span>该日无更新</span>
        </div>
      </div>

      <!-- 全局空状态 -->
      <div v-if="!loading && trackingList.length === 0" class="empty-state">
        <n-empty description="还没有追踪任何番剧" size="large">
          <template #extra>
            <n-button type="primary" @click="showManageModal = true">添加追踪番剧</n-button>
          </template>
        </n-empty>
      </div>
    </n-spin>

    <AppGlassModal appearance-key="calendar-modal" v-model:show="showManageModal" style="max-width: 900px; width: 90vw;" content-style="padding: 0" title="追踪管理">
      <n-tabs type="line" animated class="manage-tabs">
        <n-tab-pane name="list" tab="正在追踪">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; padding: 0 16px">
            <span style="font-size: 12px; color: var(--text-tertiary)">共 {{ trackingList.length }} 个追踪项</span>
            <n-space :size="8">
              <n-button size="small" @click="clearExpiredSubjects">
                清理过期
              </n-button>
              <n-button type="primary" size="small" @click="refreshAllSubjects">
                全部刷新
              </n-button>
            </n-space>
          </div>
          <div class="tab-content">
            <n-grid :x-gap="8" :y-gap="8" cols="3 600:5 900:6 1200:8 1600:9" v-if="trackingList.length > 0">
              <n-gi v-for="sub in trackingList" :key="sub.id">
                <AppGlassCard appearance-key="track-card" hoverable class="track-manage-card" content-style="padding: 0;" :bordered="true" @click="openCardEdit(sub)">
                  <div class="tm-content">
                    <!-- 海报 -->
                    <div class="tm-poster">
                      <n-image
                        v-if="sub.poster_path"
                        :src="getImg(sub.poster_path)"
                        fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
                        object-fit="cover"
                        preview-disabled
                        style="width: 100%; height: 100%;"
                      />
                      <div v-else class="tm-poster-placeholder">
                        <span>{{ sub.title?.charAt(0) || '?' }}</span>
                      </div>
                    </div>

                    <!-- 信息区 -->
                    <div class="tm-info">
                      <div class="tm-title" :title="sub.title">{{ sub.title }}</div>
                      <div class="tm-meta">
                        <span class="tm-season">S{{ sub.season }}</span>
                        <span class="tm-ep" :class="{ 'no-data-text': getEpisodeRange(sub.episodes_cache) === '无数据' }">{{ getEpisodeRange(sub.episodes_cache) }}</span>
                        <div class="tm-actions" @click.stop>
                          <n-button v-bind="getButtonStyle('icon')" size="tiny" @click="refreshSubject(sub.id)" title="刷新"><template #icon><n-icon><RefreshIcon /></n-icon></template></n-button>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" title="删除" @click="handleDeleteSubject(sub)"><template #icon><n-icon><DeleteIcon /></n-icon></template></n-button>
                        </div>
                      </div>
                    </div>
                  </div>
                </AppGlassCard>
              </n-gi>
            </n-grid>
            <n-empty v-if="trackingList.length === 0" description="暂无追踪条目" style="margin-top: 100px" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="discover" tab="从放送表导入">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; padding: 0 16px">
            <span style="font-size: 12px; color: var(--text-tertiary)">点击下方番剧可自动同步至日历</span>
            <n-button type="primary" size="small" :loading="importingBatch" @click="handleBatchImport">
              导入全周番剧
            </n-button>
          </div>
          <div class="tab-content">
            <div class="discover-grid">
              <div v-for="day in bangumiRaw" :key="day.weekday.id" style="display: contents">
                <div v-for="item in day.items" :key="item.id" class="discover-item" @click="handleAutoImport(item)">
                  <n-avatar size="small" :src="item.image" />
                  <span class="discover-name">{{ item.title }}</span>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="add" tab="手动添加">
          <n-form :model="newSubject" label-placement="left" label-width="80">
            <n-form-item><AppTextField v-model:value="newSubject.tmdb_id" label="TMDB ID" placeholder="例如: 1399" /></n-form-item>
            <n-form-item><AppTextField v-model:value="newSubject.title" label="标题" placeholder="日历显示的标题" /></n-form-item>
            <n-form-item><AppTextField v-model:value="newSubject.season" label="季号" type="number" :min="1" /></n-form-item>
            <n-button v-bind="getButtonStyle('primary')" block @click="handleAddSubject">保存追踪</n-button>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="settings" tab="推送设置">
          <div class="tab-content settings-content">
            <n-form label-placement="left" label-width="140">
              <!-- 每日播报设置 -->
              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="20" class="notify-icon"><NotifyIcon /></n-icon>
                <n-text strong style="font-size: 16px">每日播报设置</n-text>
              </div>

              <n-form-item>
                <div class="switch-row">
                  <n-switch v-model:value="calendarConfig.daily_push_enabled" @update:value="saveCalendarConfig" />
                  <span class="switch-row__label">启用每日播报</span>
                </div>
              </n-form-item>

              <n-form-item :style="{ opacity: calendarConfig.daily_push_enabled ? 1 : 0.5 }">
                <AppTimeField
                  :value="calendarConfig.push_time"
                  label="推送时间"
                  value-format="HH:mm"
                  format="HH:mm"
                  :disabled="!calendarConfig.daily_push_enabled"
                  @update:value="(val: string | null) => { calendarConfig.push_time = val ?? ''; saveCalendarConfig() }"
                />
              </n-form-item>

              <n-form-item :style="{ opacity: calendarConfig.daily_push_enabled ? 1 : 0.5 }">
                <div class="switch-row">
                  <n-switch
                    v-model:value="calendarConfig.pin_message"
                    @update:value="saveCalendarConfig"
                    :disabled="!calendarConfig.daily_push_enabled"
                  />
                  <span class="switch-row__label">消息置顶</span>
                  <span class="switch-row__desc">将播报消息置顶显示</span>
                </div>
              </n-form-item>

              <n-form-item>
                <n-button v-bind="getButtonStyle('secondary')" @click="testCalendarPush" :loading="isTestingPush">
                  发送测试播报
                </n-button>
              </n-form-item>

              <n-alert type="info" size="small" :show-icon="false" style="margin-top: 12px; margin-bottom: 32px;">
                系统将在设定时间通过 Telegram 推送今日播出清单。
              </n-alert>

              <!-- 订阅智能提醒 -->
              <n-divider style="margin: 16px 0;" />

              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="20" class="notify-icon"><NotifyIcon /></n-icon>
                <n-text strong style="font-size: 16px">订阅智能提醒</n-text>
              </div>

              <n-form-item>
                <div class="switch-row">
                  <n-switch v-model:value="subscriptionNotifyConfig.enabled" @update:value="saveSubscriptionNotifyConfig" />
                  <span class="switch-row__label">启用订阅提醒</span>
                </div>
              </n-form-item>

              <n-form-item :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }">
                <AppTextField
                  v-model:value="subscriptionNotifyConfig.interval"
                  label="检查间隔"
                  type="number"
                  :min="5"
                  :max="1440"
                  suffix="分钟"
                  :disabled="!subscriptionNotifyConfig.enabled"
                  @update:value="saveSubscriptionNotifyConfig"
                />
              </n-form-item>

              <n-form-item :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }">
                <div class="switch-row">
                  <n-switch
                    v-model:value="subscriptionNotifyConfig.notify_on_new_episode"
                    @update:value="saveSubscriptionNotifyConfig"
                    :disabled="!subscriptionNotifyConfig.enabled"
                  />
                  <span class="switch-row__label">新集通知</span>
                  <span class="switch-row__desc">检测到新集播出时发送通知</span>
                </div>
              </n-form-item>

              <n-form-item :style="{ opacity: subscriptionNotifyConfig.enabled ? 1 : 0.5 }">
                <div class="switch-row">
                  <n-switch
                    v-model:value="subscriptionNotifyConfig.daily_summary"
                    @update:value="saveSubscriptionNotifyConfig"
                    :disabled="!subscriptionNotifyConfig.enabled"
                  />
                  <span class="switch-row__label">每日摘要</span>
                  <span class="switch-row__desc">每天推送订阅番剧播出摘要</span>
                </div>
              </n-form-item>

              <n-form-item :style="{ opacity: subscriptionNotifyConfig.enabled && subscriptionNotifyConfig.daily_summary ? 1 : 0.5 }">
                <AppTimeField
                  :value="subscriptionNotifyConfig.summary_time"
                  label="摘要时间"
                  value-format="HH:mm"
                  format="HH:mm"
                  :disabled="!subscriptionNotifyConfig.enabled || !subscriptionNotifyConfig.daily_summary"
                  @update:value="(val: string | null) => { subscriptionNotifyConfig.summary_time = val ?? ''; saveSubscriptionNotifyConfig() }"
                />
              </n-form-item>

              <n-alert type="info" size="small" :show-icon="false" style="margin-top: 12px">
                订阅提醒会检查你订阅的番剧是否有新集播出，并通过 Telegram 发送通知。
              </n-alert>
            </n-form>
          </div>
        </n-tab-pane>
      </n-tabs>
    </AppGlassModal>

    <!-- 卡片编辑弹框 -->
    <AppGlassModal appearance-key="calendar-modal" v-model:show="showCardEditModal" style="width: 450px;" :title="editBuffer.title ? `编辑 - ${editBuffer.title}` : '编辑追踪项'">
      <n-form label-placement="left" label-width="60">
        <n-form-item>
          <AppTextField v-model:value="editBuffer.title" label="标题" placeholder="日历显示的标题" />
        </n-form-item>
        <n-form-item>
          <AppTextField v-model:value="editBuffer.season" label="季号" type="number" :min="1" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showCardEditModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleCardEditSave(editingId!)">保存</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.calendar-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-header h1 {
  font-size: var(--text-2xl);
  font-weight: 800;
  margin: 0;
  color: var(--text-primary);
}

.subtitle {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: 4px;
}

.calendar-spin {
  flex: 1;
  overflow: hidden;
}

/* 卡片网格容器 */
.card-grid-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) 0 var(--space-8);
}

.selected-date-label {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-4);
  padding: 0 var(--m-1);
}

/* 番剧卡片网格 - 参考 TMDB 热门动画卡片样式 */
.track-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-5);
  padding: 0 var(--m-1);
}

.track-card {
  cursor: pointer;
  transition: all var(--transition-normal);
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--app-border-light) !important;
  background: var(--app-surface-card-mixed) !important;
  border-radius: var(--card-border-radius, 12px) !important;
  -webkit-tap-highlight-color: transparent;
}
.track-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-xl);
  border-color: var(--n-primary-color) !important;
}
.track-card:active { transform: scale(0.95); }

.card-poster {
  width: 100%;
  aspect-ratio: 2/3;
  overflow: hidden;
  position: relative;
  background: var(--bg-tertiary);
}
.card-poster .poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder-poster {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, var(--n-primary-color), #667eea);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 36px;
  font-weight: bold;
}

.card-info {
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.ep-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ep-tag {
  font-size: var(--text-sm);
  padding: 2px 8px;
  background: var(--primary-medium, #e3f2fd);
  color: var(--n-primary-color);
  border-radius: var(--radius-sm);
  font-weight: 600;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.ep-tag:hover {
  background: var(--n-primary-color);
  color: white;
}

.ep-tag.ep-finale {
  background: linear-gradient(135deg, #ff6b9d, #ffa07a);
  color: white;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.finale-badge {
  font-size: var(--text-xs);
  padding: 2px 6px;
  background: #ff4757;
  color: white;
  border-radius: var(--radius-sm);
  font-weight: bold;
  margin-left: 4px;
  animation: pulse 2s infinite;
}

/* 空状态 - 单日无更新 */
.empty-day {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0.5;
  user-select: none;
  padding: var(--space-10) 0;
}

.empty-day .mascot-placeholder {
  font-size: 48px;
  animation: float 3s ease-in-out infinite;
}

.empty-day span {
  font-size: var(--text-base);
  color: var(--text-tertiary);
  font-weight: 500;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Modal 样式 */
.discover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
  padding: 4px;
}

.manage-tabs {
  padding-bottom: 16px;
  --tabs-pane-padding: 16px 0;
}

.tab-content {
  padding: 0 16px;
}

.settings-content {
  padding: 24px 40px;
}

/* 追踪管理卡片 - 参考追剧订阅/元数据资产卡片风格 */
.track-manage-card {
  overflow: hidden;
  transition: all var(--transition-normal);
}
.track-manage-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.tm-content {
  display: flex;
  flex-direction: column;
}

.tm-poster {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  background: var(--app-surface-inner);
  overflow: hidden;
  cursor: pointer;
}
.tm-poster :deep(img) {
  width: 100%;
  height: 100%;
  transition: transform var(--transition-slow);
}
.track-manage-card:hover .tm-poster :deep(img) {
  transform: scale(1.08);
}

.tm-poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--n-primary-color), #667eea);
  color: white;
  font-size: 24px;
  font-weight: bold;
}

.tm-info {
  padding: 6px 8px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tm-title {
  font-weight: 700;
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--app-instance-text-color, var(--text-primary));
  cursor: pointer;
}

.tm-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--app-instance-text-secondary-color, var(--text-tertiary));
}
.tm-meta .tm-actions {
  margin-left: auto;
}

.tm-season {
  color: var(--n-primary-color);
  font-weight: 600;
}

.tm-ep {
  color: var(--app-instance-text-secondary-color, var(--text-tertiary));
}

.no-data-text {
  color: var(--color-error);
  font-weight: bold;
}

.tm-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.discover-item { display: flex; align-items: center; gap: 8px; padding: 6px; border-radius: 6px; background: var(--bg-surface); cursor: pointer; transition: background var(--transition-fast); min-width: 0; }
.discover-item:hover { background: var(--primary-light); }
.discover-name { font-size: var(--text-base); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.calendar-icon { color: var(--n-primary-color); }
.notify-icon { color: var(--n-primary-color); }

/* 开关行 - 与项目统一风格：开关靠左，后接标题/说明 */
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }

/* 响应式布局 */
@media (max-width: 900px) {
  .track-card-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--space-4);
  }
}
</style>