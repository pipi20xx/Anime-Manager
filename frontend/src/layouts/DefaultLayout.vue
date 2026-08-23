<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore, useSystemStore } from '@/stores'
import { ConfirmDialog, LogTerminal, AppNotification } from '@/components/common'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const systemStore = useSystemStore()
const appVersion = __APP_VERSION__ as string
const drawer = ref(true)
const rail = ref(false)
const isMobile = ref(false)

// 导航分组 — 与旧前端功能一一对应
const navGroups = [
  {
    key: 'core',
    label: '核心功能',
    items: [
      { title: '番剧探索', icon: 'mdi-compass-outline', to: '/explore' },
      { title: '订阅管理', icon: 'mdi-rss', to: '/subscription' },
      { title: '整理管理', icon: 'mdi-folder-sync-outline', to: '/organizer' },
      { title: '链接同步', icon: 'mdi-link-variant', to: '/strm' },
    ],
  },
  {
    key: 'tools',
    label: '工具',
    items: [
      { title: '识别测试', icon: 'mdi-head-cog-outline', to: '/' },
      { title: '追剧日历', icon: 'mdi-calendar-month-outline', to: '/calendar' },
      { title: '资源搜索', icon: 'mdi-magnify-scan', to: '/jackett' },
      { title: '文件浏览', icon: 'mdi-file-tree-outline', to: '/files' },
      { title: 'AI 实验室', icon: 'mdi-robot-outline', to: '/ai-lab' },
    ],
  },
  {
    key: 'data',
    label: '数据中心',
    items: [
      { title: '数据中心', icon: 'mdi-database-outline', to: '/data-center' },
      { title: '任务中心', icon: 'mdi-clipboard-list-outline', to: '/task-history' },
      { title: '文件哈希', icon: 'mdi-fingerprint', to: '/file-hashes' },
    ],
  },
  {
    key: 'system',
    label: '系统',
    items: [
      { title: '系统设置', icon: 'mdi-cog-outline', to: '/settings' },
      { title: '外部控制', icon: 'mdi-api', to: '/external-control' },
      { title: '使用指南', icon: 'mdi-book-open-page-variant-outline', to: '/guide' },
    ],
  },
]

// 扁平化的导航项（用于查找当前标题）
const allNavItems = navGroups.flatMap(g => g.items)

const currentTitle = computed(() => {
  const item = allNavItems.find(n => {
    if (n.to === '/') return route.path === '/'
    return route.path.startsWith(n.to)
  })
  return item?.title ?? '番剧管家'
})

// 检查某个导航组是否应该高亮
function isGroupActive(group: typeof navGroups[0]): boolean {
  return group.items.some(item => {
    if (item.to === '/') return route.path === '/'
    return route.path.startsWith(item.to)
  })
}

function handleLogout() {
  systemStore.logout()
  router.push('/login')
}

function checkMobile() {
  isMobile.value = window.innerWidth < 960
  if (isMobile.value) drawer.value = false
}

