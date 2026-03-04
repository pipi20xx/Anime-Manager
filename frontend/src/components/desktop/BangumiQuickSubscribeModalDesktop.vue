<script setup lang="ts">
import { 
  NModal, NButton, NSpace, NIcon, NCheckbox, NCheckboxGroup,
  NImage, NScrollbar, NSelect, NInput, NInputGroup,
  NSpin, NEmpty, NGrid, NGi, NTag, NTabs, NTabPane
} from 'naive-ui'
import {
  FlashOnOutlined as FlashIcon,
  CheckCircleOutlined as CheckIcon,
  DeleteOutlined as DeleteIcon
} from '@vicons/material'
import { useBangumiQuickSub } from '../../composables/components/useBangumiQuickSub'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits(['update:show', 'finish'])

const {
  loading, submitting, weeklyData, templates, selectedTemplate, selectedIds,
  manualId, manualItems,
  fetchData, addManualItem, handleBatchSubscribe
} = useBangumiQuickSub(props, emit)
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="v => emit('update:show', v)"
    preset="card"
    style="width: 1000px; max-width: 95vw;"
  >
    <template #header>
      <div class="header-box">
        <n-icon size="24" color="#f06292"><FlashIcon /></n-icon>
        <div>
          <div class="title">Bangumi 一键订阅</div>
          <div class="subtitle">快速同步全周放送列表</div>
        </div>
      </div>
    </template>

    <n-scrollbar style="max-height: 65vh; padding-right: 10px;">
      <n-spin :show="loading">
        <n-space vertical size="large">
          <n-grid :cols="2" :x-gap="20">
            <n-gi>
              <div class="label">套用预设预设</div>
              <n-select v-model:value="selectedTemplate" :options="templates.map(t => ({label: t.name, value: t.id}))" />
            </n-gi>
            <n-gi>
              <div class="label">手动添加 Bangumi ID</div>
              <n-input-group>
                <n-input v-model:value="manualId" @keypress.enter="addManualItem" />
                <n-button type="primary" @click="addManualItem">添加</n-button>
              </n-input-group>
            </n-gi>
          </n-grid>

          <n-checkbox-group v-model:value="selectedIds">
            <n-tabs type="line" animated>
              <n-tab-pane v-for="day in weeklyData" :key="day.weekday.id" :name="day.weekday.id" :tab="day.weekday.cn">
                <div class="anime-grid">
                  <div v-for="item in day.items" :key="item.id" class="anime-item" :class="{ 'is-subbed': item.isSubscribed }">
                    <n-checkbox :value="item.id" :disabled="item.isSubscribed" />
                    <div class="anime-card">
                      <n-image :src="item.image" class="poster" preview-disabled />
                      <div class="info">
                        <div class="name">{{ item.title }}</div>
                        <n-tag v-if="item.isSubscribed" size="tiny" type="success">已订阅</n-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </n-tab-pane>
            </n-tabs>
          </n-checkbox-group>
        </n-space>
      </n-spin>
    </n-scrollbar>

    <template #action>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :disabled="selectedIds.length === 0" @click="handleBatchSubscribe">
          确认批量订阅 ({{ selectedIds.length }})
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.header-box { display: flex; align-items: center; gap: 10px; }
.title { font-size: 18px; font-weight: bold; }
.subtitle { font-size: 12px; color: #888; }
.label { font-size: 12px; margin-bottom: 8px; font-weight: bold; }
.anime-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.anime-item { display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--app-surface-inner); border-radius: 8px; }
.anime-item.is-subbed { opacity: 0.5; }
.anime-card { flex: 1; display: flex; gap: 8px; align-items: center; }
.poster { width: 40px; height: 55px; border-radius: 4px; object-fit: cover; }
.info { flex: 1; overflow: hidden; }
.name { font-weight: bold; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
