<script setup lang="ts">
/**
 * SectionHeader — 区块标题
 *
 * 统一「20px 图标 + text-subtitle-1 加粗标题」的区块头结构。
 *
 * Props:
 *  - icon: 图标名 (mdi)
 *  - title: 标题文本 (含插值/混排时改用默认 slot)
 *  - cardTitle: 以 v-card-title 渲染（玻璃卡片头部场景，自带 pa-4 pb-2）
 *  - iconColor: 图标颜色，默认 primary
 *
 * Slots:
 *  - default: 标题区自定义内容（覆盖 title）
 *  - actions: 标题右侧附加内容（状态 chip 等，位于同一行）
 */
defineOptions({ name: 'SectionHeader' })

withDefaults(defineProps<{
  icon: string
  title?: string
  cardTitle?: boolean
  iconColor?: string
}>(), {
  title: '',
  cardTitle: false,
  iconColor: 'primary',
})
</script>

<template>
  <v-card-title v-if="cardTitle" class="pa-4 pb-2 d-flex align-center ga-2">
    <v-icon :icon="icon" :color="iconColor" size="20" />
    <span class="text-subtitle-1 font-weight-bold"><slot>{{ title }}</slot></span>
    <slot name="actions" />
  </v-card-title>
  <div v-else class="d-flex align-center ga-2">
    <v-icon :icon="icon" :color="iconColor" size="20" />
    <span class="text-subtitle-1 font-weight-bold"><slot>{{ title }}</slot></span>
    <slot name="actions" />
  </div>
</template>
