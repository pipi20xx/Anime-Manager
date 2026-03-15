<script setup lang="ts">
import { watch, h } from 'vue'
import { 
  NModal, NDataTable, NTag, NButton, NSpace, NSpin, NEmpty, NPopselect
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

watch(() => props.show, (newVal) => {
  if (newVal) fetchPreview()
})

const columns = [
  { 
    title: '预计匹配到的资源标题', 
    key: 'title',
    render(row: any) {
      return h('div', { style: 'padding: 4px 0' }, [
        h('div', { style: 'font-weight: bold; font-size: 14px; line-height: 1.4' }, { default: () => row.title }),
        row.description ? h('div', { style: 'font-size: 12px; color: var(--text-tertiary); margin-top: 2px' }, { default: () => row.description }) : null
      ])
    }
  },
  {
    title: '来源订阅源',
    key: 'feed_name',
    width: 180,
    render(row: any) {
      return h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#6a1b9a', borderRadius: '12px' } }, { default: () => row.feed_name })
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
    style="width: 1000px; max-width: 98vw; height: 96vh;" 
    content-style="display: flex; flex-direction: column; padding: 0;"
    :segmented="{ content: true, footer: 'soft' }"
    title="匹配结果预览"
  >
    <n-spin :show="loading" style="flex: 1; display: flex; flex-direction: column;" content-style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
      <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px 20px;">
        <n-data-table
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
  </n-modal>
</template>
