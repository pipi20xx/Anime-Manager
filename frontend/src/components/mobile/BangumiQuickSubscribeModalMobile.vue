<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NButton, NSpace, NIcon, NCheckbox, NCheckboxGroup,
  NImage, NScrollbar, NSelect,
  NSpin, NEmpty, NTag, NTabs, NTabPane, NList, NListItem, NThing
} from 'naive-ui'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import {
  FlashOnOutlined as FlashIcon,
  ArrowBackOutlined as BackIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import { useBangumiQuickSub } from '../../composables/components/useBangumiQuickSub'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits(['update:show', 'finish'])

const {
  loading, weeklyData, templates, selectedTemplate, selectedIds,
  manualId, fetchData, addManualItem, handleBatchSubscribe,
  renderReady, activeTab,
  selectAll, deselectAll
} = useBangumiQuickSub(props, emit)
</script>

<template>
  <AppGlassModal 
    appearance-key="bangumi-quick-subscribe-modal"
    :show="show" 
    @update:show="v => emit('update:show', v)"
    class="mobile-fullscreen-modal"
  >
    <template #header>
      <div class="mobile-modal-header">
        <n-button v-bind="getButtonStyle('iconPrimary')" @click="emit('update:show', false)">
          <template #icon><n-icon><BackIcon/></n-icon></template>
        </n-button>
        <span class="title">Bangumi 一键订阅</span>
      </div>
    </template>

    <div class="mobile-bangumi-container">
      <n-spin :show="loading">
        <div class="mobile-tools">
          <AppSelectField v-model:value="selectedTemplate" label="套用预设" :options="templates.map(t => ({label: t.name, value: t.id}))" placeholder="选择预设" clearable />
          <AppTextField v-model:value="manualId" label="手动添加 Bangumi ID" placeholder="输入 ID" style="margin-top: 8px">
            <template #suffix>
              <n-button @click="addManualItem">添加</n-button>
            </template>
          </AppTextField>
        </div>

        <n-checkbox-group v-model:value="selectedIds" v-if="renderReady && weeklyData.length > 0">
          <n-tabs type="line" animated justify-content="space-evenly" v-model:value="activeTab">
            <n-tab-pane v-for="day in weeklyData" :key="day.weekday.id" :name="day.weekday.id" :tab="day.weekday.cn">
              <div class="mobile-anime-list">
                <div v-for="item in day.items" :key="item.id" class="mobile-anime-card" :class="{ 'is-subbed': item.isSubscribed }">
                  <n-checkbox :value="item.id" :disabled="item.isSubscribed" />
                  <div class="anime-content">
                    <n-image :src="item.image" class="mobile-poster" preview-disabled />
                    <div class="anime-info">
                      <div class="name">{{ item.title }}</div>
                      <n-tag v-if="item.isSubscribed" size="tiny" type="success" round>已订阅</n-tag>
                    </div>
                  </div>
                </div>
              </div>
            </n-tab-pane>
          </n-tabs>
        </n-checkbox-group>
      </n-spin>
    </div>

    <template #footer>
      <n-space>
        <n-button @click="selectAll">全选</n-button>
        <n-button @click="deselectAll">取消全选</n-button>
        <n-button block type="primary" :disabled="selectedIds.length === 0" @click="handleBatchSubscribe">
          批量订阅 ({{ selectedIds.length }} 个)
        </n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.mobile-fullscreen-modal {
  width: 100vw !important;
  height: 100vh !important;
  margin: 0 !important;
}
.mobile-modal-header { display: flex; align-items: center; gap: 8px; }
.mobile-modal-header .title { font-weight: bold; font-size: 16px; }

.mobile-bangumi-container { height: calc(100vh - 160px); overflow-y: auto; }
.mobile-tools { padding: 12px; background: var(--app-surface-card-mixed); }

.mobile-anime-list { display: flex; flex-direction: column; gap: 8px; padding: 12px; }
.mobile-anime-card {
  display: flex; align-items: center; gap: 12px; padding: 10px;
  background: var(--app-surface-card-mixed); border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.mobile-anime-card.is-subbed { opacity: var(--opacity-secondary); }
.anime-content { flex: 1; display: flex; gap: 12px; align-items: center; }
.mobile-poster { width: 45px; height: 60px; border-radius: 4px; object-fit: cover; }
.anime-info .name { font-weight: bold; font-size: 13px; line-height: 1.3; margin-bottom: 4px; }
</style>
