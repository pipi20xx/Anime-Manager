<script setup lang="ts">
import { reactive, watch } from 'vue'
import { NSpace, NFormItem, NSwitch, NButton } from 'naive-ui'
import AppTextField from './AppTextField.vue'
import AppGlassModal from './AppGlassModal.vue'
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
  batch_enhance: false,
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
      form.batch_enhance = false
      form.include_keywords = ''
      form.exclude_keywords = ''
    } else {
      const data = JSON.parse(JSON.stringify(props.feedData))
      if (data.for_subscription === undefined) data.for_subscription = true
      if (data.for_rules === undefined) data.for_rules = true
      if (data.anime_priority === undefined) data.anime_priority = true
      if (data.check_emby_exists === undefined) data.check_emby_exists = false
      if (data.batch_enhance === undefined) data.batch_enhance = false
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
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    style="width: 500px;" 
    :title="isNew ? '添加 RSS 订阅源' : '编辑 RSS 订阅源'"
  >
    <n-space vertical size="large">
      <n-form-item>
        <AppTextField v-model:value="form.title" label="订阅名称 (备注)" placeholder="例如: 蜜柑 - 季度新番" />
      </n-form-item>
      
      <n-form-item>
        <AppTextField v-model:value="form.url" label="RSS 订阅地址" placeholder="支持 Mikan, Nyaa, Jackett 等标准 RSS 链接" />
      </n-form-item>

      <n-form-item>
        <AppTextField v-model:value="form.include_keywords" label="前置包含词 (可选)" placeholder="空格=且，| =或。例如: 1080P | 4K" />
      </n-form-item>

      <n-form-item>
        <AppTextField v-model:value="form.exclude_keywords" label="前置排除词 (可选)" placeholder="命中任意一个词即过滤该条目" />
      </n-form-item>
      
      <n-form-item label="自动监控设置">
        <n-space vertical :size="12">
          <div class="switch-row">
            <n-switch v-model:value="form.enabled" />
            <span class="switch-row__label">全局监控</span>
            <span class="switch-row__desc">关闭后该源不再参与定时全量刷新</span>
          </div>
          <div class="switch-row">
            <n-switch v-model:value="form.for_subscription" />
            <span class="switch-row__label">追剧订阅</span>
            <span class="switch-row__desc">用于自动匹配并下载订阅的番剧更新</span>
          </div>
          <div class="switch-row">
            <n-switch v-model:value="form.for_rules" />
            <span class="switch-row__label">下载规则</span>
            <span class="switch-row__desc">用于触发 RSS 下载规则匹配</span>
          </div>
          <div class="switch-row">
            <n-switch v-model:value="form.anime_priority" />
            <span class="switch-row__label">动漫优先</span>
            <span class="switch-row__desc">优先使用动漫专用识别策略，提高动漫识别准确率</span>
          </div>
          <div class="switch-row">
            <n-switch v-model:value="form.check_emby_exists" />
            <span class="switch-row__label">Emby 检查</span>
            <span class="switch-row__desc">检测 Emby 库是否存在，存在则跳过处理</span>
          </div>
          <div class="switch-row">
            <n-switch v-model:value="form.batch_enhance" />
            <span class="switch-row__label">副标题合集提取</span>
            <span class="switch-row__desc">从 RSS 副标题中提取合集信息，部分源可能误判</span>
          </div>
        </n-space>
      </n-form-item>
    </n-space>
    
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存</n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-row__label {
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
.switch-row__desc {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
