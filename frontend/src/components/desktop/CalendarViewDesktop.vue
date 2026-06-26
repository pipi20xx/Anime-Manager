<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppTimeField from '../AppTimeField.vue'
import { ref, computed } from 'vue'
import {
  NSpace, NIcon, NSpin, NText, NButton, NModal, NInput,
  NList, NListItem, NAvatar, NPopconfirm, NTabs, NTabPane,
  NForm, NFormItem, NInputNumber, NTooltip, NDivider, NEmpty, NButtonGroup,
  NSwitch, NDatePicker
} from 'naive-ui'
import {
  CalendarMonthOutlined as CalendarIcon,
  ChevronLeftOutlined as PrevIcon,
  ChevronRightOutlined as NextIcon,
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
          style="width: 160px"
          size="small"
          @update:value="handleDateChange"
        />
        <n-button v-bind="getButtonStyle('secondary')" size="small" @click="goToToday">
          今天
        </n-button>
        <n-button v-bind="getButtonStyle('secondary')" size="small" @click="showManageModal = true">
          管理追踪
        </n-button>
      </n-space>
    </div>

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

      <!-- 全局空状态 -->
      <div v-if="!loading && trackingList.length === 0" class="empty-state">
        <n-empty description="还没有追踪任何番剧" size="large">
          <template #extra>
            <n-button type="primary" @click="showManageModal = true">添加追踪番剧</n-button>
          </template>
        </n-empty>
      </div>
    </n-spin>

    <n-modal v-model:show="showManageModal" preset="card" style="width: 95%; max-width: 1200px" content-style="padding: 0" title="追踪管理">
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
            <n-list :show-divider="false" class="compact-list">
              <n-list-item v-for="sub in trackingList" :key="sub.id">
                <div class="tracking-item-row">
                  <div class="item-main">
                    <div class="item-info">
                      <span class="item-title">{{ sub.title }}</span>
                      <span class="item-desc">TMDB: {{ sub.tmdb_id }} | S{{ sub.season }} | <span :class="{ 'no-data-text': getEpisodeRange(sub.episodes_cache) === '无数据' }">{{ getEpisodeRange(sub.episodes_cache) }}</span></span>
                    </div>
                  </div>

                  <div class="item-actions">
                    <template v-if="editingId === sub.id">
                      <n-space :size="4" align="center">
                        <n-input v-model:value="editBuffer.title" placeholder="标题" size="tiny" style="width: 150px" />
                        <n-input-number v-model:value="editBuffer.season" :min="1" size="tiny" style="width: 80px" />
                        <n-button v-bind="getButtonStyle('primary')" @click="saveEdit(sub.id)">保存</n-button>
                        <n-button v-bind="getButtonStyle('dialogCancel')" @click="editingId = null">取消</n-button>
                      </n-space>
                    </template>
                    <template v-else>
                      <n-button-group>
                        <n-button v-bind="getButtonStyle('icon')" size="small" @click="startEdit(sub)" title="编辑"><template #icon><n-icon><EditIcon /></n-icon></template></n-button>
                        <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="refreshSubject(sub.id)" title="同步"><template #icon><n-icon><RefreshIcon /></n-icon></template></n-button>
                        <n-popconfirm 
                          positive-text="确认"
                          negative-text="取消"
                          @positive-click="deleteSubject(sub.id)"
                        >
                          <template #trigger><n-button v-bind="getButtonStyle('iconDanger')" size="small" title="删除"><template #icon><n-icon><DeleteIcon /></n-icon></template></n-button></template>
                          确定要从日历中移除此追踪项吗？
                        </n-popconfirm>
                      </n-button-group>
                    </template>
                  </div>
                </div>
              </n-list-item>
            </n-list>
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
    </n-modal>
  </div>
</template>

<style scoped>
.calendar-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--app-bg-color);
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
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--space-5);
  padding: 0 var(--m-1);
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
  border-radius: var(--radius-xl);
  overflow: hidden;
  position: relative;
  background: var(--bg-tertiary);
  box-shadow: var(--shadow-md);
  margin-bottom: var(--space-2);
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

.track-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  background: var(--n-primary-color);
  color: #fff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: bold;
  box-shadow: var(--shadow-sm);
}

.card-info {
  padding: 0 2px;
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
}
.manage-tabs :deep(.n-tab-pane) {
  padding: 16px 0;
}

.tab-content {
  padding: 0 16px;
}

.settings-content {
  padding: 24px 40px;
}

.tracking-item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.item-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.item-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.item-title {
  font-size: var(--text-lg);
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.item-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.no-data-text {
  color: var(--color-error);
  font-weight: bold;
}

.end-mark {
  color: var(--color-error) !important;
  font-weight: bold;
  margin-left: 2px;
}

.item-actions {
  margin-left: 16px;
  flex-shrink: 0;
}

.compact-list :deep(.n-list-item) {
  padding: 8px 0;
  border-bottom: none !important;
}

.compact-list :deep(.n-list-item)::after {
  display: none !important;
}

/* 强制隐藏 n-list 分割线 */
.compact-list :deep(.n-list-item__divider) {
  display: none !important;
}

.compact-list :deep(.n-list-item):not(:last-child) {
  border-bottom: none !important;
}

.compact-list :deep(.n-list) .n-list-item {
  border-bottom: 0 !important;
}

/* 禁用悬停效果 */
.compact-list :deep(.n-list-item):hover {
  background-color: transparent !important;
}

.compact-list :deep(.n-list-item--hover) {
  background-color: transparent !important;
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
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: var(--space-4);
  }
}
</style>