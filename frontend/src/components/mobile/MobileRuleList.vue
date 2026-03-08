<script setup lang="ts">
import { h } from 'vue'
import { NTag, NButton, NIcon, NDropdown, NEmpty, useDialog } from 'naive-ui'
import {
  MoreVertOutlined as MoreIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  ContentCopyOutlined as CopyIcon,
  HistoryOutlined as HistoryIcon
} from '@vicons/material'

import { getButtonStyle } from '../../composables/useButtonStyles'

defineProps<{
  rules: any[]
}>()

const emit = defineEmits<{
  (e: 'edit', rule: any): void
  (e: 'delete', id: number): void
  (e: 'duplicate', rule: any): void
  (e: 'viewHistory', rule: any): void
}>()

const dialog = useDialog()

const createOptions = (rule: any) => [
  { label: '编辑规则', key: 'edit', icon: () => h(NIcon, null, { default: () => h(EditIcon) }) },
  { label: '复制规则', key: 'copy', icon: () => h(NIcon, null, { default: () => h(CopyIcon) }) },
  { label: '执行记录', key: 'history', icon: () => h(NIcon, null, { default: () => h(HistoryIcon) }) },
  { type: 'divider' },
  { label: '删除', key: 'delete', icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }), style: { color: 'var(--n-error-color)' } }
]

const handleSelect = (key: string, rule: any) => {
  if (key === 'edit') emit('edit', rule)
  else if (key === 'copy') emit('duplicate', rule)
  else if (key === 'history') emit('viewHistory', rule)
  else if (key === 'delete') {
    dialog.warning({
      title: '删除确认',
      content: `确定要删除规则「${rule.name}」吗？`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: () => emit('delete', rule.id)
    })
  }
}
</script>

<template>
  <div class="mobile-rule-list">
    <div v-if="rules.length > 0">
      <div v-for="rule in rules" :key="rule.id" class="rule-item" @click="emit('edit', rule)">
        <div class="rule-content">
          <div class="rule-header">
            <span class="rule-name">{{ rule.name }}</span>
            <n-tag size="small" :type="rule.enabled ? 'success' : 'error'" round style="zoom: 0.8">
              {{ rule.enabled ? '生效' : '关闭' }}
            </n-tag>
          </div>
          <div class="rule-details">
            <span class="rule-keyword">包含: {{ rule.must_contain || '无' }}</span>
            <span class="rule-regex" v-if="rule.use_regex">正则</span>
          </div>
        </div>
        <div class="rule-action" @click.stop>
          <n-dropdown trigger="click" :options="createOptions(rule)" @select="(k) => handleSelect(k, rule)" placement="bottom-end">
            <n-button v-bind="getButtonStyle('icon')" size="small">
              <template #icon><n-icon><MoreIcon/></n-icon></template>
            </n-button>
          </n-dropdown>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无下载规则" />
    </div>
  </div>
</template>

<style scoped>
.mobile-rule-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rule-item {
  display: flex;
  align-items: center;
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  padding: 12px;
}
.rule-content {
  flex: 1;
  overflow: hidden;
}
.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.rule-name {
  font-weight: bold;
  font-size: 14px;
  margin-right: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rule-details {
  font-size: 11px;
  color: var(--n-text-color-3);
  display: flex;
  align-items: center;
  gap: 8px;
}
.rule-keyword {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}
.rule-regex {
  background: rgba(242, 201, 125, 0.2);
  color: #f2c97d;
  padding: 1px 4px;
  border-radius: 2px;
  font-size: 10px;
}
.rule-action {
  margin-left: 8px;
}
.empty-state {
  padding: 40px 0;
  text-align: center;
}
</style>
