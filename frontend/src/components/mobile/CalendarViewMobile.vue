<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppTimeField from '../AppTimeField.vue'
import AppGlassModal from '../AppGlassModal.vue'
import { ref, computed } from 'vue'
import {
  NSpace, NIcon, NSpin, NText, NButton, NDatePicker,
  NList, NListItem, NAvatar, NPopconfirm, NTabs, NTabPane,
  NForm, NFormItem, NInputNumber, NTooltip, NDivider, NEmpty, NButtonGroup, NThing, NTag,
  NSwitch
} from 'naive-ui'
import {
  CalendarMonthOutlined as CalendarIcon,
  SettingsOutlined as ManageIcon,
  ImportExportOutlined as ImportIcon,
  DeleteOutlined as DeleteIcon,
  SyncOutlined as RefreshIcon,
  EditOutlined as EditIcon,
  NotificationsActiveOutlined as NotifyIcon,
  SendOutlined as SendIcon
} from '@vicons/material'
import { useCalendar } from '../../composables/views/useCalendar'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { openTmdbDetail } from '../../store/navigationStore'
import { appearanceConfig } from '../../store/appearanceStore'
import { isDarkMode } from '../../store/themeStore'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

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
  showManageModal,
  editingId,
  editBuffer,
  newSubject,
  importingBatch,
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
// NDatePicker 内部嵌套 Input，需用 peers 结构
const inputPeerThemeOverrides = computed(() => {
  // 依赖 isDarkMode 确保主题切换时重算
  const _dark = isDarkMode.value
  const cfg = appearanceConfig.value.input
  const rootStyle = getComputedStyle(document.documentElement)
  const baseColor = rootStyle.getPropertyValue('--app-surface-card').trim()
  const alpha = cfg.enabled ? cfg.bg_opacity : 1
  const rgba = hexToRgba(baseColor, alpha)
  const radius = `${cfg.enabled ? cfg.border_radius : 8}px`
  // 保留 Naive UI 原生边框视觉：普通 / hover / focus 三态
  return {
    peers: {
      Input: {
        color: rgba,
        colorFocus: rgba,
        border: '1px solid var(--border-medium)',
        borderHover: '1px solid var(--text-muted)',
        borderFocus: '1px solid var(--n-primary-color)',
        borderRadius: radius
      }
    }
  }
})

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
</script>

<template>
  <div class="calendar-mobile">
    <!-- Header -->
    <div class="mobile-header">
      <div class="header-left">
        <n-icon size="24" class="calendar-icon"><CalendarIcon /></n-icon>
        <span class="header-title">追剧日历</span>
      </div>
      <n-space :size="6" align="center">
        <n-date-picker
          v-model:value="selectedDate"
          type="date"
          :clearable="false"
          :theme-overrides="inputPeerThemeOverrides"
          size="small"
          style="width: 130px"
          @update:value="handleDateChange"
        />
        <n-button v-bind="getButtonStyle('secondary')" size="small" @click="goToToday">今天</n-button>
        <n-button v-bind="getButtonStyle('icon')" @click="showManageModal = true">
          <template #icon><n-icon><ManageIcon /></n-icon></template>
        </n-button>
      </n-space>
    </div>

    <!-- Card Grid View -->
    <n-spin :show="loading" class="calendar-spin">
      <div class="card-grid-container">
        <div class="selected-date-label">{{ selectedDateLabel }}</div>

        <div v-if="selectedDateItems.length > 0" class="track-card-grid">
          <div v-for="item in selectedDateItems" :key="item.id" class="track-card" @click="openCardDetail(item)">
            <div class="card-poster">
              <img
                v-if="item.posterPath"
                :src="getImg(item.posterPath)"
                :alt="item.title"
                class="poster-img"
                @error="$event.target.style.display = 'none'"
              />
              <div v-else class="placeholder-poster">{{ item.title.charAt(0) }}</div>
              <div class="track-badge">已追踪</div>
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
          </div>
        </div>

        <div v-else class="empty-day">
          <div class="mascot-placeholder">📺</div>
          <span>该日无更新</span>
        </div>
      </div>

      <div v-if="!loading && trackingList.length === 0" class="empty-state">
        <n-empty description="还没有追踪任何番剧" size="large">
          <template #extra>
            <n-button type="primary" @click="showManageModal = true">添加追踪番剧</n-button>
          </template>
        </n-empty>
      </div>
    </n-spin>

    <!-- Manage Modal -->
    <AppGlassModal v-model:show="showManageModal" style="width: 100%; height: 100vh; margin: 0;" content-style="padding: 0; display: flex; flex-direction: column;" title="追踪管理">
      <n-tabs type="line" animated style="flex: 1; display: flex; flex-direction: column;">
        <n-tab-pane name="list" tab="正在追踪" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
          <div style="padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--app-border-light);">
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
          <div class="scroll-container">
            <n-list hoverable>
              <n-list-item v-for="sub in trackingList" :key="sub.id">
                <n-thing :title="sub.title">
                  <template #description>TMDB: {{ sub.tmdb_id }} | S{{ sub.season }} | <span :class="{ 'no-data-text': getEpisodeRange(sub.episodes_cache) === '无数据' }">{{ getEpisodeRange(sub.episodes_cache) }}</span></template>
                  <template #header-extra>
                    <n-button-group size="tiny">
                      <n-button v-bind="getButtonStyle('iconPrimary')" @click="refreshSubject(sub.id)"><template #icon><n-icon><RefreshIcon/></n-icon></template></n-button>
                      <n-popconfirm @positive-click="deleteSubject(sub.id)" positive-text="删" negative-text="取消">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
                        </template>
                        确定删除?
                      </n-popconfirm>
                    </n-button-group>
                  </template>
                </n-thing>
              </n-list-item>
            </n-list>
            <n-empty v-if="trackingList.length === 0" description="暂无追踪" style="margin-top: 40px" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="discover" tab="导入" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
          <div style="padding: 12px">
            <n-button block type="primary" size="small" :loading="importingBatch" @click="handleBatchImport">
              导入全周番剧
            </n-button>
          </div>
          <div class="scroll-container discover-list">
            <div v-for="day in bangumiRaw" :key="day.weekday.id">
              <div class="weekday-header">{{ day.weekday.cn }}</div>
              <div class="discover-grid">
                <div v-for="item in day.items" :key="item.id" class="discover-item" @click="handleAutoImport(item)">
                  <n-avatar size="medium" :src="item.image" />
                  <span class="discover-name">{{ item.title }}</span>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="add" tab="添加">
          <n-form :model="newSubject" label-placement="top" style="padding: 16px">
            <n-form-item><AppTextField v-model:value="newSubject.tmdb_id" label="TMDB ID" placeholder="ID" /></n-form-item>
            <n-form-item><AppTextField v-model:value="newSubject.title" label="标题" placeholder="标题" /></n-form-item>
            <n-form-item><AppTextField v-model:value="newSubject.season" label="季号" type="number" :min="1" /></n-form-item>
            <n-button v-bind="getButtonStyle('primary')" block @click="handleAddSubject">保存</n-button>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="push" tab="推送">
          <div style="padding: 16px; max-height: 60vh; overflow-y: auto;">
            <n-form label-placement="top">
              <!-- 每日番剧播报 -->
              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="18" class="notify-icon"><NotifyIcon /></n-icon>
                <n-text strong>每日番剧播报</n-text>
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

              <n-divider dashed />

              <n-button
                v-bind="getButtonStyle('secondary')"
                block
                @click="testCalendarPush"
                :loading="isTestingPush"
              >
                发送测试播报
              </n-button>

              <n-alert type="info" size="small" :show-icon="false" style="margin-top: 24px; margin-bottom: 16px;">
                系统将在设定时间推送今日播出清单。
              </n-alert>

              <!-- 订阅智能提醒 -->
              <n-divider style="margin: 16px 0;" />

              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="18" class="notify-icon"><NotifyIcon /></n-icon>
                <n-text strong>订阅智能提醒</n-text>
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
                  label="检查间隔(分钟)"
                  type="number"
                  :min="5"
                  :max="1440"
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
                  <span class="switch-row__desc">新集播出时通知</span>
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
                  <span class="switch-row__desc">每天推送播出摘要</span>
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
                订阅提醒会检查你订阅的番剧是否有新集播出，并发送通知。
              </n-alert>
            </n-form>
          </div>
        </n-tab-pane>
      </n-tabs>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.calendar-mobile { padding-bottom: 20px; display: flex; flex-direction: column; height: 100%; }