// 路由变化时，移动端自动关闭抽屉
watch(() => route.path, () => {
  if (isMobile.value) drawer.value = false
})

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<template>
  <v-app>
    <div class="glass-grain" />

    <!-- 侧边导航 -->
    <v-navigation-drawer
      v-model="drawer"
      :rail="rail && !isMobile"
      :permanent="!isMobile"
      :temporary="isMobile"
      width="256"
      rail-width="72"
    >
      <!-- Logo 区域 -->
      <div class="logo-header" :class="{ 'logo-header--rail': rail && !isMobile }">
        <v-avatar class="liquid-avatar" rounded="xl" size="40">
          <img src="/favicon.svg" alt="番剧管家" class="app-logo" />
        </v-avatar>
        <div v-if="!rail || isMobile" class="logo-text">
          <div class="text-subtitle-1 font-weight-bold liquid-glass-subtitle">番剧管家</div>
          <div class="text-caption text-medium-emphasis">Anime Manager</div>
          <div class="sidebar-version">v{{ appVersion }}</div>
        </div>
        <v-btn
          v-if="!isMobile"
          variant="text"
          :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
          size="x-small"
          density="comfortable"
          @click.stop="rail = !rail"
        />
      </div>

      <v-divider />

      <!-- 导航菜单分组 -->
      <v-list density="compact" nav class="px-2 py-2 flex-grow-0 overflow-y-auto">
        <template v-for="group in navGroups" :key="group.key">
          <!-- 分组标题（非 rail 模式显示） -->
          <div v-if="!rail || isMobile" class="nav-group-label">
            <span class="text-caption text-medium-emphasis font-weight-medium text-uppercase tracking-wider">
              {{ group.label }}
            </span>
          </div>

          <v-list-item
            v-for="item in group.items"
            :key="item.to"
            :prepend-icon="item.icon"
            :title="item.title"
            :to="item.to"
            :value="item.to"
            rounded="xl"
            class="mb-1"
            :exact="item.to === '/'"
          />

          <v-divider v-if="group.key !== 'system'" class="my-2 mx-2" />
        </template>
      </v-list>

      <template #append>
        <v-divider />
        <!-- 进度指示 -->
        <div v-if="systemStore.hasActiveProgress" class="px-4 py-3">
          <div class="d-flex align-center mb-2">
            <v-progress-circular indeterminate :size="16" :width="2" color="primary" class="mr-2" />
            <span class="text-caption font-weight-medium text-truncate">处理中...</span>
          </div>
          <v-progress-linear color="primary" height="6" rounded="pill" indeterminate />
        </div>
      </template>
    </v-navigation-drawer>

    <!-- 顶栏 -->
    <v-app-bar elevation="0" density="comfortable">
      <v-app-bar-nav-icon v-if="isMobile" @click="drawer = !drawer" />
      <v-app-bar-title class="font-weight-bold text-body-1">{{ currentTitle }}</v-app-bar-title>

      <template #append>
        <div class="d-flex align-center ga-2">
          <!-- WS 连接状态 -->
          <v-chip
            :color="systemStore.isConnected ? 'success' : 'error'"
            size="small"
            variant="tonal"
            label
          >
            <v-icon start size="14">{{ systemStore.isConnected ? 'mdi-access-point-check' : 'mdi-access-point-off' }}</v-icon>
            {{ systemStore.isConnected ? '已连接' : '断开' }}
          </v-chip>

          <!-- 系统日志 -->
          <v-btn
            variant="text"
            density="comfortable"
            size="small"
            color="info"
            icon="mdi-card-text-outline"
            @click="systemStore.showLogModal = true"
          />

          <!-- 深色/浅色切换（ACG 主题下禁用，仅支持暗色） -->
          <v-tooltip :text="themeStore.glassTheme === 'acg' ? 'ACG 主题仅支持暗色模式' : '深色 / 浅色'" location="bottom">
            <template #activator="{ props: tooltipProps }">
              <v-btn
                v-bind="tooltipProps"
                variant="text"
                density="comfortable"
                size="small"
                :color="themeStore.isDarkMode ? 'warning' : 'info'"
                :icon="themeStore.isDarkMode ? 'mdi-white-balance-sunny' : 'mdi-weather-night'"
                :disabled="themeStore.glassTheme === 'acg'"
                @click="themeStore.toggleDarkMode()"
              />
            </template>
          </v-tooltip>

          <!-- 主题选择菜单 -->
          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                variant="text"
                density="comfortable"
                size="small"
                :color="{ liquid: 'accent', acg: 'secondary', classic: 'primary' }[themeStore.glassTheme]"
                :icon="{ liquid: 'mdi-layers-outline', acg: 'mdi-image-multiple', classic: 'mdi-contrast-box' }[themeStore.glassTheme]"
              />
            </template>
            <v-list density="compact" min-width="180" nav>
              <v-list-item
                prepend-icon="mdi-layers-outline"
                title="液态玻璃"
                subtitle="Apple 液态玻璃风格"
                :active="themeStore.glassTheme === 'liquid'"
                active-color="primary"
                @click="themeStore.setGlassTheme('liquid')"
              />
              <v-list-item
                prepend-icon="mdi-image-multiple"
                title="ACG 毛玻璃"
                subtitle="二次元壁纸 + 暗色毛玻璃"
                :active="themeStore.glassTheme === 'acg'"
                active-color="primary"
                @click="themeStore.setGlassTheme('acg')"
              />
              <v-list-item
                prepend-icon="mdi-contrast-box"
                title="经典实色"
                subtitle="纯白/纯黑 最简风格"
                :active="themeStore.glassTheme === 'classic'"
                active-color="primary"
                @click="themeStore.setGlassTheme('classic')"
              />
            </v-list>
          </v-menu>

          <!-- 用户菜单 -->
          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-chip size="small" variant="outlined" label v-bind="menuProps" class="cursor-pointer">
                <v-icon start size="14">mdi-account-circle</v-icon>
                {{ systemStore.username || 'admin' }}
                <v-icon end size="14">mdi-chevron-down</v-icon>
              </v-chip>
            </template>
            <v-list density="compact" min-width="160">
              <v-list-item prepend-icon="mdi-logout" title="退出登录" @click="handleLogout" rounded="xl" color="error" />
            </v-list>
          </v-menu>
        </div>
      </template>
    </v-app-bar>

    <!-- 主内容 -->
    <v-main>
      <router-view v-slot="{ Component, route: r }">
        <keep-alive :include="[]">
          <component :is="Component" :key="r.fullPath" />
        </keep-alive>
      </router-view>
    </v-main>

    <!-- 全局组件 -->
    <LogTerminal />
    <ConfirmDialog />

    <!-- 全局通知 -->
    <AppNotification />
  </v-app>
</template>

<style scoped>
/* 导航项 — 图标与文字收紧间距 + 整体居中 */
:deep(.v-navigation-drawer .v-list-item) {
  display: flex;
  justify-content: center;
}

/* 缩小图标与文字之间的默认 spacer（Vuetify 默认 32px） */
:deep(.v-navigation-drawer .v-list-item__spacer) {
  width: 8px !important;
  min-width: 8px !important;
}

.app-logo {
  width: 28px;
  height: 28px;
  /* <img> 引入的 SVG 无法继承 currentColor，用 filter 着色 */
  filter: brightness(0) saturate(100%) invert(47%) sepia(98%) saturate(1925%) hue-rotate(234deg) brightness(96%) contrast(96%);
}
</style>
