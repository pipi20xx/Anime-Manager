<script setup lang="ts">
import { watch } from 'vue'
import { 
  NModal, NList, NListItem, NThing, NIcon, NTag, NButton, NSpace, NSpin, NEmpty, NPopselect
} from 'naive-ui'
import { DownloadOutlined as DownloadIcon, HistoryOutlined as HistoryIcon } from '@vicons/material'
import { useRulePreview } from '../../composables/modals/useRulePreview'

const props = defineProps<{
  show: boolean
  ruleData: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  clientOptions,
  fetchPreview,
  handleDownload,
  handleToggleHistory
} = useRulePreview(props)

watch(() => props.show, (newVal) => {
  if (newVal) fetchPreview()
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 100%; height: 100vh; margin: 0;"
    content-style="padding: 0; display: flex; flex-direction: column;"
    :segmented="{ content: true, footer: 'soft' }"
    title="匹配结果预览"
  >
    <n-spin :show="loading" style="flex: 1; display: flex; flex-direction: column;" content-style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
      <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <div class="mobile-list-container" v-if="items.length > 0">
           <n-list hoverable>
              <n-list-item v-for="item in items" :key="item.guid">
                 <template #prefix>
                    <div class="status-dot" :class="{ downloaded: item.is_downloaded }"></div>
                 </template>
                 <n-thing :title="item.title" content-style="margin-top: 4px">
                   <template #description>
                      <n-tag size="small" type="info" bordered={false} style="margin-top: 4px;">{{ item.feed_name }}</n-tag>
                   </template>
                 </n-thing>
                 <template #suffix>
                    <div style="display: flex; flex-direction: column; gap: 8px; justify-content: center;">
                       <n-popselect :options="clientOptions" @update:value="val => handleDownload(item, val)" trigger="click">
                         <n-button size="small" circle type="primary" secondary><template #icon><n-icon><DownloadIcon/></n-icon></template></n-button>
                       </n-popselect>
                       <n-button 
                         size="small" 
                         circle 
                         :type="item.is_downloaded ? 'warning' : 'info'" 
                         secondary 
                         @click="handleToggleHistory(item, !item.is_downloaded)"
                       >
                         <template #icon><n-icon><HistoryIcon/></n-icon></template>
                       </n-button>
                    </div>
                 </template>
              </n-list-item>
           </n-list>
        </div>

        <n-empty v-else-if="!loading" description="未匹配到条目" style="margin-top: 80px" />
      </div>
    </n-spin>
    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)" size="small">返回</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.mobile-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  margin-top: 6px;
}
.status-dot.downloaded {
  background: var(--n-success-color);
  box-shadow: 0 0 4px var(--n-success-color);
}
</style>
