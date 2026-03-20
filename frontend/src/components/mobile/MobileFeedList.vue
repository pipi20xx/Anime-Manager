<script setup lang="ts">
import { ref, h } from 'vue'
import { NTag, NButton, NIcon, NDrawer, NDrawerContent, NEmpty, useDialog } from 'naive-ui'
import {
  MoreVertOutlined as MoreIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  ListAltOutlined as ListIcon,
  HistoryOutlined as ResetIcon
} from '@vicons/material'

import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  feeds: any[]
}>()

const emit = defineEmits<{
  (e: 'edit', feed: any): void
  (e: 'delete', id: number): void
  (e: 'reset', id: number): void
  (e: 'viewItems', feed: any): void
}>()

const dialog = useDialog()

// 操作抽屉状态
const showActionDrawer = ref(false)
const currentFeed = ref<any>(null)
useBackClose(showActionDrawer)

const feedActions = [
  { key: 'edit', label: '编辑源', icon: EditIcon },
  { key: 'view', label: '查看内容', icon: ListIcon },
  { key: 'reset', label: '清除历史', icon: ResetIcon },
]

const openActions = (feed: any, e: Event) => {
  e.stopPropagation()
  currentFeed.value = feed
  showActionDrawer.value = true
}

const handleAction = (key: string) => {
  const feed = currentFeed.value
  if (!feed) return

  showActionDrawer.value = false
  setTimeout(() => {
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
  }, 300)
}
</script>

<template>
  <div class="mobile-feed-list">
    <div v-if="feeds.length > 0">
      <div v-for="feed in feeds" :key="feed.id" class="feed-item m-touchable" @click="emit('edit', feed)">
        <div class="feed-content">
          <div class="feed-header">
            <span class="feed-title">{{ feed.title || '未命名' }}</span>
            <n-tag size="small" round :bordered="false" :style="feed.enabled ? { color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' } : { color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' }" class="status-tag">
              {{ feed.enabled ? '监控' : '暂停' }}
            </n-tag>
          </div>
          <div class="feed-url">{{ feed.url }}</div>
        </div>
        <div class="feed-action" @click.stop="openActions(feed, $event)">
          <n-button v-bind="getButtonStyle('icon')" size="small">
            <template #icon><n-icon><MoreIcon/></n-icon></template>
          </n-button>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无订阅源" />
    </div>

    <!-- 操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="(feedActions.length + 1) * 100 + 60" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content :title="currentFeed?.title || '订阅源操作'" closable :native-scrollbar="false">
        <div class="action-list">
          <div v-for="action in feedActions" :key="action.key" class="action-item" @click="handleAction(action.key)">
            <div class="action-icon">
              <n-icon size="22"><component :is="action.icon" /></n-icon>
            </div>
            <span class="action-label">{{ action.label }}</span>
          </div>
          <div class="action-item danger" @click="handleAction('delete')">
            <div class="action-icon">
              <n-icon size="22"><DeleteIcon /></n-icon>
            </div>
            <span class="action-label">删除订阅源</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
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
  min-height: 64px;
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  box-shadow: var(--shadow-sm);
}
.feed-item:active {
  transform: scale(0.98);
  box-shadow: var(--shadow-md);
}
.feed-content {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}
.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-spacing-xs);
  gap: var(--m-spacing-sm);
}
.feed-title {
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
.feed-url {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.feed-action {
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
