<script setup lang="ts">
import { ref, watch, h, computed, onMounted, onUnmounted } from 'vue'
import { dataTableThemeOverrides } from '../../store/appearanceStore'
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NDataTable, NTag, NButton, NSpace, NSpin, NEmpty, useMessage
} from 'naive-ui'
import { getButtonStyle } from '../../composables/useButtonStyles'

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

const activeDropdownKey = ref<string | null>(null)

const toggleDropdown = (key: string) => {
  if (activeDropdownKey.value === key) {
    activeDropdownKey.value = null
  } else {
    activeDropdownKey.value = key
  }
}

const closeDropdown = () => {
  activeDropdownKey.value = null
}

const selectClient = (item: any, clientId: string) => {
  handleDownload(item, clientId)
  closeDropdown()
}

const handleClickOutside = (e: Event) => {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-dropdown')) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
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
      return row.state === 'Success'
        ? h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' } }, { default: () => '成功' })
        : h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' } }, { default: () => '失败' })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render(row: any) {
      const btns = []
      btns.push(h(NButton, {
        ...getButtonStyle('primary'),
        size: 'small',
        onClick: () => handleDelete(row.guid)
      }, { default: () => '清除下载记录' }))

      if (row.link) {
        const dropdownKey = `download-${row.guid}`
        
        btns.push(
          h('div', {
            class: 'custom-dropdown',
            style: { position: 'relative', display: 'inline-block' }
          }, [
            h(NButton, {
              ...getButtonStyle('primary'),
              size: 'small',
              disabled: clientOptions.value.length === 0,
              onClick: (e: Event) => {
                e.stopPropagation()
                toggleDropdown(dropdownKey)
              }
            }, { 
              default: () => clientOptions.value.length === 0 ? '无下载器' : '再下载'
            }),
            activeDropdownKey.value === dropdownKey ? h('div', {
              class: 'custom-dropdown-menu',
              style: {
                position: 'absolute',
                top: '100%',
                left: '50%',
                transform: 'translateX(-50%)',
                marginTop: '6px',
                zIndex: 2000,
                minWidth: '140px',
                background: 'linear-gradient(135deg, rgba(187, 134, 252, 0.15) 0%, rgba(156, 100, 217, 0.1) 100%)',
                borderRadius: 'var(--code-radius, 8px)',
                boxShadow: 'var(--shadow-lg, 0 8px 24px rgba(0, 0, 0, 0.5)), 0 0 20px rgba(187, 134, 252, 0.15)',
                padding: '6px',
                border: '1px solid var(--primary-medium, rgba(187, 134, 252, 0.3))',
                backdropFilter: 'blur(12px)'
              }
            }, 
              clientOptions.value.map(client => 
                h('div', {
                  class: 'custom-dropdown-item',
                  style: {
                    padding: '10px 20px',
                    cursor: 'pointer',
                    borderRadius: '12px',
                    marginBottom: '4px',
                    background: 'var(--n-primary-color, #bb86fc)',
                    color: '#fff',
                    fontSize: '13px',
                    fontWeight: '500',
                    transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                    userSelect: 'none',
                    letterSpacing: '0.3px',
                    boxShadow: 'var(--shadow-sm, 0 2px 4px rgba(0, 0, 0, 0.3))'
                  },
                  onMouseenter: (e: Event) => {
                    const el = e.target as HTMLElement
                    el.style.background = 'linear-gradient(135deg, var(--n-primary-color, #bb86fc) 0%, #9c64d9 100%)'
                    el.style.boxShadow = 'var(--shadow-md, 0 4px 12px rgba(187, 134, 252, 0.4))'
                    el.style.transform = 'scale(1.02)'
                  },
                  onMouseleave: (e: Event) => {
                    const el = e.target as HTMLElement
                    el.style.background = 'var(--n-primary-color, #bb86fc)'
                    el.style.boxShadow = 'var(--shadow-sm, 0 2px 4px rgba(0, 0, 0, 0.3))'
                    el.style.transform = 'scale(1)'
                  },
                  onMousedown: (e: Event) => {
                    const el = e.target as HTMLElement
                    el.style.background = 'linear-gradient(135deg, #8b5fbf 0%, #7a4db8 100%)'
                    el.style.transform = 'scale(0.98)'
                    el.style.boxShadow = 'var(--shadow-xs, 0 1px 2px rgba(0, 0, 0, 0.5))'
                  },
                  onMouseup: (e: Event) => {
                    const el = e.target as HTMLElement
                    el.style.background = 'linear-gradient(135deg, var(--n-primary-color, #bb86fc) 0%, #9c64d9 100%)'
                    el.style.transform = 'scale(1.02)'
                    el.style.boxShadow = 'var(--shadow-md, 0 4px 12px rgba(187, 134, 252, 0.4))'
                  },
                  onClick: (e: Event) => {
                    e.stopPropagation()
                    selectClient(row, client.value)
                  }
                }, { default: () => client.label })
              )
            ) : null
          ])
        )
      } else {
         btns.push(h(NButton, { 
           ...getButtonStyle('primary'),
           size: 'small',
           disabled: true 
         }, { default: () => '无链接' }))
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
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    style="width: 800px" 
    :title="`推送历史: ${rule?.name}`"
  >
    <n-spin :show="loading">
      <div style="min-height: 300px">
        <n-data-table
          :theme-overrides="dataTableThemeOverrides"
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
  </AppGlassModal>
</template>
