<script setup lang="ts">
import { NTabs, NTabPane, NIcon } from 'naive-ui'
import {
  RecommendOutlined as RecommendIcon,
  ExploreOutlined as ExploreIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import { useExploreView } from '../../composables/views/useExploreView'

const { currentTab, activeComponent } = useExploreView()
</script>

<template>
  <div class="m-page m-page-safe-bottom">
    <div class="explore-header">
       <n-tabs
          v-model:value="currentTab"
          type="segment"
          animated
          class="m-tabs m-tabs-segment"
          style="width: 100%"
       >
          <n-tab-pane name="recommend" tab="推荐">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><RecommendIcon /></n-icon>
                   <span>推荐</span>
                </div>
             </template>
          </n-tab-pane>
          <n-tab-pane name="discover" tab="探索">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><ExploreIcon /></n-icon>
                   <span>探索</span>
                </div>
             </template>
          </n-tab-pane>
          <n-tab-pane name="search" tab="搜索">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><SearchIcon /></n-icon>
                   <span>搜索</span>
                </div>
             </template>
          </n-tab-pane>
       </n-tabs>
    </div>

    <div class="m-page-scrollable">
       <keep-alive>
          <component :is="activeComponent" />
       </keep-alive>
    </div>
  </div>
</template>

<style scoped>
.explore-header {
  display: flex;
  justify-content: center;
  padding: var(--m-spacing-md) var(--m-spacing-lg) var(--m-spacing-lg);
  width: 100%;
  box-sizing: border-box;
  flex-shrink: 0;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-xs);
  font-weight: 600;
  font-size: var(--m-text-sm);
}

.m-tabs :deep(.n-tabs-nav) {
  padding: 0;
}

.m-tabs :deep(.n-tabs-pane-wrapper) {
  display: none;
}
</style>
