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
  <div class="explore-view-container">
    <div class="explore-header">
       <n-tabs 
          v-model:value="currentTab" 
          type="segment" 
          animated
          class="custom-tabs"
          style="width: 420px"
       >
          <n-tab-pane name="recommend" tab="推荐看板">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><RecommendIcon /></n-icon>
                   <span>推荐</span>
                </div>
             </template>
          </n-tab-pane>
          <n-tab-pane name="discover" tab="探索索引">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><ExploreIcon /></n-icon>
                   <span>探索</span>
                </div>
             </template>
          </n-tab-pane>
          <n-tab-pane name="search" tab="聚合搜索">
             <template #tab>
                <div class="tab-label">
                   <n-icon size="18"><SearchIcon /></n-icon>
                   <span>搜索</span>
                </div>
             </template>
          </n-tab-pane>
       </n-tabs>
    </div>

    <div class="explore-content">
       <keep-alive>
          <component :is="activeComponent" />
       </keep-alive>
    </div>
  </div>
</template>

<style scoped>
.explore-view-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.explore-header {
  display: flex;
  justify-content: center;
  padding: 16px 0 24px 0;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.explore-content {
  flex: 1;
  width: 100%;
}
</style>
