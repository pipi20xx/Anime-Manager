<script setup lang="ts">
/**
 * AppConfirmAction - 统一确认操作
 *
 * 自动根据设备类型选择交互模式:
 * - Desktop: NPopconfirm (hover/click 触发气泡确认)
 * - Mobile:  useDialog (全屏对话框确认)
 *
 * 用法:
 * <AppConfirmAction
 *   content="确定清空所有缓存吗？"
 *   danger
 *   button-style="warning"
 *   button-text="清空缓存"
 *   :button-icon="CleanIcon"
 *   @confirm="handleClear"
 * />
 */

import { type Component } from 'vue'
import { NPopconfirm, NButton, NIcon, useDialog } from 'naive-ui'
import { useIsMobile } from '../../composables/useIsMobile'
import { getButtonStyle, type ButtonStyleKey } from '../../composables/useButtonStyles'

const props = withDefaults(defineProps<{
  /** 确认提示内容 */
  content: string
  /** 确认标题（Mobile Dialog 用） */
  title?: string
  /** 确认按钮文字 */
  confirmText?: string
  /** 取消按钮文字 */
  cancelText?: string
  /** 是否危险操作 */
  danger?: boolean
  /** 触发按钮样式 key */
  buttonStyle?: ButtonStyleKey
  /** 触发按钮文字 */
  buttonText?: string
  /** 触发按钮图标 */
  buttonIcon?: Component
  /** 按钮大小 */
  size?: 'small' | 'medium' | 'large'
}>(), {
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  buttonStyle: 'iconPrimary',
  size: 'small'
})

const emit = defineEmits<{
  (e: 'confirm'): void
}>()

const { isMobile } = useIsMobile()
const dialog = useDialog()

const triggerBtnStyle = getButtonStyle(props.buttonStyle)

const handleConfirm = () => {
  emit('confirm')
}

const triggerMobileDialog = () => {
  const dialogMethod = props.danger ? dialog.error : dialog.warning
  dialogMethod.call(dialog, {
    title: props.title || '确认操作',
    content: props.content,
    positiveText: props.confirmText,
    negativeText: props.cancelText,
    onPositiveClick: () => handleConfirm()
  })
}
</script>

<template>
  <!-- Desktop: NPopconfirm -->
  <n-popconfirm
    v-if="!isMobile"
    :positive-text="confirmText"
    :negative-text="cancelText"
    @positive-click="handleConfirm"
  >
    <template #trigger>
      <n-button v-bind="triggerBtnStyle" :size="size">
        <template v-if="buttonIcon" #icon><n-icon><component :is="buttonIcon" /></n-icon></template>
        <span v-if="buttonText">{{ buttonText }}</span>
      </n-button>
    </template>
    {{ content }}
  </n-popconfirm>

  <!-- Mobile: 触发 Dialog -->
  <n-button
    v-else
    v-bind="triggerBtnStyle"
    :size="size"
    @click="triggerMobileDialog"
  >
    <template v-if="buttonIcon" #icon><n-icon><component :is="buttonIcon" /></n-icon></template>
    <span v-if="buttonText">{{ buttonText }}</span>
  </n-button>
</template>
