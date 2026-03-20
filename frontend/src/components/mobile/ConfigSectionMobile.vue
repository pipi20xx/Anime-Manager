<script setup lang="ts">
import { computed } from 'vue'
import { NInput, NTag, NIcon, NSpace } from 'naive-ui'
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
  <div class="config-section-mobile">
    <div class="section-header">
      <div class="icon-box">
        <n-icon size="18"><ConfigIcon /></n-icon>
      </div>
      <div class="title-group">
        <div class="title">{{ title }}</div>
        <div v-if="description" class="description">{{ description }}</div>
      </div>
    </div>

    <div class="config-body">
      <!-- 本地规则 -->
      <div class="config-block">
        <div class="block-header">
          <span class="block-label">本地规则</span>
          <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">可编辑</n-tag>
        </div>
        <div class="input-wrapper">
          <n-input
            v-model:value="localText"
            type="textarea"
            :placeholder="placeholder"
            :autosize="{ minRows: 4, maxRows: 8 }"
            class="mono-input"
          />
        </div>
      </div>

      <!-- 远程订阅 -->
      <div class="config-block">
        <div class="block-header">
          <span class="block-label">远程订阅</span>
          <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">仅同步</n-tag>
        </div>
        <div class="input-wrapper">
          <n-input
            v-model:value="remoteText"
            type="textarea"
            placeholder="http://example.com/rules.txt"
            :autosize="{ minRows: 4, maxRows: 8 }"
            class="mono-input"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-section-mobile {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  margin-bottom: var(--m-spacing-md);
}

.icon-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--primary-light);
  border-radius: var(--m-radius-md);
  color: var(--color-primary);
  flex-shrink: 0;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.title {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.description {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  line-height: 1.3;
}

.config-body {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.config-block {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.block-label {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.input-wrapper {
  background: var(--app-surface-inner);
  padding: var(--m-spacing-xs);
  border-radius: var(--m-radius-md);
  border: 1px solid var(--app-border-light);
}

.mono-input :deep(textarea) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: transparent;
  color: var(--text-secondary);
  border: none;
  padding: var(--m-spacing-sm);
  min-height: 80px;
}

.mono-input :deep(.n-input__border),
.mono-input :deep(.n-input__state-border) {
  display: none;
}
</style>
