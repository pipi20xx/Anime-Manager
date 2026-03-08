<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { 
  NModal, NButton, NSpace, NList, NListItem, NThing, NIcon, NTag, NPopselect
} from 'naive-ui'
import { DownloadOutlined as DownloadIcon, HistoryOutlined as HistoryIcon } from '@vicons/material'
import { useFeedItems } from '../../composables/modals/useFeedItems'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  feed: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  offset,
  hasMore,
  clientOptions,
  fetchItems,
  handleDownload,
  handleToggleHistory,
  handleRetryRecognition
} = useFeedItems(props)

const mobileListRef = ref<any>(null)

const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  if (!target || loading.value || !hasMore.value) return
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50) {
    fetchItems(true)
  }
}

const setupScrollListener = () => {
  nextTick(() => {
    // Mobile list container scroll
    const el = mobileListRef.value
    if (el) {
      el.removeEventListener('scroll', handleScroll)
      el.addEventListener('scroll', handleScroll)
    }
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems(false)
    setupScrollListener()
  }
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
    :title="`订阅源详情`"
  >
    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
      <div class="mobile-list-container" ref="mobileListRef">
        <n-list hoverable>
          <n-list-item v-for="item in items" :key="item.guid">
             <template #prefix>
                <div class="status-dot" :class="{ downloaded: item.is_downloaded }"></div>
             </template>
             <n-thing content-style="margin-top: 6px;">
               <template #header>
                  <div class="item-title">{{ item.title }}</div>
               </template>
               <template #description>
                 <div class="item-desc-text" v-if="item.description">{{ item.description }}</div>
                 <div class="item-pub-date">{{ item.pub_date }}</div>
               </template>
               
               <div class="metadata-container">
                 <!-- Recognition Info -->
                 <div v-if="item.tmdb_title" class="tmdb-preview">
                    <span class="icon">🎯</span>
                    <span class="text">{{ item.tmdb_title }}</span>
                 </div>

                 <n-space size="small" :inline="true" style="margin-top: 6px; flex-wrap: wrap;">
                    <!-- Status Tags -->
                    <n-tag v-if="item.in_subscription" type="info" size="tiny" secondary>已订阅</n-tag>
                    <n-tag v-if="item.episode_collected" type="success" size="tiny" secondary>已下载</n-tag>

                    <!-- Recognition Tags -->
                    <template v-if="item.recognition_done && item.tmdb_id">
                      <n-tag type="primary" size="tiny" round>ID: {{ item.tmdb_id }}</n-tag>
                      <n-tag type="info" size="tiny" quaternary>
                        {{ item.media_type === 'movie' ? '🎬 电影' : '📺 剧集' }}
                      </n-tag>
                      <n-tag v-if="item.media_type === 'tv'" type="info" size="tiny" round>
                        S{{ item.season || 1 }} E{{ item.episode || '-' }}
                      </n-tag>
                    </template>
                    <n-tag v-else-if="item.recognition_done" type="warning" size="tiny" quaternary>未命中</n-tag>

                    <!-- Spec Tags -->
                    <n-tag v-if="item.team" size="tiny" quaternary type="info">{{ item.team }}</n-tag>
                    <n-tag v-if="item.resolution" size="tiny" quaternary type="warning">{{ item.resolution }}</n-tag>
                    <n-tag v-if="item.video_effect" size="tiny" quaternary type="success">{{ item.video_effect }}</n-tag>
                    <n-tag v-if="item.video_encode" size="tiny" quaternary>{{ item.video_encode }}</n-tag>
                    <n-tag v-if="item.subtitle" size="tiny" quaternary type="error">{{ item.subtitle }}</n-tag>
                 </n-space>
               </div>
             </n-thing>
             <template #suffix>
                <div style="display: flex; flex-direction: column; gap: 10px; padding-left: 8px;">
                   <n-popselect :options="clientOptions" @update:value="val => handleDownload(item, val)" trigger="click">
                     <n-button v-bind="getButtonStyle('iconPrimary')" size="small"><template #icon><n-icon><DownloadIcon/></n-icon></template></n-button>
                   </n-popselect>
                   <n-button 
                     v-bind="getButtonStyle('icon')"
                     size="small"
                     :type="item.is_downloaded ? 'warning' : 'info'"
                     @click="handleToggleHistory(item, !item.is_downloaded)"
                   >
                     <template #icon><n-icon><HistoryIcon/></n-icon></template>
                   </n-button>
                </div>
             </template>
          </n-list-item>
        </n-list>
        <div v-if="loading" style="padding: 10px; text-align: center; color: #666;">加载中...</div>
        <div v-if="!loading && items.length === 0" style="padding: 20px; text-align: center; color: #666;">暂无数据</div>
      </div>
    </div>
    
    <template #footer>
      <n-space justify="space-between" align="center">
        <div style="font-size: 12px; color: #666">
          已加载 {{ items.length }} 条 <span v-if="loading && offset > 0">...</span>
        </div>
        <n-space>
          <n-button type="warning" secondary @click="handleRetryRecognition" :loading="loading" size="small">
             重试识别
          </n-button>
          <n-button @click="emit('update:show', false)" size="small">关闭</n-button>
        </n-space>
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
  background: #444;
  margin-top: 10px;
}
.status-dot.downloaded {
  background: var(--n-success-color);
  box-shadow: 0 0 6px var(--n-success-color);
}

.item-title {
  font-size: 14px;
  font-weight: bold;
  line-height: 1.4;
  word-break: break-all;
  color: var(--n-text-color-1);
}

.item-desc-text {
  font-size: 11px;
  color: #777;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-pub-date {
  font-size: 10px;
  color: #555;
  margin-top: 4px;
  font-family: monospace;
}

.tmdb-preview {
  margin-top: 8px;
  background: var(--app-surface-inner);
  border: 1px solid var(--app-border-light);
  padding: 4px 8px;
  border-radius: var(--button-border-radius, 4px);
  display: flex;
  align-items: center;
  gap: 6px;
}
.tmdb-preview .icon { font-size: 12px; }
.tmdb-preview .text { font-size: 12px; font-weight: bold; color: var(--n-primary-color); }

.metadata-container {
  display: flex;
  flex-direction: column;
}
</style>
