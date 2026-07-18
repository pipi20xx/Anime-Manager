<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute, RouterView } from 'vue-router'
import { NTabs, NTabPane, NIcon } from 'naive-ui'
import {
  StarIcon as RecommendIcon,
  GlobeAltIcon as ExploreIcon,
  MagnifyingGlassIcon as SearchIcon
} from '@heroicons/vue/24/outline'

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
  <div class="explore-view-container">
    <div class="explore-header">
       <n-tabs 
          v-model:value="currentTab" 
          type="line"
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
       <router-view v-slot="{ Component, route: r }">
         <transition name="fade" mode="out-in">
           <component :is="Component" :key="r.fullPath" />
         </transition>
       </router-view>
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