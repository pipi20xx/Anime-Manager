<script setup lang="ts">
/**
 * AppPageLayout - 统一页面骨架组件
 *
 * 替代 Desktop 的 .page-header + .xxx-view 和 Mobile 的 .m-page + .m-header
 * 通过 CSS 媒体查询自动适配间距和布局，无需 useIsMobile
 *
 * 用法:
 * <AppPageLayout title="订阅与下载" subtitle="RSS 自动化追番">
 *   <template #actions>
 *     <n-button>新增</n-button>
 *   </template>
 *   <div>页面内容</div>
 * </AppPageLayout>
 *
 * 全屏页面 (详情页等):
 * <AppPageLayout full-bleed>
 *   <slot />
 * </AppPageLayout>
 */

defineProps<{
  title?: string
  subtitle?: string
  /** 是否不使用默认 padding（详情页等全屏页面） */
  fullBleed?: boolean
}>()
</script>

<template>
  <div class="app-page" :class="{ 'app-page--full-bleed': fullBleed }">
    <div
      v-if="title || $slots.header || $slots.actions"
      class="app-page-header"
    >
      <div class="app-page-header__left">
        <slot name="header">
          <div v-if="title">
            <h1>{{ title }}</h1>
            <div v-if="subtitle" class="subtitle">{{ subtitle }}</div>
          </div>
        </slot>
      </div>
      <div v-if="$slots.actions" class="app-page-header__actions">
        <slot name="actions" />
      </div>
    </div>
    <div class="app-page-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.app-page-body {
  flex: 1;
  min-height: 0;
}
</style>
