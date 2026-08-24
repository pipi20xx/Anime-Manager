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
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'

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

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: tabs.map(t => ({ title: t.title, icon: t.icon, tab: t.value })),
  modelValue: currentTab,
})
</script>

<template>
  <div class="explore-view pa-4 pa-md-6">
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
