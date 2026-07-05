<script setup lang="ts">
import { NCard } from 'naive-ui'

/**
 * AppGlassCard - 统一的卡片封装组件
 *
 * 功能:
 * - 包装 NCard，支持外观自定义
 * - 通过 appearance-key prop 实现实例级独立自定义
 * - 透传所有 attrs 和 slots
 *
 * 使用示例:
 * <AppGlassCard
 *   appearance-key="strm-task-card"
 *   bordered
 *   embedded
 *   class="task-card"
 *   @click="openEdit"
 * >
 *   <template #header>标题</template>
 *   内容
 * </AppGlassCard>
 *
 * 不传 appearance-key 时走全局默认外观
 */

defineProps<{
  /**
   * 实例级外观 key：用于独立自定义此卡片的外观
   * 传入后会在 NCard 根元素上设置 data-app-instance 属性，
   * 配合 appearanceStore 注入的 scoped CSS 变量实现独立自定义
   * 不传则走全局默认外观
   */
  appearanceKey?: string
}>()
</script>

<template>
  <NCard
    v-bind="$attrs"
    :data-app-instance="appearanceKey || undefined"
  >
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </NCard>
</template>
