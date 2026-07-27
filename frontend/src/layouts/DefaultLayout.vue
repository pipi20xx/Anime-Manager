<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore, useSystemStore } from '@/stores'
import { useNotification } from '@/composables'
import { ConfirmDialog, LogTerminal } from '@/components/common'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const systemStore = useSystemStore()
const { notify, state: notifyState } = useNotification()

const appVersion = __APP_VERSION__ as string
const drawer = ref(true)
const rail = ref(false)
const isMobile = ref(false)

const navItems = [
  { title: '首页', icon: 'mdi-home-outline', to: '/' },
]

const currentTitle = computed(() => {
  const item = navItems.find(n => n.to === route.path)
  return item?.title ?? '番剧管家'
})

function handleLogout() {
  systemStore.logout()
  router.push('/login')
}

function checkMobile() {
  isMobile.value = window.innerWidth < 960
  if (isMobile.value) drawer.value = false
}

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
          <v-icon icon="mdi-animation-play" size="24" />
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

      <!-- 导航菜单 -->
      <v-list density="compact" nav class="px-3 py-2 flex-grow-0 overflow-y-auto">
        <v-list-item
          v-for="item in navItems"
          :key="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          :to="item.to"
          :value="item.to"
          rounded="xl"
          class="mb-1"
          :exact="item.to === '/'"
        />
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
    <v-app-bar elevation="0" density="comfortable" color="transparent">
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

          <!-- 主题切换 -->
          <v-btn
            variant="text"
            density="comfortable"
            size="small"
            :color="themeStore.isDarkMode ? 'warning' : 'info'"
            :icon="themeStore.isDarkMode ? 'mdi-white-balance-sunny' : 'mdi-weather-night'"
            @click="themeStore.toggleDarkMode()"
          />

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
      <router-view />
    </v-main>

    <!-- 全局组件 -->
    <LogTerminal />
    <ConfirmDialog />

    <!-- 全局通知 SnackBar -->
    <v-snackbar
      v-model="notifyState.show"
      :color="notifyState.color"
      :timeout="notifyState.timeout"
      location="top right"
    >
      <div v-if="notifyState.title" class="font-weight-bold mb-1">{{ notifyState.title }}</div>
      {{ notifyState.message }}
      <template #actions>
        <v-btn variant="text" icon="mdi-close" size="small" @click="notifyState.show = false" />
      </template>
    </v-snackbar>
  </v-app>
</template>
