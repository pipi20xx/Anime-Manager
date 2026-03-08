<script setup lang="ts">
import { ref, watch } from 'vue'
import { 
  NModal, NDataTable, NTag, NButton, NSpace, NText, NIcon, useDialog, useMessage
} from 'naive-ui'
import { 
  HistoryOutlined as HistoryIcon,
  DeleteSweepOutlined as ClearIcon 
} from '@vicons/material'
import { getButtonStyle } from '../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  sub: any
  apiBase: string
}>()

const emit = defineEmits(['update:show'])

const loading = ref(false)
const history = ref<any[]>([])
const dialog = useDialog()
const message = useMessage()

const fetchHistory = async () => {
  if (!props.sub?.id) return
  loading.value = true
  try {
    const res = await fetch(`${props.apiBase}/api/subscriptions/${props.sub.id}/episodes`)
    const data = await res.json()
    // Sort by download_at desc
    history.value = data.sort((a: any, b: any) => 
      new Date(b.download_at).getTime() - new Date(a.download_at).getTime()
    )
  } catch (e) {
    console.error('Fetch subscription history failed', e)
  } finally {
    loading.value = false
  }
}

const handleClearHistory = () => {
  dialog.warning({
    title: '确认清空历史？',
    content: '清空后，系统将不再认为这些集数已下载，下次刷新或补全时可能会重复下载。确定吗？',
    positiveText: '确定清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await fetch(`${props.apiBase}/api/subscriptions/${props.sub.id}/episodes`, {
          method: 'DELETE'
        })
        message.success('历史记录已重置')
        fetchHistory()
      } catch (e) {
        message.error('操作失败')
      }
    }
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) fetchHistory()
})

const columns = [
  {
    title: '季/集',
    key: 'pos',
    width: 80,
    render(row: any) {
      if (row.season === 0 && row.episode === 0) return '电影'
      return `S${row.season}E${row.episode}`
    }
  },
  {
    title: '推送资源标题',
    key: 'title',
    render(row: any) {
      return row.title || '（历史记录无标题）'
    }
  },
  {
    title: '推送时间',
    key: 'download_at',
    width: 160,
    render(row: any) {
      return new Date(row.download_at).toLocaleString()
    }
  }
]
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="v => emit('update:show', v)" 
    preset="card" 
    style="width: 800px; max-width: 95vw; max-height: 90vh;" 
    :title="`推送记录: ${sub?.title}`"
  >
    <n-data-table 
      :columns="columns" 
      :data="history" 
      :loading="loading"
      size="small"
      max-height="calc(90vh - 200px)"
      :empty-description="'暂无推送记录'"
    />
    <template #footer>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('danger')" size="small" @click="handleClearHistory" :disabled="history.length === 0">
          清空所有推送历史
        </n-button>
        <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">关闭窗口</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
