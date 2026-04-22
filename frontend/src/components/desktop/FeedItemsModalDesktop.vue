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
      // 状态标签 - 颜色底色+白色文字
      if (row.in_subscription) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#0288d1', borderRadius: '12px' } }, { default: () => '已订阅' }))
      if (row.episode_collected) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' } }, { default: () => '订阅已下载' }))

      if (row.recognition_done && row.tmdb_id) {
        // TMDB ID - 深绿色底色+白色文字
        tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' } }, { default: () => `ID: ${row.tmdb_id}` }))
        // 类型 - 蓝色底色+白色文字
        tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#1565c0', borderRadius: '12px' } }, {
          default: () => row.media_type === 'movie' ? '🎬 电影' : '📺 剧集'
        }))
        // SXXEXX - 电光蓝底色+白色文字
        if (row.media_type === 'tv') {
          tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#3B82F6', borderRadius: '12px' } }, { default: () => `S${row.season || 1} E${row.episode || '-'}` }))
        }
      } else if (row.recognition_done) {
        tags.push(h(NTag, { size: 'small', quaternary: true, style: getTagStyle('warning') }, { default: () => '未命中' }))
      }

      // 制作组 - 深蓝色底色+白色文字
      if (row.team) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#0d47a1', borderRadius: '12px' } }, { default: () => row.team }))
      // 来源/发布平台 - 红色底色+白色文字
      if (row.source) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' } }, { default: () => row.source }))
      if (row.platform) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' } }, { default: () => row.platform }))
      // 分辨率/视频编码/音频编码/视频特效 - 深橙色底色+白色文字
      if (row.resolution) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.resolution }))
      if (row.video_effect) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.video_effect }))
      if (row.video_encode) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.video_encode }))
      if (row.audio_encode) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.audio_encode }))
      if (row.subtitle) tags.push(h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#e65100', borderRadius: '12px' } }, { default: () => row.subtitle }))

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

      btns.push(
        h(NPopselect, {
          options: clientOptions.value,
          onUpdateValue: (val: string) => handleDownload(row, val),
          trigger: 'click'
        }, {
          default: () => h(NButton, { 
            ...getButtonStyle('primary'),
            size: 'small',
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
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">关闭</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>
