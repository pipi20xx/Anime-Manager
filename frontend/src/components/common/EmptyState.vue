<script setup lang="ts">
/**
 * EmptyState — 空状态 / 占位提示
 *
 * 统一「大图标 + 标题(可选) + 描述(可选) + 操作区(可选)」的居中占位结构，
 * 替代各页面逐份手写的 text-center pa-8 三件套。
 *
 * Props:
 *  - icon: 图标名 (mdi)
 *  - title: 主标题 (可选，如「暂无任务记录」)
 *  - description: 描述文本 (可选)
 *  - iconColor: 图标颜色，默认 primary；错误占位传 error
 *  - pad: 内边距档位，default = pa-8，large = pa-12（大页面首屏占位）
 *
 * Slots:
 *  - actions: 底部操作区（按钮等），仅传入时渲染
 */
defineOptions({ name: 'EmptyState' })

withDefaults(defineProps<{
  icon: string
  title?: string
  description?: string
  iconColor?: string
  pad?: 'default' | 'large'
}>(), {
  title: '',
  description: '',
  iconColor: 'primary',
  pad: 'default',
})
</script>

<template>
  <div class="text-center" :class="pad === 'large' ? 'pa-12' : 'pa-8'">
    <v-icon :icon="icon" size="64" :color="iconColor" class="mb-4" />
    <div v-if="title" class="text-h6 font-weight-medium">{{ title }}</div>
    <div v-if="description" class="text-body-2 text-medium-emphasis" :class="title ? 'mt-2' : ''">
      {{ description }}
    </div>
    <div v-if="$slots.actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>