.mobile-header { display: flex; justify-content: space-between; align-items: center; padding: 0 4px 12px 4px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-title { font-size: 18px; font-weight: bold; }

.calendar-spin { flex: 1; overflow: hidden; }

/* 卡片网格容器 */
.card-grid-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3) var(--space-8);
}

.selected-date-label {
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

/* 番剧卡片网格 - 参考 TMDB 热门动画卡片样式 */
.track-card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

@media (min-width: 400px) {
  .track-card-grid { grid-template-columns: repeat(4, 1fr); }
}

.track-card {
  cursor: pointer;
  transition: transform var(--transition-fast);
  display: flex;
  flex-direction: column;
  min-width: 0;
  -webkit-tap-highlight-color: transparent;
}
.track-card:hover { transform: translateY(-5px); }
.track-card:active { transform: scale(0.95); }

.card-poster {
  width: 100%;
  aspect-ratio: 2/3;
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
  background: var(--bg-tertiary);
  box-shadow: var(--shadow-md);
  margin-bottom: var(--space-1);
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
  font-size: 24px;
  font-weight: bold;
}

.track-badge {
  position: absolute;
  top: 4px;
  left: 4px;
  background: var(--n-primary-color);
  color: #fff;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: bold;
  box-shadow: var(--shadow-sm);
}

.card-info {
  padding: 0 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.ep-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.ep-tag {
  font-size: 10px;
  padding: 1px 5px;
  background: var(--primary-medium, #e3f2fd);
  color: var(--n-primary-color);
  border-radius: var(--radius-sm);
  font-weight: 600;
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
  font-size: 9px;
  padding: 1px 4px;
  background: #ff4757;
  color: white;
  border-radius: var(--radius-sm);
  font-weight: bold;
  margin-left: 2px;
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
  font-size: 40px;
  animation: float 3s ease-in-out infinite;
}

.empty-day span {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  font-weight: 500;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.empty-state { padding: 40px 0; text-align: center; }

.no-data-text {
  color: var(--color-error);
  font-weight: bold;
}

.weekday-header { font-size: 12px; font-weight: bold; color: var(--text-tertiary); margin: 12px 0 8px; }
.discover-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.discover-item { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 4px; padding: 8px; background: var(--bg-surface); border-radius: 8px; }
.discover-name { font-size: 11px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; height: 28px; }
.calendar-icon { color: var(--n-primary-color); }
.notify-icon { color: var(--n-primary-color); }

/* 开关行 - 与项目统一风格：开关靠左，后接标题/说明 */
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }
</style>
