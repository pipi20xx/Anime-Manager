<script setup lang="ts">
import { 
  NSpace, NIcon, NSpin, NText, NButton, NModal, NInput,
  NList, NListItem, NAvatar, NPopconfirm, NTabs, NTabPane,
  NForm, NFormItem, NInputNumber, NTooltip, NDivider, NEmpty, NButtonGroup,
  NSwitch, NTimePicker
} from 'naive-ui'
import { 
  CalendarMonthOutlined as CalendarIcon,
  ChevronLeftOutlined as PrevIcon,
  ChevronRightOutlined as NextIcon,
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
  isTestingPush,
  getEpisodeRange,
  fetchData,
  saveCalendarConfig,
  testCalendarPush,
  handleAutoImport,
  handleBatchImport,
  startEdit,
  saveEdit,
  handleAddSubject,
  refreshSubject,
  refreshAllSubjects,
  deleteSubject
} = useCalendar()
</script>

<template>
  <div class="calendar-page">
    <div class="calendar-header-bar">
      <!-- 左侧：标题与管理 -->
      <n-space align="center" :size="12">
        <div class="title-section-new">
          <n-icon size="22" color="#63e2b7" style="margin-top: 4px"><CalendarIcon /></n-icon>
          <span class="header-title-text">追剧日历</span>
        </div>
        <n-button quaternary circle size="small" @click="showManageModal = true" title="管理追踪">
          <template #icon><n-icon><ManageIcon /></n-icon></template>
        </n-button>
      </n-space>
      
      <!-- 右侧：导航控件 -->
      <n-space align="center" :size="8">
        <n-button quaternary circle size="small" @click="viewDate = new Date(viewDate.setMonth(viewDate.getMonth() - 1))">
          <template #icon><n-icon><PrevIcon /></n-icon></template>
        </n-button>
        <div class="current-month-display">
          {{ viewDate.getFullYear() }}年{{ viewDate.getMonth() + 1 }}月
        </div>
        <n-button quaternary circle size="small" @click="viewDate = new Date(viewDate.setMonth(viewDate.getMonth() + 1))">
          <template #icon><n-icon><NextIcon /></n-icon></template>
        </n-button>
        <n-divider vertical style="margin: 0 8px" />
        <n-button secondary size="tiny" @click="viewDate = new Date()" style="padding: 0 12px; height: 24px">
          今天
        </n-button>
      </n-space>
    </div>

    <n-spin :show="loading" class="calendar-spin">
      <div class="mp-calendar-wrapper">
        <div class="mp-calendar-head">
          <div v-for="w in ['一','二','三','四','五','六','日']" :key="w" class="head-cell">{{ w }}</div>
        </div>
        <div class="mp-calendar-grid">
          <div v-for="cell in calendarGrid" :key="cell.dateStr" class="grid-cell" :class="{ 'is-today': cell.isToday, 'off-month': !cell.isCurrentMonth }">
            <div class="cell-top">
              <span class="day-num">{{ cell.day }}</span>
              <span v-if="cell.isToday" class="today-dot"></span>
            </div>
            <div class="cell-content">
              <n-tooltip v-for="item in cell.items" :key="item.id + '-' + item.episodeDisplay" trigger="hover">
                <template #trigger>
                  <div class="anime-entry-line">
                    <div class="status-dot"></div>
                    <span class="anime-name-text">{{ item.title }}</span>
                    <span class="ep-count-tag" v-html="item.episodeDisplay"></span>
                  </div>
                </template>
                <div v-html="item.epDetails"></div>
              </n-tooltip>
            </div>
          </div>
        </div>
      </div>
    </n-spin>

    <n-modal v-model:show="showManageModal" preset="card" style="width: 95%; max-width: 1200px" content-style="padding: 0" title="追踪管理">
      <n-tabs type="line" animated style="height: 80vh">
        <n-tab-pane name="list" tab="正在追踪" style="height: 100%; display: flex; flex-direction: column">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; padding: 0 16px">
            <n-text depth="3" style="font-size: 12px">共 {{ trackingList.length }} 个追踪项</n-text>
            <n-button type="primary" size="small" @click="refreshAllSubjects">
              全部刷新
            </n-button>
          </div>
          <div class="scroll-container-full">
            <n-list hoverable class="compact-list">
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
                        <n-button v-bind="getButtonStyle('ghost')" @click="editingId = null">取消</n-button>
                      </n-space>
                    </template>
                    <template v-else>
                      <n-button-group>
                        <n-button secondary size="small" type="info" @click="startEdit(sub)" title="编辑"><template #icon><n-icon><EditIcon /></n-icon></template></n-button>
                        <n-button secondary size="small" type="primary" @click="refreshSubject(sub.id)" title="同步"><template #icon><n-icon><RefreshIcon /></n-icon></template></n-button>
                        <n-popconfirm 
                          positive-text="确认"
                          negative-text="取消"
                          @positive-click="deleteSubject(sub.id)"
                        >
                          <template #trigger><n-button secondary size="small" type="error" title="删除"><template #icon><n-icon><DeleteIcon /></n-icon></template></n-button></template>
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

        <n-tab-pane name="discover" tab="从放送表导入" style="height: 100%; display: flex; flex-direction: column">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; padding: 0 16px">
            <n-text depth="3" style="font-size: 12px">点击下方番剧可自动同步至日历</n-text>
            <n-button type="primary" size="small" :loading="importingBatch" @click="handleBatchImport">
              导入全周番剧
            </n-button>
          </div>
          <div class="discover-scroll">
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
            <n-form-item label="TMDB ID"><n-input v-model:value="newSubject.tmdb_id" placeholder="例如: 1399" /></n-form-item>
            <n-form-item label="标题"><n-input v-model:value="newSubject.title" placeholder="日历显示的标题" /></n-form-item>
            <n-form-item label="季号"><n-input-number v-model:value="newSubject.season" :min="1" /></n-form-item>
            <n-button v-bind="getButtonStyle('primary')" block @click="handleAddSubject">保存追踪</n-button>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="settings" tab="推送设置">
          <div style="padding: 24px 40px">
            <n-form label-placement="left" label-width="120">
              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="20" color="#63e2b7"><NotifyIcon /></n-icon>
                <n-text strong style="font-size: 16px">每日播报设置</n-text>
              </div>
              
              <n-form-item label="启用每日播报">
                <n-switch v-model:value="calendarConfig.daily_push_enabled" @update:value="saveCalendarConfig" />
              </n-form-item>
              
              <n-form-item label="推送时间" :style="{ opacity: calendarConfig.daily_push_enabled ? 1 : 0.5 }">
                <n-time-picker 
                  v-model:formatted-value="calendarConfig.push_time" 
                  value-format="HH:mm" 
                  format="HH:mm" 
                  size="small"
                  style="width: 140px"
                  :disabled="!calendarConfig.daily_push_enabled"
                  @update:formatted-value="saveCalendarConfig" 
                />
              </n-form-item>

              <n-divider dashed />
              
              <n-form-item label="状态测试">
                <n-button v-bind="getButtonStyle('secondary')" @click="testCalendarPush" :loading="isTestingPush">
                  发送测试播报
                </n-button>
              </n-form-item>

              <n-alert type="info" size="small" :show-icon="false" style="margin-top: 12px">
                系统将在设定时间通过 Telegram 推送今日播出清单。
              </n-alert>
            </n-form>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-modal>
  </div>
