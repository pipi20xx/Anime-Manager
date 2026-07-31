import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: DefaultLayout,
    meta: { requiresAuth: true },
    children: [
      // === 首页 ===
      {
        path: '',
        name: 'home',
        component: () => import('@/views/HomeView.vue'),
      },

      // === 番剧探索 ===
      {
        path: '/explore',
        name: 'Explore',
        component: () => import('@/views/explore/ExploreView.vue'),
        redirect: '/explore/recommend',
        children: [
          {
            path: 'recommend',
            name: 'ExploreRecommend',
            component: () => import('@/views/explore/ScheduleTab.vue'),
          },
          {
            path: 'seasonal',
            name: 'ExploreSeasonal',
            component: () => import('@/views/explore/SeasonalTab.vue'),
          },
          {
            path: 'discover',
            name: 'ExploreDiscover',
            component: () => import('@/views/explore/DiscoveryTab.vue'),
          },
          {
            path: 'search',
            name: 'ExploreSearch',
            component: () => import('@/views/explore/SearchTab.vue'),
          },
        ],
      },

      // === 订阅管理 ===
      {
        path: '/subscription',
        name: 'Subscription',
        component: () => import('@/views/SubscriptionView.vue'),
      },

      // === 整理管理 ===
      {
        path: '/organizer',
        name: 'Organizer',
        component: () => import('@/views/OrganizerView.vue'),
      },

      // === 文件哈希记录 ===
      {
        path: '/file-hashes',
        name: 'FileHashes',
        component: () => import('@/views/FileHashesView.vue'),
      },

      // === 任务中心 ===
      {
        path: '/task-history',
        name: 'TaskHistory',
        component: () => import('@/views/TaskHistoryView.vue'),
      },

      // === 数据中心 ===
      {
        path: '/data-center',
        name: 'DataCenter',
        component: () => import('@/views/DataCenterView.vue'),
      },

      // === STRM 生成 ===
      {
        path: '/strm',
        name: 'StrmGenerator',
        component: () => import('@/views/StrmView.vue'),
      },

      // === Jackett 搜索 ===
      {
        path: '/jackett',
        name: 'JackettSearch',
        component: () => import('@/views/JackettSearchView.vue'),
      },

      // === 文件浏览 ===
      {
        path: '/files',
        name: 'FileBrowser',
        component: () => import('@/views/FileBrowserView.vue'),
      },

      // === 日历 ===
      {
        path: '/calendar',
        name: 'Calendar',
        component: () => import('@/views/CalendarView.vue'),
      },

      // === AI 实验室 ===
      {
        path: '/ai-lab',
        name: 'AiLab',
        component: () => import('@/views/AiLabView.vue'),
      },

      // === 外部控制 ===
      {
        path: '/external-control',
        name: 'ExternalControl',
        component: () => import('@/views/ExternalControlView.vue'),
      },

      // === 使用指南 ===
      {
        path: '/guide',
        name: 'UsageGuide',
        component: () => import('@/views/GuideView.vue'),
      },

      // === 系统设置 ===
      {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsView.vue'),
      },

      // === 详情页 ===
      {
        path: '/tmdb/:type/:id',
        name: 'TmdbDetail',
        component: () => import('@/views/detail/TmdbDetailView.vue'),
      },
      {
        path: '/bangumi/:id',
        name: 'BangumiDetail',
        component: () => import('@/views/detail/BangumiDetailView.vue'),
      },
      {
        path: '/person/:id',
        name: 'TmdbPersonDetail',
        component: () => import('@/views/detail/TmdbPersonDetailView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // 浏览器前进/后退时恢复位置
    if (savedPosition) return savedPosition
    // 同页面锚点跳转
    if (to.hash) return { el: to.hash }
    // 导航到新页面时回到顶部
    return { top: 0, left: 0 }
  },
})

// 导航守卫
router.beforeEach((to) => {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  if (to.meta.requiresAuth !== false && !token) {
    return { name: 'login' }
  } else if (to.name === 'login' && token) {
    return { name: 'home' }
  }
})

export default router
