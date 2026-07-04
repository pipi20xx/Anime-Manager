<script setup lang="ts">
import { ref, watch, h, onMounted, onUnmounted, computed } from 'vue'
import AppGlassModal from '../AppGlassModal.vue'
import {
  NDataTable, NTag, NButton, NSpace
} from 'naive-ui'
import { useAggregatedRuleHistory } from '../../composables/modals/useAggregatedRuleHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'
import AppSearchField from '../AppSearchField.vue'
import AppSelectField from '../AppSelectField.vue'

const props = defineProps<{
  show: boolean
  rules: any[]
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  total,
  page,
  pageSize,
  clientOptions,
  selectedRuleIds,
  keyword,
  fetchItems,
  applyFilter,
  handlePageChange,
  handlePageSizeChange,
  handleDownload,
  handleDelete
} = useAggregatedRuleHistory(props)

const activeDropdownKey = ref<string | null>(null)

// 规则选项：使用规则名称作为标签
const ruleOptions = computed(() => {
  return (props.rules || []).map(r => ({ label: r.name, value: r.id }))
})

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

const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems()
  }
})

// 分页配置
const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [20, 50, 100]
}))

const columns = [
  {
    title: '所属规则',
    key: 'rule_name',
    width: 160,
    render(row: any) {
      return h(NTag, {
        size: 'small',
        round: true,
        bordered: false,
        style: { color: '#fff', backgroundColor: '#6d4c41', borderRadius: '12px' }
      }, { default: () => row.rule_name || '-' })
    }
  },
  {
    title: '资源标题',
    key: 'title',
    render(row: any) {
      return h('div', { style: 'padding: 4px 0' }, [
        h('div', { style: 'font-weight: bold; font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        row.description ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px', },
          { default: () => row.description }
        ) : null
      ])
    }
  },
  { title: '推送时间', key: 'created_at', width: 160, render(row: any) { return formatDateTime(row.created_at) } },
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
        onClick: () => handleDelete(row)
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
              default: () => clientOptions.value.length === 0 ? '无下载器' : '手动下载'
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
</script>

<template>
  <AppGlassModal
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 1400px; height: 96vh;"
    content-style="display: flex; flex-direction: column; padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    title="下载记录"
  >
    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px 20px;">
      <!-- 筛选工具栏 -->
      <div class="filter-bar">
        <AppSearchField
          :value="keyword"
          placeholder="搜索资源标题或描述..."
          :loading="loading"
          class="filter-item"
          @update:value="val => keyword = val"
          @search="applyFilter"
        />
        <AppSelectField
          :value="selectedRuleIds"
          label="筛选规则"
          placeholder="筛选规则（可多选）"
          :options="ruleOptions"
          multiple
          filterable
          clearable
          :max-tag-count="'responsive'"
          class="filter-item"
          @update:value="val => { selectedRuleIds = val; applyFilter() }"
        />
      </div>

      <n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :pagination="pagination"
        :row-key="row => row.guid"
        remote
        flex-height
        style="flex: 1;"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </div>
    <template #footer>
      <n-space justify="space-between" align="center">
        <div style="font-size: 12px; color: var(--text-muted)">
          共 {{ total }} 条记录
        </div>
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">关闭</n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
  margin-bottom: 12px;
}
.filter-item {
  flex: 1;
}
.filter-item :deep(.app-search-field),
.filter-item :deep(.app-search-field__box) {
  height: 100%;
}
</style>
