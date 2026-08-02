<script setup lang="ts">
/**
 * OrganizeHistoryModal — 整理历史弹窗
 * 分页浏览 + 重试 + 删除 + 清空
 */
import { ref, watch } from 'vue'
import { organizerApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'OrganizeHistoryModal' })

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const historyList = ref<any[]>([])
const historyLoading = ref(false)
const historyOffset = ref(0)
const historyHasMore = ref(true)
const historyStatusFilter = ref<string | undefined>(undefined)
const historySearch = ref('')

watch(() => props.modelValue, (val) => {
  if (val) {
    historyList.value = []
    historyOffset.value = 0
    historyHasMore.value = true
    historyStatusFilter.value = undefined
    historySearch.value = ''
    fetchHistory()
  }
})

async function fetchHistory() {
  historyLoading.value = true
  try {
    const data = await organizerApi.getHistory({
      limit: 30,
      offset: historyOffset.value,
      status: historyStatusFilter.value,
      search: historySearch.value || undefined,
    })
    const items = Array.isArray(data) ? data : (data?.items || data?.data || [])
    historyList.value = [...historyList.value, ...items]
    historyHasMore.value = items.length >= 30
    historyOffset.value += items.length
  } catch (e) {
    // 静默
  } finally {
    historyLoading.value = false
  }
}

function filterHistory(status?: string) {
  historyStatusFilter.value = status
  historyList.value = []
  historyOffset.value = 0
  historyHasMore.value = true
  fetchHistory()
}

function searchHistory() {
  historyList.value = []
  historyOffset.value = 0
  historyHasMore.value = true
  fetchHistory()
}

async function retryHistoryItem(historyId: number) {
  try {
    const data = await organizerApi.retryHistory(historyId)
    if (data?.success) {
      success('重试已启动: ' + (data.message || ''))
    } else {
      showError(data?.message || '重试失败')
    }
  } catch (e: any) {
    showError('重试失败: ' + e.message)
  }
}

async function deleteHistoryItem(historyId: number) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此整理记录吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await organizerApi.deleteHistory(historyId)
    success('已删除')
    historyList.value = historyList.value.filter((h: any) => h.id !== historyId)
  } catch (e) {
    showError('删除失败')
  }
}

async function clearAllHistory() {
  const ok = await confirm({ title: '确认清空', content: '确定要清空所有整理历史记录吗？此操作不可逆。', confirmColor: 'error' })
  if (!ok) return
  try {
    await organizerApi.clearHistory()
    success('历史记录已清空')
    historyList.value = []
    historyOffset.value = 0
    historyHasMore.value = false
  } catch (e) {
    showError('清空失败')
  }
}

function historyStatusColor(status: string): string {
  if (status === 'success') return 'success'
  if (status === 'failed' || status === 'error') return 'error'
  if (status === 'skipped') return 'warning'
  return 'default'
}

function historyStatusLabel(status: string): string {
  if (status === 'success') return '成功'
  if (status === 'failed' || status === 'error') return '失败'
  if (status === 'skipped') return '跳过'
  return status || '-'
}
</script>

<template>
  <v-dialog v-model="show" max-width="800" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-history</v-icon>
        整理历史
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="show = false" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 筛选 -->
        <div class="d-flex ga-2 mb-4 flex-wrap align-center">
          <v-text-field
            v-model="historySearch"
            label="搜索标题或文件名"
            density="compact"
            variant="outlined"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            class="org-search-field"
            @keyup.enter="searchHistory"
            @click:clear="historySearch = ''; searchHistory()"
          />
          <v-btn-toggle v-model="historyStatusFilter" mandatory density="compact" variant="outlined" divided>
            <v-btn size="small" :value="undefined" @click="filterHistory()">全部</v-btn>
            <v-btn size="small" value="success" @click="filterHistory('success')">成功</v-btn>
            <v-btn size="small" value="failed" @click="filterHistory('failed')">失败</v-btn>
            <v-btn size="small" value="skipped" @click="filterHistory('skipped')">跳过</v-btn>
          </v-btn-toggle>
          <v-spacer />
          <v-btn variant="tonal" color="error" size="small" prepend-icon="mdi-delete-sweep-outline" @click="clearAllHistory">清空</v-btn>
        </div>

        <v-skeleton-loader v-if="historyLoading && historyList.length === 0" type="list-item@5" />

        <div v-else-if="historyList.length > 0">
          <div class="org-history-item" v-for="item in historyList" :key="item.id">
            <div class="d-flex align-start justify-space-between">
              <div class="flex-grow-1 mr-2">
                <div class="d-flex align-center ga-2 mb-1">
                  <v-chip size="x-small" :color="historyStatusColor(item.status)" variant="tonal">
                    {{ historyStatusLabel(item.status) }}
                  </v-chip>
                  <span class="text-subtitle-2 font-weight-medium">{{ item.title || item.filename || '-' }}</span>
                </div>
                <div class="text-caption text-medium-emphasis">
                  <span v-if="item.filename">{{ item.filename }}</span>
                </div>
                <div class="d-flex ga-4 mt-1 text-caption text-medium-emphasis">
                  <span v-if="item.action_type">
                    <v-icon size="12" class="mr-1">mdi-swap-horizontal</v-icon>{{ item.action_type }}
                  </span>
                  <span v-if="item.processed_at">
                    <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>{{ item.processed_at }}
                  </span>
                </div>
                <div v-if="item.source_path" class="text-caption text-medium-emphasis mt-1 org-path-truncate">
                  <span class="font-weight-medium">源:</span> {{ item.source_path }}
                </div>
                <div v-if="item.target_path" class="text-caption text-medium-emphasis mt-1 org-path-truncate">
                  <span class="font-weight-medium">目标:</span> {{ item.target_path }}
                </div>
              </div>
              <div class="d-flex flex-column ga-1">
                <v-btn v-if="item.status === 'failed' || item.status === 'error'" size="small" variant="tonal" color="warning" prepend-icon="mdi-refresh" @click="retryHistoryItem(item.id)">重试</v-btn>
                <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteHistoryItem(item.id)">删除</v-btn>
              </div>
            </div>
          </div>

          <div v-if="historyHasMore" class="text-center pa-4">
            <v-btn variant="tonal" :loading="historyLoading" @click="fetchHistory">加载更多</v-btn>
          </div>
        </div>

        <div v-else class="text-center pa-8">
          <v-icon size="64" color="primary" class="mb-4">mdi-history</v-icon>
          <div class="text-h6 font-weight-medium">暂无整理历史</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="show = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
