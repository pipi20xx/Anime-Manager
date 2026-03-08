<script setup lang="ts">
import { ref, watch, h, computed } from 'vue'
import { 
  NModal, NDataTable, NTag, NButton, NSpace, NSpin, NEmpty, NPopselect, useMessage
} from 'naive-ui'

const props = defineProps<{
  show: boolean
  rule: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const message = useMessage()

const loading = ref(false)
const items = ref<any[]>([])
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const clientOptions = computed(() => {
  return (props.clients || []).map(c => ({ label: c.name, value: c.id }))
})

const handleDownload = async (item: any, clientId: string) => {
  try {
    const res = await fetch(`${API_BASE}/api/clients/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: clientId,
        url: item.link,
        title: item.title
      })
    })
    const data = await res.json()
    if (data.success) {
      message.success(data.message)
    } else {
      message.error(data.message)
    }
  } catch (e) {
    message.error('请求失败')
  }
}

const columns = [
  { 
    title: '历史推送资源标题', 
    key: 'title',
    render(row: any) {
      return h('div', { style: 'padding: 4px 0' }, [
        h('div', { style: 'font-weight: bold; font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        row.description ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px' }, { default: () => row.description }) : null
      ])
    }
  },
  { title: '推送时间', key: 'created_at', width: 180 },
  {
    title: '推送结果',
    key: 'state',
    width: 90,
    render(row: any) {
      return h(NTag, { size: 'small', round: true, type: row.state === 'Success' ? 'success' : 'error' }, { default: () => row.state === 'Success' ? '成功' : '失败' })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 230,
    render(row: any) {
      const btns = []
      // 1. Delete Button
      btns.push(h(NButton, {
        size: 'tiny',
        quaternary: true,
        type: 'error',
        onClick: () => handleDelete(row.guid)
      }, { default: () => '清除下载记录' }))

      // 2. Download Button
      if (row.link) {
        btns.push(
          h(NPopselect, {
            options: clientOptions.value,
            onUpdateValue: (val: string) => handleDownload(row, val),
            trigger: 'click'
          }, {
            default: () => h(NButton, { 
              size: 'tiny', 
              type: 'primary', 
              secondary: true, 
              style: 'margin-left: 6px',
              disabled: clientOptions.value.length === 0
            }, { default: () => clientOptions.value.length === 0 ? '无下载器' : '再下载' })
          })
        )
      } else {
         btns.push(h(NButton, { size: 'tiny', disabled: true, style: 'margin-left: 6px' }, { default: () => '无链接' }))
      }
      
      return h(NSpace, { size: 4 }, { default: () => btns })
    }
  }
]

const handleDelete = async (guid: string) => {
  try {
    await fetch(`${API_BASE}/api/rss/history/${encodeURIComponent(guid)}`, { method: 'DELETE' })
    fetchHistory()
  } catch (e) {
    console.error(e)
  }
}

const fetchHistory = async () => {
  if (!props.rule?.id) return
  loading.value = true
  items.value = []
  try {
    const res = await fetch(`${API_BASE}/api/rules/${props.rule.id}/history`)
    items.value = await res.json()
  } catch (e) {
    console.error('获取历史失败', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) fetchHistory()
})
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 800px" 
    :title="`推送历史: ${rule?.name}`"
  >
    <n-spin :show="loading">
      <div style="min-height: 300px">
        <n-data-table
          v-if="items.length > 0"
          :columns="columns"
          :data="items"
          :pagination="{ pageSize: 10 }"
          max-height="450px"
        />
        <n-empty v-else-if="!loading" description="该规则暂无推送记录" style="margin-top: 80px" />
      </div>
    </n-spin>
    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">关闭</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
