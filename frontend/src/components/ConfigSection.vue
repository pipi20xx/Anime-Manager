<script setup lang="ts">
import { computed } from 'vue'
import { NGrid, NGi, NInput, NTag, NIcon } from 'naive-ui'
import { SettingsOutlined as ConfigIcon } from '@vicons/material'

interface Props {
  title: string
  description?: string
  local: string[]
  remote: string[]
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  description: '',
  placeholder: '每一行一条规则...'
})
const emit = defineEmits(['update:local', 'update:remote'])

const localText = computed({
  get() { return (props.local || []).join('\n') },
  set(val) { emit('update:local', (String(val || '')).split('\n').map(s => s.trim())) }
})

const remoteText = computed({
  get() { return (props.remote || []).join('\n') },
  set(val) { emit('update:remote', (String(val || '')).split('\n').map(s => s.trim())) }
})
</script>

<template>
  <n-card class="config-section" bordered size="small">
    <template #header>
      <div class="section-header">
        <div class="icon-box"><n-icon style="color: var(--n-primary-color)"><ConfigIcon /></n-icon></div>
        <div class="title-group">
          <div class="title">{{ title }}</div>
          <div v-if="description" class="description">{{ description }}</div>
        </div>
      </div>
    </template>
    
    <n-grid :cols="2" :x-gap="24" class="grid-body">
      <n-gi>
        <div class="col-header">
          <div class="label">{{ title }} · 本地规则</div>
          <n-tag type="primary" size="tiny" round ghost>可编辑</n-tag>
        </div>
        <div class="input-wrapper">
          <n-input
            v-model:value="localText"
            type="textarea"
            :placeholder="placeholder"
            :autosize="{ minRows: 8, maxRows: 12 }"
            class="mono-input"
          />
        </div>
      </n-gi>
      
      <n-gi>
        <div class="col-header">
          <div class="label">{{ title }} · 远程订阅</div>
          <n-tag type="info" size="tiny" round ghost>仅同步</n-tag>
        </div>
        <div class="input-wrapper">
          <n-input
            v-model:value="remoteText"
            type="textarea"
            placeholder="http://example.com/rules.txt"
            :autosize="{ minRows: 8, maxRows: 12 }"
            class="mono-input"
          />
        </div>
      </n-gi>
    </n-grid>
  </n-card>
</template>

<style scoped>
.config-section { background: var(--app-surface-subtle); border-radius: 8px; border: 1px solid var(--border-light); }
.section-header { display: flex; align-items: center; gap: 12px; }
.icon-box { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; background: var(--primary-light); border-radius: 8px; flex-shrink: 0; }
.title-group { display: flex; flex-direction: column; gap: 2px; }
.section-header .title { font-size: 15px; font-weight: bold; color: var(--text-secondary); line-height: 1.2; }
.section-header .description { font-size: 12px; color: var(--text-tertiary); font-weight: normal; }
.col-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 0 4px; }
.col-header .label { font-size: 12px; color: var(--text-tertiary); font-weight: 500; }
.input-wrapper { background: var(--app-surface-inner); padding: 4px; border-radius: var(--button-border-radius, 4px); border: 1px solid var(--n-border-color); }
.mono-input :deep(textarea) { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: transparent; color: var(--text-secondary); border: none; padding: 8px; }
.mono-input :deep(.n-input__border), .mono-input :deep(.n-input__state-border) { display: none; }
</style>