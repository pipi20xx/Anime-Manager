<script setup lang="ts">
/**
 * AppCardGrid - 响应式卡片网格
 *
 * 替代 NGrid 硬编码 :cols="3"，通过 CSS 自动响应屏幕宽度
 *
 * 用法:
 * <AppCardGrid :cols="3">           桌面 3 列，平板 2 列，手机 1 列
 * <AppCardGrid :cols="'auto'">      自动: 大桌面 4 列 → 手机 1 列
 * <AppCardGrid :cols="2" clickable> 可点击卡片网格
 */

withDefaults(defineProps<{
  /** 桌面端列数 */
  cols?: 2 | 3 | 4 | 'auto'
  /** 子项是否可点击（自动添加 hover/active 效果） */
  clickable?: boolean
}>(), {
  cols: 'auto',
  clickable: false
})
</script>

<template>
  <div
    class="app-card-grid"
    :class="[
      typeof cols === 'number' ? `app-card-grid--${cols}` : 'app-card-grid--auto',
      { 'app-card-grid--clickable': clickable }
    ]"
  >
    <slot />
  </div>
</template>

<style scoped>
.app-card-grid {
  display: grid;
  gap: var(--rsp-grid-gap);
}

/* 默认单列 */
.app-card-grid--auto,
.app-card-grid--2,
.app-card-grid--3,
.app-card-grid--4 {
  grid-template-columns: 1fr;
}

/* 平板：2 列 */
@media (min-width: 768px) {
  .app-card-grid--auto,
  .app-card-grid--2,
  .app-card-grid--3,
  .app-card-grid--4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 桌面 */
@media (min-width: 1024px) {
  .app-card-grid--auto { grid-template-columns: repeat(3, 1fr); }
  .app-card-grid--2 { grid-template-columns: repeat(2, 1fr); }
  .app-card-grid--3 { grid-template-columns: repeat(3, 1fr); }
  .app-card-grid--4 { grid-template-columns: repeat(4, 1fr); }
}

/* 大桌面 */
@media (min-width: 1440px) {
  .app-card-grid--auto { grid-template-columns: repeat(4, 1fr); }
}

/* 可点击卡片 */
.app-card-grid--clickable > :deep(*) {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s ease, border-color var(--transition-normal), box-shadow var(--transition-normal);
}

.app-card-grid--clickable > :deep(*:hover) {
  border-color: var(--app-border-hover) !important;
  box-shadow: var(--shadow-md) !important;
}

.app-card-grid--clickable > :deep(*:active) {
  transform: scale(0.98);
}
</style>
