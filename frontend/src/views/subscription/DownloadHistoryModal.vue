<script setup lang="ts">
/**
 * DownloadHistoryModal — 下载记录弹窗
 * Feed 条目浏览 + 规则下载记录
 */
import { ref, computed, watch } from 'vue'
import { subscriptionApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{
  show: boolean
  feeds?: any[]
  clients?: any[]
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const items = ref<any[]>([])
const loading = ref(false)
const keyword = ref('')
const selectedFeedIds = ref<number[]>([])

watch(() => props.show, (v) => {
  if (v) fetchItems()
})

async function fetchItems() {
  loading.value = true
  try {
    const data = await subscriptionApi.getDownloadHistory()
    let filtered: any[] = Array.isArray(data) ? data : (data?.items || data?.data || [])
    if (selectedFeedIds.value.length > 0) {
      filtered = filtered.filter((item: any) => selectedFeedIds.value.includes(item.feed_id))
    }
    if (keyword.value) {
      const kw = keyword.value.toLowerCase()
      filtered = filtered.filter((item: any) =>
        (item.title || '').toLowerCase().includes(kw) ||
        (item.raw_title || '').toLowerCase().includes(kw)
      )
    }
    items.value = filtered
  } catch { items.value = [] }
  finally { loading.value = false }
}

async function deleteItem(guid: string) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此记录吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.deleteDownloadHistory(guid)
    success('已删除')
    items.value = items.value.filter((i: any) => (i.guid || i.id) !== guid)
  } catch { showError('删除失败') }
}
</script>

<template>
  <v-dialog :model-value="show" max-width="800" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-format-list-bulleted</v-icon>
        下载记录
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <div class="d-flex ga-2 mb-4 flex-wrap">
          <v-text-field
            v-model="keyword" placeholder="搜索关键词..." prepend-inner-icon="mdi-magnify"
            density="compact" hide-details variant="outlined" class="flex-grow-1"
            @keyup.enter="fetchItems"
          />
          <v-select
            v-if="feeds && feeds.length > 0"
            v-model="selectedFeedIds"
            :items="feeds.map((f: any) => ({ title: f.title || f.url, value: f.id }))"
            multiple chips clearable density="compact" hide-details variant="outlined"
            placeholder="筛选站点" class="flex-grow-1" @update:model-value="fetchItems"
          />
          <v-btn variant="tonal" @click="fetchItems" prepend-icon="mdi-refresh">刷新</v-btn>
        </div>

        <v-skeleton-loader v-if="loading" type="list-item@5" />

        <template v-else-if="items.length > 0">
          <div class="feed-item-card mb-2" v-for="item in items" :key="item.guid || item.id">
            <div class="d-flex align-start justify-space-between">
              <div class="flex-grow-1 mr-2">
                <div class="text-body-2 font-weight-medium">{{ item.raw_title || item.title }}</div>
                <div class="text-caption text-medium-emphasis mt-1">
                  <span v-if="item.feed_title">{{ item.feed_title }} · </span>
                  {{ item.download_at ? new Date(item.download_at).toLocaleString() : '' }}
                </div>
              </div>
              <v-chip v-if="item.status" size="x-small" :color="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'info'" variant="tonal">
                {{ item.status || '已推送' }}
              </v-chip>
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteItem(item.guid || item.id)">删除</v-btn>
            </div>
          </div>
        </template>

        <div v-else class="text-center pa-6">
          <v-icon size="48" color="primary" class="mb-3">mdi-inbox-outline</v-icon>
          <div class="text-body-2 text-medium-emphasis">暂无下载记录</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
