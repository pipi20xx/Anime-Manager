import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Explore',
    component: () => import('../views/desktop/ExploreViewDesktop.vue'),
    redirect: '/explore/recommend',
    children: [
      {
        path: '/explore/recommend',
        name: 'ExploreRecommend',
        component: () => import('../views/explore/desktop/ScheduleTabDesktop.vue')
      },
      {
        path: '/explore/discover',
        name: 'ExploreDiscover',
        component: () => import('../views/explore/desktop/DiscoveryTabDesktop.vue')
      },
      {
        path: '/explore/search',
        name: 'ExploreSearch',
        component: () => import('../views/explore/desktop/SearchTabDesktop.vue')
      }
    ]
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../components/desktop/SettingsViewDesktop.vue')
  },
  {
    path: '/guide',
    name: 'UsageGuide',
    component: () => import('../views/desktop/UsageGuideDesktop.vue')
  },
  {
    path: '/files',
    name: 'FileBrowser',
    component: () => import('../views/desktop/FileBrowserViewDesktop.vue')
  },
  {
    path: '/organizer',
    name: 'Organizer',
    component: () => import('../views/desktop/OrganizerViewDesktop.vue')
  },
  {
    path: '/organize-history',
    name: 'OrganizeHistory',
    component: () => import('../components/desktop/OrganizeHistoryDesktop.vue')
  },
  {
    path: '/subscription',
    name: 'Subscription',
    component: () => import('../views/desktop/SubscriptionViewDesktop.vue')
  },
  {
    path: '/strm',
    name: 'StrmGenerator',
    component: () => import('../views/desktop/StrmGeneratorViewDesktop.vue')
  },
  {
    path: '/database',
    name: 'Database',
    component: () => import('../components/desktop/DatabaseViewDesktop.vue')
  },
  {
    path: '/tmdb-full',
    name: 'TmdbFullData',
    component: () => import('../components/desktop/TmdbFullDataViewDesktop.vue')
  },
  {
    path: '/external-control',
    name: 'ExternalControl',
    component: () => import('../views/desktop/ExternalControlDesktop.vue')
  },
  {
    path: '/calendar',
    name: 'Calendar',
    component: () => import('../components/desktop/CalendarViewDesktop.vue')
  },
  {
    path: '/tasks',
    name: 'TaskHistory',
    component: () => import('../views/desktop/TaskHistoryViewDesktop.vue')
  },
  {
    path: '/file-hashes',
    name: 'FileHashes',
    component: () => import('../views/desktop/FileHashesViewDesktop.vue')
  },
  {
    path: '/jackett-search',
    name: 'JackettSearch',
    component: () => import('../views/desktop/JackettSearchViewDesktop.vue')
  },
  {
    path: '/appearance',
    name: 'Appearance',
    component: () => import('../views/desktop/AppearanceViewDesktop.vue')
  },
  {
    path: '/tmdb/:type/:id',
    name: 'TmdbDetail',
    component: () => import('../views/desktop/TmdbDetailViewDesktop.vue')
  },
  {
    path: '/bangumi/:id',
    name: 'BangumiDetail',
    component: () => import('../views/desktop/BangumiDetailViewDesktop.vue')
  },
  {
    path: '/person/:id',
    name: 'TmdbPersonDetail',
    component: () => import('../views/desktop/TmdbPersonDetailViewDesktop.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
