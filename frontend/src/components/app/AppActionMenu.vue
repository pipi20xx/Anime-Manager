<script setup lang="ts">
/**
 * AppActionMenu - 统一操作菜单
 *
 * 自动根据设备类型选择交互模式:
 * - Desktop: NDropdown (点击触发下拉菜单)
 * - Mobile:  NDrawer (底部弹出操作抽屉，支持 Android 返回键)
 *
 * 这是少数内部使用 useIsMobile 的组件，
 * 业务页面使用此组件时无需关心设备类型。
 *
 * 用法:
 * <AppActionMenu
 *   :items="[
 *     { key: 'edit', label: '编辑', icon: EditIcon },
 *     { key: 'delete', label: '删除', icon: DeleteIcon, danger: true },
 *   ]"
 *   :trigger-icon="MoreIcon"
 *   @select="handleSelect"
 * />
 */

import { ref, computed, h, type Component } from 'vue'
import { NDropdown, NDrawer, NDrawerContent, NIcon, NButton } from 'naive-ui'
import { useIsMobile } from '../../composables/useIsMobile'
import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle, type ButtonStyleKey } from '../../composables/useButtonStyles'
import { MoreVertOutlined as DefaultMoreIcon } from '@vicons/material'

export interface ActionMenuItem {
  key: string
  label: string
  icon?: Component
  danger?: boolean
}

const props = withDefaults(defineProps<{
  items: ActionMenuItem[]
  /** 触发按钮图标 */
  triggerIcon?: Component
  /** 触发按钮文字（不传则纯图标按钮） */
  triggerText?: string
  /** 触发按钮样式 */
  triggerStyle?: ButtonStyleKey
  /** 按钮大小 */
  size?: 'small' | 'medium' | 'large'
}>(), {
  triggerStyle: 'iconPrimary',
  size: 'small'
})

const emit = defineEmits<{
  (e: 'select', key: string): void
}>()

const { isMobile } = useIsMobile()
const showDrawer = ref(false)
useBackClose(showDrawer)

const triggerBtnStyle = computed(() => getButtonStyle(props.triggerStyle))

const dropdownOptions = computed(() =>
  props.items.map(item => ({
    key: item.key,
    label: item.label,
    icon: item.icon ? () => h(NIcon, null, { default: () => h(item.icon!) }) : undefined,
    props: { style: item.danger ? 'color: var(--color-error)' : '' }
  }))
)

const handleDropdownSelect = (key: string) => {
  emit('select', key)
}

const handleDrawerSelect = (key: string) => {
  showDrawer.value = false
  setTimeout(() => emit('select', key), 200)
}
</script>

<template>
  <!-- Desktop: NDropdown -->
  <n-dropdown
    v-if="!isMobile"
    trigger="click"
    :options="dropdownOptions"
    @select="handleDropdownSelect"
  >
    <n-button v-bind="triggerBtnStyle" :size="size">
      <template #icon>
        <n-icon><component :is="triggerIcon || DefaultMoreIcon" /></n-icon>
      </template>
      <span v-if="triggerText">{{ triggerText }}</span>
    </n-button>
  </n-dropdown>

  <!-- Mobile: NDrawer (底部操作抽屉) -->
  <template v-else>
    <n-button v-bind="triggerBtnStyle" :size="size" @click="showDrawer = true">
      <template #icon>
        <n-icon><component :is="triggerIcon || DefaultMoreIcon" /></n-icon>
      </template>
      <span v-if="triggerText">{{ triggerText }}</span>
    </n-button>

    <n-drawer v-model:show="showDrawer" placement="bottom" :height="items.length * 56 + 100">
      <n-drawer-content closable>
        <template #header>
          <span style="font-size: var(--text-md); font-weight: 600;">操作</span>
        </template>
        <div class="action-sheet-body">
          <div
            v-for="item in items"
            :key="item.key"
            class="action-sheet-item"
            :class="{ danger: item.danger }"
            @click="handleDrawerSelect(item.key)"
          >
            <div class="action-sheet-icon">
              <n-icon v-if="item.icon" size="20"><component :is="item.icon" /></n-icon>
            </div>
            <span class="action-sheet-label">{{ item.label }}</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </template>
</template>

<style scoped>
.action-sheet-body {
  display: flex;
  flex-direction: column;
  padding: 0 var(--space-2);
}

.action-sheet-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  border-radius: var(--radius-lg);
  transition: background 0.15s ease;
  min-height: 48px;
  -webkit-tap-highlight-color: transparent;
}

.action-sheet-item:active {
  background: var(--bg-surface-hover);
}

.action-sheet-item.danger {
  color: var(--color-error);
}

.action-sheet-icon {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-sheet-label {
  font-size: var(--text-md);
  font-weight: 500;
}
</style>
