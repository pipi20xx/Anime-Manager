<script setup lang="ts">
import { ref, watch, h, nextTick } from 'vue'
import { 
  NModal, NDataTable, NTag, NButton, NSpace, NText, NPopselect
} from 'naive-ui'
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

const tableRef = ref<any>(null)

// Desktop specific scroll logic
const handleScroll = (e: Event) => {
  const target = e.target as HTMLElement
  if (!target || loading.value || !hasMore.value) return
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50) {
    fetchItems(true)
  }
}

const setupScrollListener = () => {
  nextTick(() => {
    if (tableRef.value) {
      const el = tableRef.value.$el.querySelector('.v-vl')
      if (el) {
        el.removeEventListener('scroll', handleScroll)
        el.addEventListener('scroll', handleScroll)
      }
    }
  })
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems(false)
    setupScrollListener()
  }
})

const columns = [
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
      return h('div', { style: 'padding: 4px 0' }, [
        h(NText, { strong: true, style: 'font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        row.description ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px' }, { default: () => row.description }) : null,
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
      if (row.in_subscription) tags.push(h(NTag, { type: 'info', size: 'small', secondary: true, bordered: false }, { default: () => '已订阅' }))
      if (row.episode_collected) tags.push(h(NTag, { type: 'success', size: 'small', secondary: true, bordered: false }, { default: () => '订阅已下载' }))

      if (row.recognition_done && row.tmdb_id) {
        tags.push(h(NTag, { type: 'primary', size: 'small', round: true }, { default: () => `ID: ${row.tmdb_id}` }))
        tags.push(h(NTag, { type: 'info', size: 'small', quaternary: true }, { 
          default: () => row.media_type === 'movie' ? '🎬 电影' : '📺 剧集' 
        }))
        if (row.media_type === 'tv') {
          tags.push(h(NTag, { type: 'info', size: 'small', round: true }, { default: () => `S${row.season || 1} E${row.episode || '-'}` }))
        }
      } else if (row.recognition_done) {
        tags.push(h(NTag, { type: 'warning', size: 'small', quaternary: true }, { default: () => '未命中' }))
      }

      if (row.team) tags.push(h(NTag, { size: 'small', quaternary: true, type: 'info' }, { default: () => row.team }))
      if (row.resolution) tags.push(h(NTag, { size: 'small', quaternary: true, type: 'warning' }, { default: () => row.resolution }))
      if (row.video_effect) tags.push(h(NTag, { size: 'small', quaternary: true, type: 'success' }, { default: () => row.video_effect }))
      if (row.video_encode) tags.push(h(NTag, { size: 'small', quaternary: true }, { default: () => row.video_encode }))
      if (row.subtitle) tags.push(h(NTag, { size: 'small', quaternary: true, type: 'error' }, { default: () => row.subtitle }))
      
      return h(NSpace, { size: 4, itemStyle: 'display: flex' }, { default: () => tags })
    }
  },
  { title: '发布时间', key: 'pub_date', width: 140 },
  { 
    title: 'GUID 状态', 
    key: 'is_downloaded', 
    width: 100,
    render(row: any) {
      return row.is_downloaded 
        ? h(NTag, { type: 'success', size: 'small', round: true }, { default: () => '已推送' })
        : h(NTag, { type: 'default', size: 'small', round: true }, { default: () => '未推送' })
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 230,
    render(row: any) {
      const btns = []      
      if (row.is_downloaded) {
        btns.push(h(NButton, { size: 'tiny', secondary: true, type: 'warning', onClick: () => handleToggleHistory(row, false) }, { default: () => '清除下载记录' }))
      } else {
        btns.push(h(NButton, { size: 'tiny', secondary: true, type: 'info', onClick: () => handleToggleHistory(row, true) }, { default: () => '设为已下载' }))
      }

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
          }, { default: () => clientOptions.value.length === 0 ? '无下载器' : '下载' })
        })
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
    style="width: 1200px; max-width: 98vw; height: 96vh;" 
    content-style="display: flex; flex-direction: column; padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    :title="`订阅源详情: ${feed?.title || feed?.url}`"
  >
    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px 20px;">
      <n-data-table
        ref="tableRef"
        :columns="columns"
        :data="items"
        :loading="loading"
        :virtual-scroll="true"
        :row-key="row => row.guid"
        flex-height
        style="flex: 1;"
      />
    </div>
    <template #footer>
      <n-space justify="space-between" align="center">
        <div style="font-size: 12px; color: var(--text-muted)">
          已加载 {{ items.length }} 条记录 <span v-if="loading && offset > 0"> (加载中...)</span>
        </div>
        <n-space>
          <n-button v-bind="getButtonStyle('secondary')" @click="handleRetryRecognition" :loading="loading">
            重试识别失败项
          </n-button>
          <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">关闭</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>