</template>

<style scoped>
.calendar-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--app-bg-color);
  padding: 12px;
}

.calendar-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  background: var(--app-surface-inner);
  padding: 6px 16px;
  border-radius: var(--card-border-radius);
  border: 1px solid var(--app-border-light);
  min-height: 48px;
}

.title-section-new {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title-text {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--n-text-color-1);
}

.current-month-display {
  font-size: 15px;
  font-weight: 700;
  min-width: 90px;
  text-align: center;
  font-family: var(--font-family-base);
  color: var(--n-text-color-2);
}

.mp-calendar-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius);
  overflow: hidden;
  background: var(--app-surface-card);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.mp-calendar-head {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: var(--app-surface-inner);
  border-bottom: 1px solid var(--app-border-light);
}

.head-cell {
  padding: 10px;
  text-align: center;
  font-weight: 800;
  font-size: 13px;
  color: var(--n-text-color-3);
  text-transform: uppercase;
}

.mp-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  grid-template-rows: repeat(6, 1fr);
  flex: 1;
  gap: 1px;
  background: var(--app-border-light);
}

.grid-cell {
  background: var(--app-surface-card);
  padding: 6px;
  display: flex;
  flex-direction: column;
  min-height: 80px;
  min-width: 0;
  transition: background 0.2s;
}

.grid-cell:hover {
  background: rgba(255, 255, 255, 0.02);
}

.grid-cell.is-today {
  background: rgba(99, 226, 183, 0.06);
}

.grid-cell.off-month {
  background: rgba(0, 0, 0, 0.25);
  opacity: 0.4;
}

.day-num {
  font-size: 14px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--n-text-color-2);
}

.today-dot {
  width: 6px;
  height: 6px;
  background: var(--n-primary-color);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--n-primary-color);
}

.cell-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 4px;
}

.anime-entry-line {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid transparent;
  transition: all 0.2s;
  min-width: 0;
}

.anime-entry-line:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(99, 226, 183, 0.3);
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--n-primary-color);
  box-shadow: 0 0 4px var(--n-primary-color);
  flex-shrink: 0;
}
.anime-name-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; color: var(--n-text-color-2); }
.ep-count-tag { font-size: 9px; background: rgba(99, 226, 183, 0.15); color: #63e2b7; padding: 0 3px; border-radius: 3px; font-weight: bold; flex-shrink: 0; }
.discover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
  padding: 4px;
}

.scroll-container-full {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px;
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
  font-size: 14px;
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.item-desc {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.no-data-text {
  color: #ff6b6b;
  font-weight: bold;
}

.end-mark {
  color: #ff6b6b !important;
  font-weight: bold;
  margin-left: 2px;
}

.item-actions {
  margin-left: 16px;
  flex-shrink: 0;
}

.compact-list :deep(.n-list-item) {
  padding: 8px 0;
}

.discover-scroll {
  height: 100%;
  overflow-y: auto;
  padding: 0 16px 16px;
}

.discover-item { display: flex; align-items: center; gap: 8px; padding: 6px; border-radius: 6px; background: rgba(255, 255, 255, 0.03); cursor: pointer; transition: background 0.2s; min-width: 0; }
.discover-item:hover { background: rgba(99, 226, 183, 0.1); }
.discover-name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.calendar-spin { height: 100%; }
</style>