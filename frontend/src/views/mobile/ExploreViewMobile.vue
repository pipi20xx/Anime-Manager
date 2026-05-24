<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute, RouterView } from 'vue-router'
import { NTabs, NTabPane, NIcon } from 'naive-ui'
import {
  RecommendOutlined as RecommendIcon,
  ExploreOutlined as ExploreIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'

const router = useRouter()
const route = useRoute()

const currentTab = computed({
  get: () => {
    const name = route.name as string
    if (name?.includes('Recommend')) return 'recommend'
    if (name?.includes('Discover')) return 'discover'
    if (name?.includes('Search')) return 'search'
    return 'recommend'
  },
  set: (value: string) => {
    const routeMap: Record<string, string> = {
      recommend: 'ExploreRecommend',
      discover: 'ExploreDiscover',
      search: 'ExploreSearch'
    }
    router.push({ name: routeMap[value] })
  }
})
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
       <router-view v-slot="{ Component, route: r }">
         <transition name="fade" mode="out-in">
           <component :is="Component" :key="r.fullPath" />
         </transition>
       </router-view>
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

.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>