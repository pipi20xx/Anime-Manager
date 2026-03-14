<script setup lang="ts">
import { reactive, watch, ref, onMounted, computed } from 'vue'
import { 
  NModal, NSpace, NFormItem, NInput, NSwitch, 
  NButton, NSelect, NInputNumber, NDivider, NIcon, NTooltip, useMessage
} from 'naive-ui'
import { HelpOutlineOutlined as HelpIcon } from '@vicons/material'
import { getButtonStyle } from '../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  ruleData: any
  isNew: boolean
  feeds: any[]   // 传入所有 Feed 以供选择作用域
  clients: any[] // 传入所有 Client 以供选择目标
}>()

const emit = defineEmits(['update:show', 'save'])
const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const form = reactive({
  id: undefined,
  name: '',
  enabled: true,
  
  // Matching
  must_contain: '',
  must_not_contain: '',
  use_regex: false,
  target_feeds: '', // comma separated IDs
  
  // Action
  target_client_id: '',
  save_path: '',
  category: '',
  tags: '',
  paused: false
})

const selectedFeedIds = ref<string[]>([])

watch(() => props.show, (newVal) => {
  if (newVal) {
    if (props.isNew) {
      // Reset
      form.id = undefined
      form.name = ''
      form.enabled = true
      form.must_contain = ''
      form.must_not_contain = ''
      form.use_regex = false
      form.target_feeds = ''
      form.target_client_id = props.clients.length > 0 ? props.clients[0].id : ''
      form.save_path = ''
      form.category = ''
      form.tags = ''
      form.paused = false
      selectedFeedIds.value = []
    } else {
      // Fill
      Object.assign(form, JSON.parse(JSON.stringify(props.ruleData)))
      // Handle target_feeds string -> array
      if (form.target_feeds) {
        selectedFeedIds.value = (String(form.target_feeds || '')).split(',')
      } else {
        selectedFeedIds.value = []
      }
    }
  }
})

const handleSave = () => {
  form.target_feeds = selectedFeedIds.value.join(',')
  emit('save', { ...form })
  emit('update:show', false)
}

const handlePreview = () => {
  const previewData = {
    ...form,
    target_feeds: selectedFeedIds.value.join(',')
  }
  emit('preview', previewData)
}

const feedOptions = computed(() => props.feeds.map(f => ({ label: f.title || f.url, value: String(f.id) })))
const clientOptions = computed(() => props.clients.map(c => ({ label: c.name, value: c.id })))

</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 800px; max-width: 95vw;" 
    :title="isNew ? '添加匹配规则' : '编辑匹配规则'"
  >
    <n-space vertical size="medium">
      
      <n-form-item label="规则名称">
        <n-input v-model:value="form.name" placeholder="例如: 海贼王 1080p" />
      </n-form-item>

      <n-divider title-placement="left" style="margin: 0">匹配条件配置</n-divider>

      <n-space align="center">
        <span style="font-weight: bold; color: var(--text-tertiary)">匹配模式:</span>
        <n-switch v-model:value="form.use_regex">
          <template #checked>正则表达式</template>
          <template #unchecked>普通关键词</template>
        </n-switch>
      </n-space>

      <n-form-item>
        <template #label>
          <div style="display: flex; align-items: center; gap: 4px">
            包含关键词
            <n-tooltip trigger="hover">
              <template #trigger><n-icon><HelpIcon/></n-icon></template>
              普通模式下：<br/>• <b>空格</b> 分隔多个关键词表示「且」(AND)<br/>• <b>|</b> 符号分隔表示「或」(OR)<br/><br/>示例: <code>海贼王 1080p | 鬼灭之刃 4k</code>
            </n-tooltip>
          </div>
        </template>
        <n-input v-model:value="form.must_contain" type="textarea" :autosize="{minRows: 2}" placeholder="输入需要包含的词，支持高级逻辑..." />
      </n-form-item>

      <n-form-item label="排除关键词">
        <n-input v-model:value="form.must_not_contain" placeholder="碰到这些词就跳过该任务 (用 | 分隔)" />
      </n-form-item>

      <n-form-item label="作用范围 (留空则监控所有源)">
        <n-select multiple v-model:value="selectedFeedIds" :options="feedOptions" placeholder="选择此规则生效的特定订阅源" />
      </n-form-item>

      <n-divider title-placement="left" style="margin: 0">下载任务设置</n-divider>

      <n-form-item label="指定下载器">
        <n-select v-model:value="form.target_client_id" :options="clientOptions" placeholder="选择推送的目标客户端" />
      </n-form-item>

      <n-form-item label="保存路径">
        <n-input v-model:value="form.save_path" placeholder="留空则使用下载器默认路径" />
      </n-form-item>

      <n-grid :cols="2" :x-gap="12">
        <n-gi>
          <n-form-item label="分类">
            <n-input v-model:value="form.category" placeholder="例如: Anime" />
          </n-form-item>
        </n-gi>
        <n-gi>
          <n-form-item label="标签">
            <n-input v-model:value="form.tags" placeholder="例如: RSS, 自动推送" />
          </n-form-item>
        </n-gi>
      </n-grid>

      <n-form-item label="添加任务后的初始状态">
        <n-space align="center" :size="8">
          <n-switch v-model:value="form.paused" />
          <span style="font-size: 12px; color: var(--text-secondary);">
            {{ form.paused ? '手动确认 (任务将处于暂停状态)' : '自动开始 (任务直接进入下载队列)' }}
          </span>
        </n-space>
      </n-form-item>

      <n-form-item label="启用状态">
        <n-switch v-model:value="form.enabled" />
      </n-form-item>
    </n-space>
    <template #action>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('primary')" @click="handlePreview">
          预览匹配
        </n-button>
        <n-space>
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存规则</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
</style>
