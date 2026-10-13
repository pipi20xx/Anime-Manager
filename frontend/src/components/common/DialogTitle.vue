<script setup lang="ts">
/**
 * DialogTitle — 弹窗标题行
 *
 * 统一「图标(可选) + 标题 + 右侧附加内容(可选) + 关闭按钮」结构，
 * 替代各弹窗逐份手写的 v-card-title + v-spacer + 关闭按钮。
 *
 * Props:
 *  - title: 标题文本 (可选；含插值/混排时改用默认 slot)
 *  - icon: 图标名 (可选，mdi)
 *  - iconColor: 图标颜色 (可选；不传则继承默认文字色)
 *
 * Slots:
 *  - default: 标题区自定义内容（覆盖 title 文本）
 *  - icon: 自定义图标内容（覆盖 icon prop）
 *  - append: 标题右侧、关闭按钮之前的附加内容（状态 chip 等）
 *  - actions: 最右侧动作区（默认渲染关闭按钮；传入后需自行包含关闭按钮）
 *
 * Emits:
 *  - close: 点击默认关闭按钮时触发
 */
defineOptions({ name: 'DialogTitle' })

withDefaults(defineProps<{
  title?: string
  icon?: string
  iconColor?: string
}>(), {
  title: '',
  icon: '',
  iconColor: undefined,
})

const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <v-card-title class="pa-4 d-flex align-center">
    <v-icon v-if="icon || $slots.icon" start :color="iconColor">
      <slot name="icon">{{ icon }}</slot>
    </v-icon>
    <slot>{{ title }}</slot>
    <slot name="append" />
    <v-spacer />
    <slot name="actions">
      <v-btn icon="mdi-close" variant="text" size="small" aria-label="关闭" @click="emit('close')" />
    </slot>
  </v-card-title>
</template>
