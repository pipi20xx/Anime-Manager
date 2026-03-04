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
  <div class="explore-view-mobile">
    <div class="explore-header-mobile">
       <n-tabs 
          v-model:value="currentTab" 
          type="segment" 
          animated
          class="custom-tabs"
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

    <div class="explore-content-mobile">
       <keep-alive>
          <component :is="activeComponent" />
       </keep-alive>
    </div>
  </div>
</template>

<style scoped>
.explore-view-mobile {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  box-sizing: border-box;
}

.explore-header-mobile {
  display: flex;
  justify-content: center;
  padding: 8px 12px 16px 12px;
  width: 100%;
  box-sizing: border-box;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  font-size: 13px;
}

.explore-content-mobile {
  flex: 1;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
