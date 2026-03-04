<script setup lang="ts">
import { watch, ref } from 'vue'
import { 
  NModal, NSpace, NButton, NIcon, NTag, NSwitch, NVirtualList, NSelect, NSpin
} from 'naive-ui'
import {
  PauseCircleRound as PauseIcon,
  PlayCircleRound as PlayIcon,
  DeleteSweepRound as ClearIcon,
  VerticalAlignBottomRound as ScrollIcon,
  CloseRound as CloseIcon,
  OpenInNewRound as OpenIcon,
  SettingsRound as SettingsIcon
} from '@vicons/material'
import { useLogConsole } from '../../composables/components/useLogConsole'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])

const {
  consoleLogs,
  isPaused,
  autoScroll,
  virtualListInst,
  socketStatus,
  logDates,
  selectedDate,
  isLoadingHistory,
  logSource,
  handleSourceChange,
  handleDateChange,
  scrollToTop,
  clearConsole,
  openFullLog
} = useLogConsole()

const showSettings = ref(false)

const close = () => {
  emit('update:show', false)
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    setTimeout(() => {
      scrollToTop()
    }, 100)
  }
})
</script>

<template>
  <n-modal :show="show" @update:show="val => emit('update:show', val)" style="width: 100%; height: 100vh; margin: 0; border-radius: 0;">
    <div class="mobile-console">
      <!-- Header -->
      <div class="console-header">
        <n-button quaternary circle @click="close">
          <template #icon><n-icon><CloseIcon /></n-icon></template>
        </n-button>
        <div class="header-title">
          <span class="title-text">{{ selectedDate ? `历史: ${selectedDate}` : '实时日志' }}</span>
          <div class="status-indicator">
             <div class="dot" :class="{ active: socketStatus === 'connected' }"></div>
             <span>{{ socketStatus === 'connected' ? '就绪' : '断开' }}</span>
          </div>
        </div>
        <n-space>
           <n-button quaternary circle @click="autoScroll = !autoScroll" :type="autoScroll ? 'primary' : 'default'">
             <template #icon><n-icon><ScrollIcon /></n-icon></template>
           </n-button>
           <n-button quaternary circle @click="showSettings = !showSettings" :type="showSettings ? 'primary' : 'default'">
             <template #icon><n-icon><SettingsIcon /></n-icon></template>
           </n-button>
        </n-space>
      </div>

      <!-- Logs -->
      <div class="console-body">
        <n-spin :show="isLoadingHistory" class="log-spin">
          <div v-if="consoleLogs.length === 0 && !isLoadingHistory" class="empty-tip">
            等待日志...
          </div>
          <n-virtual-list
            ref="virtualListInst"
            class="log-list"
            :items="consoleLogs"
            :item-size="20"
            key-field="id"
          >
            <template #default="{ item }">
              <div class="log-line">{{ item.content }}</div>
            </template>
          </n-virtual-list>
        </n-spin>
      </div>

      <!-- Settings Overlay (Manual implementation to avoid z-index issues) -->
      <div class="settings-overlay" v-if="showSettings">
         <div class="settings-header-row">
            <span class="settings-title">控制台设置</span>
            <n-button size="small" quaternary circle @click="showSettings = false"><template #icon><n-icon><CloseIcon/></n-icon></template></n-button>
         </div>
         
         <div class="settings-list">
            <div class="setting-row">
               <span class="setting-label">暂停更新</span>
               <n-switch v-model:value="isPaused" />
            </div>
            
            <div class="setting-row">
               <span class="setting-label">历史日志回溯</span>
               <n-select 
                  v-model:value="selectedDate"
                  placeholder="选择日期"
                  size="small"
                  style="width: 180px;"
                  :options="[
                    { label: '🔴 实时日志流', value: null },
                    ...logDates.map(d => ({ label: `📅 ${d}`, value: d }))
                  ]"
                  @update:value="handleDateChange"
                />
            </div>

            <div class="setting-row" v-if="selectedDate">
               <span class="setting-label">历史数据源</span>
               <n-switch 
                  v-model:value="logSource" 
                  checked-value="db" 
                  unchecked-value="file"
                  @update:value="handleSourceChange"
                >
                  <template #checked>审计</template>
                  <template #unchecked>全量</template>
                </n-switch>
            </div>

            <div class="setting-actions">
               <n-button secondary block @click="openFullLog" style="margin-bottom: 12px;">
                  <template #icon><n-icon><OpenIcon /></n-icon></template> 查看导出
               </n-button>
               <n-button secondary block type="error" @click="clearConsole">
                  <template #icon><n-icon><ClearIcon /></n-icon></template> 清空
               </n-button>
            </div>
         </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.mobile-console { background: #101014; height: 100%; display: flex; flex-direction: column; position: relative; }
.console-header { 
  display: flex; justify-content: space-between; align-items: center; 
  padding: 8px 12px; background: #18181c; border-bottom: 1px solid rgba(255,255,255,0.1); 
  z-index: 20;
}
.header-title { display: flex; flex-direction: column; align-items: center; }
.title-text { font-weight: bold; font-size: 14px; }
.status-indicator { display: flex; align-items: center; gap: 4px; font-size: 10px; color: #666; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #666; }
.dot.active { background: var(--n-primary-color); box-shadow: 0 0 4px var(--n-primary-color); }

.console-body { flex: 1; overflow: hidden; background: #000; padding: 4px; position: relative; z-index: 10; display: flex; flex-direction: column; }
.log-spin { flex: 1; display: flex; flex-direction: column; height: 100%; }
:deep(.n-spin-content) { flex: 1; display: flex; flex-direction: column; height: 100%; }
.log-list { flex: 1; height: 100% !important; }
.log-line { 
  font-family: monospace; font-size: 11px; line-height: 1.4; color: #ccc; 
  padding: 2px 4px; word-break: break-all; white-space: pre-wrap; 
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.empty-tip { color: #666; text-align: center; margin-top: 40px; }

/* Settings Overlay */
.settings-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: #18181c; /* Match dark theme modal bg */
  border-top: 1px solid rgba(255,255,255,0.15);
  border-radius: 16px 16px 0 0;
  z-index: 50; /* Higher than content */
  box-shadow: 0 -4px 20px rgba(0,0,0,0.5);
  padding: 16px;
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.settings-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.settings-title { font-weight: bold; font-size: 16px; color: #fff; }

.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.setting-label { font-weight: bold; color: #ccc; font-size: 14px; }
.setting-actions { margin-top: 24px; }
</style>