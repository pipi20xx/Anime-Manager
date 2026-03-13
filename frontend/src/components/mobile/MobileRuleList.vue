<script setup lang="ts">
import { ref, h } from 'vue'
import { NTag, NButton, NIcon, NDrawer, NDrawerContent, NEmpty, useDialog } from 'naive-ui'
import {
  MoreVertOutlined as MoreIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  ContentCopyOutlined as CopyIcon,
  HistoryOutlined as HistoryIcon
} from '@vicons/material'

import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  rules: any[]
}>()

const emit = defineEmits<{
  (e: 'edit', rule: any): void
  (e: 'delete', id: number): void
  (e: 'duplicate', rule: any): void
  (e: 'viewHistory', rule: any): void
}>()

const dialog = useDialog()

// 操作抽屉状态
const showActionDrawer = ref(false)
const currentRule = ref<any>(null)
useBackClose(showActionDrawer)

const ruleActions = [
  { key: 'edit', label: '编辑规则', icon: EditIcon },
  { key: 'copy', label: '复制规则', icon: CopyIcon },
  { key: 'history', label: '执行记录', icon: HistoryIcon },
]

const openActions = (rule: any, e: Event) => {
  e.stopPropagation()
  currentRule.value = rule
  showActionDrawer.value = true
}

const handleAction = (key: string) => {
  const rule = currentRule.value
  if (!rule) return

  showActionDrawer.value = false
  setTimeout(() => {
    if (key === 'edit') emit('edit', rule)
    else if (key === 'copy') emit('duplicate', rule)
    else if (key === 'history') emit('viewHistory', rule)
    else if (key === 'delete') {
      dialog.warning({
        title: '删除确认',
        content: `确定要删除规则「${rule.name}」吗？`,
        action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
          h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
          h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { emit('delete', rule.id); dialog.destroyAll() } }, { default: () => '删除' })
        ])
      })
    }
  }, 300)
}
</script>

<template>
  <div class="mobile-rule-list">
    <div v-if="rules.length > 0">
      <div v-for="rule in rules" :key="rule.id" class="rule-item m-touchable" @click="emit('edit', rule)">
        <div class="rule-content">
          <div class="rule-header">
            <span class="rule-name">{{ rule.name }}</span>
            <n-tag size="small" :type="rule.enabled ? 'success' : 'error'" round class="status-tag">
              {{ rule.enabled ? '生效' : '关闭' }}
            </n-tag>
          </div>
          <div class="rule-details">
            <span class="rule-keyword">包含: {{ rule.must_contain || '无' }}</span>
            <span class="rule-regex" v-if="rule.use_regex">正则</span>
          </div>
        </div>
        <div class="rule-action" @click.stop="openActions(rule, $event)">
          <n-button v-bind="getButtonStyle('icon')" size="small">
            <template #icon><n-icon><MoreIcon/></n-icon></template>
          </n-button>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无下载规则" />
    </div>

    <!-- 操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="320" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content :title="currentRule?.name || '规则操作'" closable>
        <div class="action-list">
          <div v-for="action in ruleActions" :key="action.key" class="action-item" @click="handleAction(action.key)">
            <div class="action-icon">
              <n-icon size="22"><component :is="action.icon" /></n-icon>
            </div>
            <span class="action-label">{{ action.label }}</span>
          </div>
          <div class="action-item danger" @click="handleAction('delete')">
            <div class="action-icon">
              <n-icon size="22"><DeleteIcon /></n-icon>
            </div>
            <span class="action-label">删除规则</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.mobile-rule-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}
.rule-item {
  display: flex;
  align-items: center;
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
  min-height: 64px;
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  box-shadow: var(--shadow-sm);
}
.rule-item:active {
  transform: scale(0.98);
  box-shadow: var(--shadow-md);
}
.rule-content {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}
.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-spacing-xs);
  gap: var(--m-spacing-sm);
}
.rule-name {
  font-weight: 600;
  font-size: var(--m-text-md);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}
.status-tag {
  flex-shrink: 0;
  transform: scale(0.85);
  transform-origin: right center;
}
.rule-details {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}
.rule-keyword {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
.rule-regex {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  padding: 2px 6px;
  border-radius: var(--m-radius-sm);
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
}
.rule-action {
  margin-left: var(--m-spacing-sm);
  flex-shrink: 0;
}
.empty-state {
  padding: 60px var(--m-spacing-lg);
  text-align: center;
}
.empty-state :deep(.n-empty__icon) {
  font-size: 64px;
}
.empty-state :deep(.n-empty__description) {
  font-size: var(--m-text-md);
  color: var(--text-secondary);
  margin-top: var(--m-spacing-md);
}

/* 操作列表样式 */
.action-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}
.action-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}
.action-item:active {
  background: var(--bg-surface-hover);
}
.action-item.danger {
  color: var(--color-error);
}
.action-item.danger .action-icon {
  color: var(--color-error);
}
.action-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  color: var(--text-secondary);
}
.action-item.danger .action-icon {
  background: var(--color-error-bg);
}
.action-label {
  font-size: var(--m-text-md);
  font-weight: 500;
}
</style>
