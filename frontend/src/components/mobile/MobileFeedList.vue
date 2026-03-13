<script setup lang="ts">
import { h } from 'vue'
import { NList, NListItem, NTag, NButton, NIcon, NDropdown, NText, NEmpty, useDialog } from 'naive-ui'
import {
  MoreVertOutlined as MoreIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  ListAltOutlined as ListIcon,
  HistoryOutlined as ResetIcon
} from '@vicons/material'

import { getButtonStyle } from '../../composables/useButtonStyles'

defineProps<{
  feeds: any[]
}>()

const emit = defineEmits<{
  (e: 'edit', feed: any): void
  (e: 'delete', id: number): void
  (e: 'reset', id: number): void
  (e: 'viewItems', feed: any): void
}>()

const dialog = useDialog()

const createOptions = (feed: any) => [
  { label: '编辑源', key: 'edit', icon: () => h(NIcon, null, { default: () => h(EditIcon) }) },
  { label: '查看内容', key: 'view', icon: () => h(NIcon, null, { default: () => h(ListIcon) }) },
  { label: '清除历史', key: 'reset', icon: () => h(NIcon, null, { default: () => h(ResetIcon) }) },
  { type: 'divider' },
  { label: '删除', key: 'delete', icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }), style: { color: 'var(--n-error-color)' } }
]

const handleSelect = (key: string, feed: any) => {
  if (key === 'edit') emit('edit', feed)
  else if (key === 'view') emit('viewItems', feed)
  else if (key === 'reset') {
    dialog.warning({
      title: '清除历史',
      content: `确定要清除「${feed.title || '未命名'}」的下载历史吗？`,
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
        h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { emit('reset', feed.id); dialog.destroyAll() } }, { default: () => '确定' })
      ])
    })
  }
  else if (key === 'delete') {
    dialog.warning({
      title: '删除确认',
      content: `确定要删除订阅源「${feed.title || '未命名'}」吗？`,
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
        h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { emit('delete', feed.id); dialog.destroyAll() } }, { default: () => '删除' })
      ])
    })
  }
}
</script>

<template>
  <div class="mobile-feed-list">
    <div v-if="feeds.length > 0">
      <div v-for="feed in feeds" :key="feed.id" class="feed-item" @click="emit('edit', feed)">
        <div class="feed-content">
          <div class="feed-header">
            <span class="feed-title">{{ feed.title || '未命名' }}</span>
            <n-tag size="small" :type="feed.enabled ? 'success' : 'error'" round style="zoom: 0.8">
              {{ feed.enabled ? '监控' : '暂停' }}
            </n-tag>
          </div>
          <div class="feed-url">{{ feed.url }}</div>
        </div>
        <div class="feed-action" @click.stop>
          <n-dropdown trigger="click" :options="createOptions(feed)" @select="(k) => handleSelect(k, feed)" placement="bottom-end">
            <n-button v-bind="getButtonStyle('icon')" size="small">
              <template #icon><n-icon><MoreIcon/></n-icon></template>
            </n-button>
          </n-dropdown>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无订阅源" />
    </div>
  </div>
</template>

<style scoped>
.mobile-feed-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}
.feed-item {
  display: flex;
  align-items: center;
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
  min-height: 56px;
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.feed-item:active {
  transform: scale(0.98);
  box-shadow: var(--shadow-sm);
}
.feed-content {
  flex: 1;
  overflow: hidden;
}
.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.feed-title {
  font-weight: bold;
  font-size: 14px;
  margin-right: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.feed-url {
  font-size: 11px;
  color: var(--n-text-color-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: var(--opacity-tertiary);
}
.feed-action {
  margin-left: 8px;
}
.empty-state {
  padding: 40px 0;
  text-align: center;
}
</style>
