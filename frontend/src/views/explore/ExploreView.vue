<script setup lang="ts">
/**
 * ExploreView — 番剧探索主页面
 *
 * 包含四个子 Tab:
 * - 播出时间表 (ScheduleTab)
 * - 季度番剧表 (SeasonalTab)
 * - 探索索引 (DiscoveryTab)
 * - 聚合搜索 (SearchTab)
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

defineOptions({ name: 'ExploreView' })

const route = useRoute()
const router = useRouter()

const currentTab = computed({
  get: () => {
    const name = route.name as string
    if (name?.includes('Seasonal')) return 'seasonal'
    if (name?.includes('Recommend')) return 'recommend'
    if (name?.includes('Discover')) return 'discover'
    if (name?.includes('Search')) return 'search'
    return 'recommend'
  },
  set: (value: string) => {
    const routeMap: Record<string, string> = {
      recommend: 'ExploreRecommend',
      seasonal: 'ExploreSeasonal',
      discover: 'ExploreDiscover',
      search: 'ExploreSearch',
    }
    router.push({ name: routeMap[value] })
  },
})

const tabs = [
  { value: 'seasonal', title: '季度番剧表', icon: 'mdi-calendar-month-outline' },
  { value: 'recommend', title: '播出时间表', icon: 'mdi-star-outline' },
  { value: 'discover', title: '探索', icon: 'mdi-compass-outline' },
  { value: 'search', title: '搜索', icon: 'mdi-magnify' },
]
</script>

<template>
  <div class="explore-view">
    <!-- 标签导航 -->
    <div class="explore-header d-flex justify-center py-4">
      <v-tabs v-model="currentTab" align-tabs="center" color="primary" style="max-width: 560px">
        <v-tab v-for="tab in tabs" :key="tab.value" :value="tab.value">
          <v-icon start size="18">{{ tab.icon }}</v-icon>
          {{ tab.title }}
        </v-tab>
      </v-tabs>
    </div>

    <!-- 子路由内容 -->
    <div class="explore-content">
      <router-view v-slot="{ Component, route: r }">
        <keep-alive>
          <component :is="Component" :key="r.fullPath" />
        </keep-alive>
      </router-view>
    </div>
  </div>
</template>
