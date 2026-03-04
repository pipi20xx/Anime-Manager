<script setup lang="ts">
import { 
  NSpace, NIcon, NSpin, NText, NButton, NModal, NInput,
  NList, NListItem, NAvatar, NPopconfirm, NTabs, NTabPane,
  NForm, NFormItem, NInputNumber, NTooltip, NDivider, NEmpty, NButtonGroup, NThing, NTag,
  NSwitch, NTimePicker
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

const {
  loading,
  trackingList,
  bangumiRaw,
  showManageModal,
  editingId,
  editBuffer,
  newSubject,
  importingBatch,
  mobileAgenda,
  calendarConfig,
  isTestingPush,
  fetchData,
  saveCalendarConfig,
  testCalendarPush,
  handleAutoImport,
  handleBatchImport,
  startEdit,
  saveEdit,
  handleAddSubject,
  refreshSubject,
  deleteSubject
} = useCalendar()
</script>

<template>
  <div class="calendar-mobile">
    <!-- Header -->
    <div class="mobile-header">
      <div class="header-left">
        <n-icon size="24" color="#63e2b7"><CalendarIcon /></n-icon>
        <span class="header-title">追剧日历</span>
      </div>
      <n-button circle quaternary @click="showManageModal = true">
        <template #icon><n-icon><ManageIcon /></n-icon></template>
      </n-button>
    </div>

    <!-- Agenda View -->
    <n-spin :show="loading" class="calendar-spin">
      <div class="agenda-container" v-if="mobileAgenda.length > 0">
        <div v-for="day in mobileAgenda" :key="day.dateStr" class="day-group">
          <div class="day-header">
            <span class="day-label">{{ day.dayLabel }}</span>
            <span class="day-date">{{ day.fullDate }}</span>
          </div>
          <div class="day-items">
            <div v-for="(item, idx) in day.items" :key="idx" class="agenda-item">
              <div class="item-time-bar"></div>
              <div class="item-content">
                <div class="item-title">{{ item.title }}</div>
                <div class="item-eps">
                  <n-tag v-for="ep in item.episodes" :key="ep.ep" size="small" :bordered="false" type="primary" class="ep-tag">
                    {{ ep.ep }}
                  </n-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-agenda">
        <n-empty description="近期没有更新的番剧" />
      </div>
    </n-spin>

    <!-- Manage Modal -->
    <n-modal v-model:show="showManageModal" preset="card" style="width: 100%; height: 100vh; margin: 0;" content-style="padding: 0; display: flex; flex-direction: column;" title="追踪管理">
      <n-tabs type="line" animated style="flex: 1; display: flex; flex-direction: column;">
        <n-tab-pane name="list" tab="正在追踪" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
          <div class="scroll-container">
            <n-list hoverable>
              <n-list-item v-for="sub in trackingList" :key="sub.id">
                <n-thing :title="sub.title">
                  <template #description>TMDB: {{ sub.tmdb_id }} | S{{ sub.season }}</template>
                  <template #header-extra>
                    <n-button-group size="tiny">
                      <n-button secondary type="primary" @click="refreshSubject(sub.id)"><template #icon><n-icon><RefreshIcon/></n-icon></template></n-button>
                      <n-popconfirm @positive-click="deleteSubject(sub.id)" positive-text="删" negative-text="取消">
                        <template #trigger>
                          <n-button secondary type="error"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
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
            <n-form-item label="TMDB ID"><n-input v-model:value="newSubject.tmdb_id" placeholder="ID" /></n-form-item>
            <n-form-item label="标题"><n-input v-model:value="newSubject.title" placeholder="标题" /></n-form-item>
            <n-form-item label="季号"><n-input-number v-model:value="newSubject.season" :min="1" style="width: 100%" /></n-form-item>
            <n-button type="primary" block @click="handleAddSubject">保存</n-button>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="push" tab="推送">
          <div style="padding: 16px">
            <n-form label-placement="top">
              <div style="margin-bottom: 24px; display: flex; align-items: center; gap: 8px">
                <n-icon size="18" color="#63e2b7"><NotifyIcon /></n-icon>
                <n-text strong>每日番剧播报</n-text>
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
                  block
                  :disabled="!calendarConfig.daily_push_enabled"
                  @update:formatted-value="saveCalendarConfig" 
                />
              </n-form-item>

              <n-divider dashed />

              <n-button 
                secondary 
                type="primary" 
                block 
                @click="testCalendarPush"
                :loading="isTestingPush"
              >
                <template #icon><n-icon><SendIcon /></n-icon></template>
                发送测试播报
              </n-button>

              <n-alert type="info" size="small" :show-icon="false" style="margin-top: 24px">
                系统将在设定时间推送今日播出清单。
              </n-alert>
            </n-form>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-modal>
  </div>
</template>

<style scoped>
.calendar-mobile { padding-bottom: 20px; display: flex; flex-direction: column; height: 100%; }
.mobile-header { display: flex; justify-content: space-between; align-items: center; padding: 0 4px 12px 4px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-title { font-size: 18px; font-weight: bold; }

.agenda-container { padding-bottom: 40px; }
.day-group { margin-bottom: 20px; }
.day-header { 
  display: flex; align-items: baseline; gap: 8px; 
  padding: 8px 12px; 
  background: var(--app-surface-inner);
  position: sticky; top: 0; z-index: 10;
  border-bottom: 1px solid var(--app-border-light);
}
.day-label { font-size: 16px; font-weight: bold; color: var(--n-primary-color); }
.day-date { font-size: 12px; color: #888; }

.day-items { padding: 8px 12px; }
.agenda-item { 
  display: flex; gap: 12px; margin-bottom: 12px; 
  background: var(--app-surface-card);
  padding: 10px; border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.item-time-bar { width: 4px; background: var(--n-primary-color); border-radius: 2px; }
.item-content { flex: 1; }
.item-title { font-weight: bold; font-size: 14px; margin-bottom: 6px; }
.item-eps { display: flex; gap: 4px; flex-wrap: wrap; }
.ep-tag { font-family: monospace; font-weight: bold; }

.scroll-container { flex: 1; overflow-y: auto; padding: 0 16px 16px; }
.empty-agenda { padding: 40px 0; text-align: center; }

.weekday-header { font-size: 12px; font-weight: bold; color: #888; margin: 12px 0 8px; }
.discover-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.discover-item { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 4px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 8px; }
.discover-name { font-size: 11px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; height: 28px; }
</style>
