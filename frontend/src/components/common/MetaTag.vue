<script setup lang="ts">
/**
 * MetaTag — 统一元数据标签（v-chip + 悬浮提示）
 *
 * 用法：
 *   <MetaTag label="制作组" class="meta-tag meta-tag--team">ADWeb</MetaTag>
 *   <MetaTag label="TMDB ID" href="..." target="_blank" class="meta-tag meta-tag--tmdb">ID: 123</MetaTag>
 *
 * - `label` 为空时退化为普通 v-chip，不显示悬浮提示
 * - 其余属性（class / color / prepend-icon / @click / href / target 等）透传给 v-chip
 * - 悬浮提示文案即字段中文名，与「整理规则变量手册 / 哈希详情表单」字段文案保持一致
 */
defineOptions({ name: 'MetaTag', inheritAttrs: false })

withDefaults(defineProps<{
  /** 悬浮提示（字段中文名）；为空则不渲染 tooltip */
  label?: string
  size?: string
  variant?: 'flat' | 'tonal' | 'outlined' | 'text' | 'plain' | 'elevated'
}>(), {
  size: 'x-small',
  variant: 'flat',
})
</script>

<template>
  <v-tooltip v-if="label" :text="label" location="top">
    <template #activator="{ props: tipProps }">
      <v-chip v-bind="{ ...tipProps, ...$attrs }" :size="size" :variant="variant">
        <slot />
      </v-chip>
    </template>
  </v-tooltip>

  <v-chip v-else v-bind="$attrs" :size="size" :variant="variant">
    <slot />
  </v-chip>
</template>
