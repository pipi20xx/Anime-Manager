<script setup lang="ts">
import { watch, h, ref, onMounted, onUnmounted } from 'vue'
import { dataTableThemeOverrides } from '../../store/appearanceStore'
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NDataTable, NTag, NButton, NSpace, NSpin, NEmpty
} from 'naive-ui'
import { useRulePreview } from '../../composables/modals/useRulePreview'
import { getButtonStyle } from '../../composables/useButtonStyles'

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

const getTagStyle = (type: string) => {
  const styles: Record<string, any> = {
    info: { color: 'var(--color-info)', borderColor: 'var(--color-info-bg)', backgroundColor: 'var(--color-info-bg)' },
    success: { color: 'var(--color-success)', borderColor: 'var(--color-success-bg)', backgroundColor: 'var(--color-success-bg)' },
    warning: { color: 'var(--color-warning)', borderColor: 'var(--color-warning-bg)', backgroundColor: 'var(--color-warning-bg)' },
    error: { color: 'var(--color-error)', borderColor: 'var(--color-error-bg)', backgroundColor: 'var(--color-error-bg)' },
    primary: { color: 'var(--n-primary-color)', borderColor: 'var(--app-code-primary)', backgroundColor: 'var(--app-code-primary)' },
    default: { color: 'var(--text-tertiary)', borderColor: 'var(--app-border-light)', backgroundColor: 'var(--bg-surface)' }
  }
  return styles[type] || styles.default
}

const cleanDescription = (desc: string | null | undefined): string | null => {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) {
    if (desc.length > 100) {
      return desc.substring(0, 100) + '...'
    }
    return desc
  }
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  if (clean.length > 100) {
    clean = clean.substring(0, 100) + '...'
  }
  return clean || null
}

watch(() => props.show, (newVal) => {
  if (newVal) fetchPreview()
})

const columns = [
  { 
    title: '预计匹配到的资源标题', 
    key: 'title',
    render(row: any) {
      const cleanDesc = cleanDescription(row.description)
      return h('div', { style: 'padding: 4px 0' }, [
        h('div', { style: 'font-weight: bold; font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        cleanDesc ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px' }, { default: () => cleanDesc }) : null
      ])
    }
  },
  {
    title: '来源订阅源',
    key: 'feed_name',
    width: 180,
    render(row: any) {
      return h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#3B82F6', borderRadius: '12px' } }, { default: () => row.feed_name })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render(row: any) {
      const btns = []
      if (row.is_downloaded) {
        btns.push(h(NButton, { 
          ...getButtonStyle('primary'),
          size: 'small',
          onClick: () => handleToggleHistory(row, false)
        }, { default: () => '清除下载记录' }))
      } else {
        btns.push(h(NButton, {
          ...getButtonStyle('primary'),
          size: 'small',
          onClick: () => handleToggleHistory(row, true)
        }, { default: () => '设为已下载' }))
      }

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
            default: () => clientOptions.value.length === 0 ? '无下载器' : '下载'
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

      return h(NSpace, { size: 4 }, { default: () => btns })
    }
  }
]
</script>

<template>
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    style="width: 1000px; max-width: 98vw; height: 96vh;" 
    content-style="display: flex; flex-direction: column; padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    title="匹配结果预览"
  >
    <n-spin :show="loading" style="flex: 1; display: flex; flex-direction: column;" content-style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
      <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px 20px;">
        <n-data-table
          :theme-overrides="dataTableThemeOverrides"
          v-if="items.length > 0"
          :columns="columns"
          :data="items"
          :pagination="{ pageSize: 15 }"
          flex-height
          style="flex: 1;"
        />
        <n-empty v-else-if="!loading" description="该规则未匹配到任何最近抓取的条目" style="margin-top: 80px" />
      </div>
    </n-spin>
    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">返回编辑</n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>
