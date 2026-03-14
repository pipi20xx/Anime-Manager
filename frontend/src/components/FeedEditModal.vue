<script setup lang="ts">
import { reactive, watch } from 'vue'
import { NModal, NSpace, NFormItem, NInput, NSwitch, NButton } from 'naive-ui'
import { getButtonStyle } from '../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  feedData: any
  isNew: boolean
}>()

const emit = defineEmits(['update:show', 'save'])

const form = reactive({
  id: undefined,
  title: '',
  url: '',
  enabled: true,
  for_subscription: true,
  for_rules: true,
  anime_priority: true,
  check_emby_exists: false,
  include_keywords: '',
  exclude_keywords: ''
})

watch(() => props.show, (newVal) => {
  if (newVal) {
    if (props.isNew) {
      form.id = undefined
      form.title = ''
      form.url = ''
      form.enabled = true
      form.for_subscription = true
      form.for_rules = true
      form.anime_priority = true
      form.check_emby_exists = false
      form.include_keywords = ''
      form.exclude_keywords = ''
    } else {
      const data = JSON.parse(JSON.stringify(props.feedData))
      // Handle legacy data missing new fields
      if (data.for_subscription === undefined) data.for_subscription = true
      if (data.for_rules === undefined) data.for_rules = true
      if (data.anime_priority === undefined) data.anime_priority = true
      if (data.check_emby_exists === undefined) data.check_emby_exists = false
      Object.assign(form, data)
    }
  }
})

const handleSave = () => {
  emit('save', { ...form })
  emit('update:show', false)
}
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 500px; max-width: 95vw;" 
    :title="isNew ? '添加 RSS 订阅源' : '编辑 RSS 订阅源'"
  >
    <n-scrollbar style="max-height: 75vh" trigger="none">
      <div style="padding-right: 12px;">
        <n-space vertical size="large">
      <n-form-item label="订阅名称 (备注)">
        <n-input v-model:value="form.title" placeholder="例如: 蜜柑 - 季度新番" />
      </n-form-item>
      
      <n-form-item label="RSS 订阅地址">
        <n-input v-model:value="form.url" placeholder="支持 Mikan, Nyaa, Jackett 等标准 RSS 链接" />
      </n-form-item>

      <n-form-item label="前置包含词 (可选)">
        <n-input v-model:value="form.include_keywords" placeholder="空格=且，| =或。例如: 1080P | 4K" />
      </n-form-item>

      <n-form-item label="前置排除词 (可选)">
        <n-input v-model:value="form.exclude_keywords" placeholder="命中任意一个词即过滤该条目" />
      </n-form-item>
      
      <n-form-item label="自动监控设置">
        <n-space vertical :size="12">
          <n-space align="center" :size="8">
            <n-switch v-model:value="form.enabled" />
            <span style="font-size: 12px; color: var(--text-secondary);">全局监控</span>
          </n-space>
          
          <n-space vertical :size="8" v-if="form.enabled">
            <n-space align="center" :size="8">
              <n-switch v-model:value="form.for_subscription" />
              <span style="font-size: 12px; color: var(--text-secondary);">追剧订阅</span>
            </n-space>
            <n-space align="center" :size="8">
              <n-switch v-model:value="form.for_rules" />
              <span style="font-size: 12px; color: var(--text-secondary);">下载规则</span>
            </n-space>
            <n-space align="center" :size="8">
              <n-switch v-model:value="form.anime_priority" />
              <span style="font-size: 12px; color: var(--text-secondary);">动漫优先</span>
            </n-space>
            <n-space align="center" :size="8">
              <n-switch v-model:value="form.check_emby_exists" />
              <span style="font-size: 12px; color: var(--text-secondary);">Emby 检查</span>
            </n-space>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px; line-height: 1.4;">
              检测 Emby 库是否存在，存在则跳过处理
            </div>
          </n-space>
        </n-space>
      </n-form-item>
    </n-space>
      </div>
    </n-scrollbar>
    
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
