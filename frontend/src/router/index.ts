import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Explore',
    component: () => import('../views/ExploreView.vue')
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/cache',
    name: 'Cache',
    component: () => import('../views/CacheView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue')
  },
  {
    path: '/guide',
    name: 'UsageGuide',
    component: () => import('../views/UsageGuideView.vue')
  },
  {
    path: '/files',
    name: 'FileBrowser',
    component: () => import('../views/FileBrowserView.vue')
  },
  {
    path: '/organizer',
    name: 'Organizer',
    component: () => import('../views/OrganizerView.vue')
  },
  {
    path: '/organize-history',
    name: 'OrganizeHistory',
    component: () => import('../views/OrganizeHistoryView.vue')
  },
  {
    path: '/subscription',
    name: 'Subscription',
    component: () => import('../views/SubscriptionView.vue')
  },
  {
    path: '/strm',
    name: 'StrmGenerator',
    component: () => import('../views/StrmGeneratorView.vue')
  },
  {
    path: '/database',
    name: 'Database',
    component: () => import('../views/DatabaseView.vue')
  },
  {
    path: '/tmdb-full',
    name: 'TmdbFullData',
    component: () => import('../views/TmdbFullDataView.vue')
  },
  {
    path: '/external-control',
    name: 'ExternalControl',
    component: () => import('../views/ExternalControlView.vue')
  },
  {
    path: '/calendar',
    name: 'Calendar',
    component: () => import('../views/CalendarView.vue')
  },
  {
    path: '/tasks',
    name: 'TaskHistory',
    component: () => import('../views/TaskHistoryView.vue')
  },
  {
    path: '/tmdb/:id',
    name: 'TmdbDetail',
    component: () => import('../views/TmdbDetailView.vue')
  },
  {
    path: '/bangumi/:id',
    name: 'BangumiDetail',
    component: () => import('../views/BangumiDetailView.vue')
  },
  {
    path: '/person/:id',
    name: 'TmdbPersonDetail',
    component: () => import('../views/TmdbPersonDetailView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
