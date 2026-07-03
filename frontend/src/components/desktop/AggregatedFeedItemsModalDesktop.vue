<script setup lang="ts">
import { ref, watch, h, onMounted, onUnmounted, computed } from 'vue'
import {
  NModal, NDataTable, NTag, NButton, NSpace, NText, NSelect, NInput, NPopconfirm
} from 'naive-ui'
import { useAggregatedFeedItems } from '../../composables/modals/useAggregatedFeedItems'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  feeds: any[]
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
  selectedFeedIds,
  keyword,
  fetchItems,
  applyFilter,
  handlePageChange,
  handlePageSizeChange,
  handleDownload,
  handleToggleHistory,
  handleRetryRecognition,
  handleClearHistory
} = useAggregatedFeedItems(props)

const activeDropdownKey = ref<string | null>(null)

// 站点选项：使用用户备注名作为标签
const feedOptions = computed(() => {
  return (props.feeds || []).map(f => ({ label: f.title || f.url, value: f.id }))
})

// 清除下载记录的确认文案：根据是否筛选站点动态变化
const clearHistoryTip = computed(() => {
  return selectedFeedIds.value.length > 0
    ? `确认清除当前筛选的 ${selectedFeedIds.value.length} 个站点的下载记录吗？`
    : '未筛选站点，将清除全部下载记录，确认吗？'
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

const cleanDescription = (desc: string | null | undefined): string | null => {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  if (clean.length > 100) {
    clean = clean.substring(0, 100) + '...'
  }
  return clean || null
}

const formatPubDate = (dateStr: string | null | undefined): string => {
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

// 分页配置（remote 模式，数据从后端获取）
const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [20, 50, 100]
}))

const columns = [
  {
    title: '来源源',
    key: 'feed_name',
    width: 140,
    render(row: any) {
      return h(NTag, {
        size: 'small',
        round: true,
        bordered: false,
        style: { color: '#fff', backgroundColor: '#6d4c41', borderRadius: '12px' }
      }, { default: () => row.feed_name || '-' })
    }
  },
  {
    title: '#',
    key: 'index',
    width: 50,
    render(_, index) {
      return index + 1
    }
  },
  {
    title: '资源标题',
    key: 'title',
    render(row: any) {
      const cleanDesc = cleanDescription(row.description)
      return h('div', { style: 'padding: 4px 0' }, [
        h(NText, { strong: true, style: 'font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        cleanDesc ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px' }, { default: () => cleanDesc }) : null,
        row.tmdb_title ? h('div', { style: 'margin-top: 6px; color: var(--n-primary-color); font-size: 12px; display: flex; align-items: center' }, [
          h('span', { style: 'margin-right: 4px' }, { default: () => '🎯' }),
          h(NText, { depth: 3, style: 'color: var(--n-primary-color); font-weight: bold' }, { default: () => row.tmdb_title })
        ]) : null
      ])
    }
  },
  {
    title: '识别元数据与规格',
    key: 'specs',
    width: 320,
    render(row: any) {
      const tags = []
      if (row.in_subscription) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#0288d1', borderRadius: '12px' } }, { default: () => '已订阅' }))
      if (row.episode_collected) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' } }, { default: () => '订阅已下载' }))

      if (row.recognition_done && row.tmdb_id) {
        const tmdbUrl = `https://www.themoviedb.org/${row.media_type === 'movie' ? 'movie' : 'tv'}/${row.tmdb_id}`
        tags.push(h('a', {
          href: tmdbUrl,
          target: '_blank',
          style: {
            color: '#fff',
            backgroundColor: '#2e7d32',
            borderRadius: '12px',
            padding: '2px 10px',
            fontSize: '12px',
            fontWeight: '500',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            height: '22px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }
        }, { default: () => `ID: ${row.tmdb_id}` }))
        tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#1565c0', borderRadius: '12px' } }, {
          default: () => row.media_type === 'movie' ? '🎬 电影' : '📺 剧集'
        }))
        if (row.media_type === 'tv') {
          tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#3B82F6', borderRadius: '12px' } }, { default: () => `S${row.season || 1} E${row.episode || '-'}` }))
        }
      } else if (row.recognition_done) {
        tags.push(h(NTag, { size: 'small', quaternary: true, style: { color: 'var(--color-warning)', borderColor: 'var(--color-warning-bg)', backgroundColor: 'var(--color-warning-bg)' } }, { default: () => '未命中' }))
      }

      if (row.team) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#0d47a1', borderRadius: '12px' } }, { default: () => row.team }))
      if (row.source) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' } }, { default: () => row.source }))
      if (row.platform) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' } }, { default: () => row.platform }))
      if (row.resolution) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.resolution }))
      if (row.video_effect) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.video_effect }))
      if (row.video_encode) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.video_encode }))
      if (row.audio_encode) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.audio_encode }))
      if (row.subtitle) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.subtitle }))

      return h(NSpace, { size: 4, itemStyle: 'display: flex' }, { default: () => tags })
    }
  },
  { title: '发布时间', key: 'pub_date', width: 140, render(row: any) { return formatPubDate(row.pub_date) } },
  {
    title: 'GUID 状态',
    key: 'is_downloaded',
    width: 100,
    render(row: any) {
      return row.is_downloaded
        ? h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' } }, { default: () => '已推送' })
        : h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#757575', borderRadius: '12px' } }, { default: () => '未推送' })
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
  <n-modal
    :show="show"
    @update:show="val => emit('update:show', val)"
    preset="card"
    style="width: 1400px; max-width: 98vw; height: 96vh;"
    content-style="display: flex; flex-direction: column; padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    title="订阅源详情"
  >
    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px 20px;">
      <!-- 筛选工具栏 -->
      <div class="filter-bar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索资源标题或识别名..."
          clearable
          class="filter-item"
          @update:value="applyFilter"
        />
        <n-select
          v-model:value="selectedFeedIds"
          multiple
          filterable
          clearable
          placeholder="筛选站点（可多选）"
          :options="feedOptions"
          max-tag-count="1"
          class="filter-item"
          @update:value="applyFilter"
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
        <n-space>
          <n-popconfirm @positive-click="handleClearHistory" positive-text="确认清除" negative-text="取消">
            <template #trigger>
              <n-button v-bind="getButtonStyle('text')" size="medium" style="color: var(--n-error-color); height: 34px">清除下载记录</n-button>
            </template>
            {{ clearHistoryTip }}
          </n-popconfirm>
          <n-button v-bind="getButtonStyle('secondary')" @click="handleRetryRecognition" :loading="loading">
            重试识别失败项
          </n-button>
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">关闭</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
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
.filter-item :deep(.n-input-wrapper) {
  display: flex;
  align-items: center;
}
</style>
