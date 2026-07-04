<script setup lang="ts">
import { ref, computed, h, Component, watch, onMounted, onUnmounted } from 'vue'
import { 
  NLayout, 
  NLayoutSider, 
  NLayoutContent, 
  NMenu, 
  NScrollbar,
  NButton,
  NDropdown,
  NIcon,
  NSpace,
  NDrawer,
  NDrawerContent,
  NNotificationProvider,
  useNotification
} from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import {
  MovieOutlined as MovieIcon,
  FolderOutlined as FileIcon,
  DriveFileMoveOutlined as OrganizeIcon,
  RssFeedOutlined as RssIcon,
  LinkOutlined as LinkIcon,
  HistoryOutlined as LogIcon,
  SettingsOutlined as SettingIcon,
  MenuBookOutlined as GuideIcon,
  ApiOutlined as ApiIcon,
  PaletteOutlined as ThemeIcon,
  TableChartOutlined as DbIcon,
  SearchOutlined as SearchIcon,
  CalendarMonthOutlined as CalendarIcon,
  AssignmentOutlined as TaskIcon,
  TerminalOutlined as ConsoleIcon,
  MenuOutlined as HamburgerIcon,
  PersonOutlined as ProfileIcon,
  ExitToAppOutlined as LogoutIcon
} from '@vicons/material'

// Views - 不再需要导入，使用路由
import { useRouter, useRoute } from 'vue-router'

import LogConsoleModal from '../components/LogConsoleModal.vue'
import ReloadPrompt from '../components/ReloadPrompt.vue'
import { systemApi } from '../api/system'
import { APP_VERSION } from '../version'
import { getButtonStyle } from '../composables/useButtonStyles'

import { 
  isLogConsoleOpen, 
  isLoggedIn, logout, username
} from '../store/navigationStore'
import { currentThemeMode, isDarkMode, logoColor, toggleThemeMode } from '../store/themeStore'
import { ThemeMode } from '../themes'
import { useIsMobile } from '../composables/useIsMobile'

const notification = useNotification()
const router = useRouter()
const route = useRoute()

const checkVersionUpdate = async () => {
  try {
    const response = await systemApi.checkVersion()
    const data = response.data
    
    if (data.latest_version && data.latest_version !== APP_VERSION) {
      notification.info({
        title: '发现新版本',
        content: `当前版本: ${APP_VERSION}，最新版本: ${data.latest_version}`,
        duration: 0,
        action: () => [
          h(NButton, {
            size: 'small',
            onClick: () => {
              window.open('https://hub.docker.com/r/pipi20xx/anime-manager/tags', '_blank')
            }
          }, { default: () => '查看更新' })
        ]
      })
    }
  } catch (error) {
    console.error('版本检查失败:', error)
  }
}

onMounted(() => {
  checkVersionUpdate()
})

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const userOptions = [
  {
    label: '退出登录',
    key: 'logout',
    icon: renderIcon(LogoutIcon)
  }
]

const handleUserSelect = (key: string) => {
  if (key === 'logout') {
    logout()
  }
}

// 动态显示用户名：处理免密模式下的空名字问题
const displayUsername = computed(() => {
  return username.value || '管理员'
})

import { useBackClose } from '../composables/useBackClose'

// ... existing code ...

const { isMobile } = useIsMobile()

// --- History Management (Android Back Button Support) ---
// ... (keep existing history logic) ...
// ----------------------------------------------------

// Apply Back Button support to Global Modals
useBackClose(isLogConsoleOpen)

const showMobileMenu = ref(false)

const collapsed = ref(localStorage.getItem('apm_sidebar_collapsed') === 'true')
watch(collapsed, (val) => localStorage.setItem('apm_sidebar_collapsed', String(val)))

const showLogConsole = isLogConsoleOpen

const menuOptions: MenuOption[] = [
  { label: 'Jackett 搜索', key: 'JackettSearch', icon: renderIcon(SearchIcon) },
  { label: '追剧日历', key: 'Calendar', icon: renderIcon(CalendarIcon) },
  { label: '文件浏览', key: 'FileBrowser', icon: renderIcon(FileIcon) },
  { label: '整理重命名', key: 'Organizer', icon: renderIcon(OrganizeIcon) },
  { label: '整理历史', key: 'OrganizeHistory', icon: renderIcon(LogIcon) },
  { label: '订阅与下载', key: 'Subscription', icon: renderIcon(RssIcon) },
  { label: '虚拟库 (STRM)', key: 'StrmGenerator', icon: renderIcon(LinkIcon) },
  { label: '任务中心', key: 'TaskHistory', icon: renderIcon(TaskIcon) },
  { label: '外部控制 (API)', key: 'ExternalControl', icon: renderIcon(ApiIcon) },
  { label: '系统数据中心', key: 'Database', icon: renderIcon(DbIcon) },
  { label: '外观设置', key: 'Appearance', icon: renderIcon(ThemeIcon) },
  { label: '规则说明', key: 'UsageGuide', icon: renderIcon(GuideIcon) },
]

const currentMenuKey = computed(() => route.name as string)

const handleMenuSelect = (key: string) => {
  router.push({ name: key })
}

// Mobile Bottom Nav Helpers
const handleMobileNav = (key: string) => {
  if (key === 'MORE') {
    showMobileMenu.value = true
  } else {
    router.push({ name: key })
  }
}

const isNavActive = (key: string) => route.name === key
</script>

<template>
  <!-- 全局背景图片层 -->
  <div class="app-global-bg-layer" />
  <n-layout :has-sider="!isMobile" position="absolute">
    <!-- Desktop Sidebar -->
    <n-layout-sider
      v-if="!isMobile"
      bordered
      collapse-mode="width"
      :collapsed-width="56"
      :width="170"
      show-trigger="arrow-circle"
      content-style="padding: var(--space-2) 0; display: flex; flex-direction: column; height: 100%;"
      v-model:collapsed="collapsed"
      class="main-sider"
    >
      <div class="logo-container">
        <n-space align="center" :size="10" :wrap="false">
          <div @click="router.push({ name: 'Explore' })" style="cursor: pointer; display: flex; align-items: center; gap: var(--space-2);">
            <img src="/favicon.svg" alt="logo" style="width: 24px; height: 24px;" />
            <div v-if="!collapsed" class="logo-text">
              <span class="title" :style="{ color: logoColor }">番剧管家</span>
              <div class="version">v{{ APP_VERSION }}</div>
            </div>
          </div>
        </n-space>
      </div>
      
      <n-scrollbar style="flex-grow: 1;">
        <n-menu
          :value="currentMenuKey"
          :collapsed-width="56"
          :collapsed-icon-size="18"
          :options="menuOptions"
          :indent="14"
          @update:value="handleMenuSelect"
        />
      </n-scrollbar>

      <div class="sidebar-footer">
        <n-space vertical align="stretch" :size="[4, 8]">
          <!-- 用户状态与退出 (集成下拉菜单) -->
          <div class="user-status-container">
            <n-dropdown 
              trigger="click" 
              :options="userOptions" 
              @select="handleUserSelect"
            >
              <div class="user-status-trigger" :class="{ 'is-collapsed': collapsed }">
                <n-icon size="20" color="var(--n-primary-color)"><ProfileIcon /></n-icon>
                <div v-if="!collapsed" class="username-text">{{ displayUsername }}</div>
              </div>
            </n-dropdown>
          </div>

          <n-space :vertical="collapsed" justify="space-around" align="center" :size="[4, 8]">
            <n-button 
              v-bind="getButtonStyle('iconPrimary')" 
              size="small" 
              type="primary"
              @click="toggleThemeMode"
              :title="isDarkMode ? '切换白天模式' : '切换黑夜模式'"
            >
              <template #icon>
                <n-icon>
                  <svg v-if="isDarkMode" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5s5-2.24 5-5s-2.24-5-5-5M2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1m18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1M11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1m0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1M5.99 4.58a.996.996 0 0 0-1.41 0a.996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41zm12.37 12.37a.996.996 0 0 0-1.41 0a.996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0c.39-.39.39-1.03 0-1.41zm1.06-10.96a.996.996 0 0 0 0-1.41a.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0zM7.05 18.36a.996.996 0 0 0 0-1.41a.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0z"/>
                  </svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M9 2c-1.05 0-2.05.16-3 .46c1.06.39 1.86 1.27 2.15 2.38A6.01 6.01 0 0 1 9 4c3.31 0 6 2.69 6 6s-2.69 6-6 6s-6-2.69-6-6c0-.6.09-1.18.25-1.73c-.87.33-1.54.99-1.93 1.85C1.16 11.95 1 12.95 1 14c0 4.42 3.58 8 8 8s8-3.58 8-8s-3.58-8-8-8"/>
                  </svg>
                </n-icon>
              </template>
            </n-button>

            <n-button 
              v-bind="getButtonStyle('iconPrimary')"
              size="small"
              :type="route.name === 'Home' ? 'primary' : 'default'"
              @click="router.push({ name: 'Home' })"
              title="识别控制台"
            >
              <template #icon><n-icon><MovieIcon /></n-icon></template>
            </n-button>

            <n-button 
              v-bind="getButtonStyle('iconPrimary')"
              size="small"
              :type="route.name === 'Settings' ? 'primary' : 'default'"
              @click="router.push({ name: 'Settings' })"
              title="系统设置"
            >
              <template #icon><n-icon><SettingIcon /></n-icon></template>
            </n-button>

            <n-button 
              v-bind="getButtonStyle('iconPrimary')"
              size="small"
              @click="showLogConsole = true"
              title="实时日志"
            >
              <template #icon><n-icon><ConsoleIcon /></n-icon></template>
            </n-button>
          </n-space>
        </n-space>
      </div>
    </n-layout-sider>

    <n-layout-content
      :content-style="`padding: var(--space-4); padding-bottom: ${isMobile ? '80px' : 'var(--space-4)'}; min-height: 100vh; display: flex; flex-direction: column;`"
    >
      <!-- Mobile Top Bar (Optional, for Logo/Search if needed, or keep clean) -->
      <div v-if="isMobile" class="mobile-header">
        <n-space align="center" justify="space-between" style="width: 100%">
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            <img src="/favicon.svg" alt="logo" style="width: 22px; height: 22px;" />
            <div style="display: flex; flex-direction: column;">
              <span class="title" :style="{ color: logoColor, fontWeight: '800', lineHeight: '1.2' }">番剧管家</span>
              <span style="font-size: var(--text-2xs); opacity: var(--opacity-60); margin-top: -2px;">v{{ APP_VERSION }}</span>
            </div>
          </div>
          <n-button v-bind="getButtonStyle('icon')" size="small" @click="router.push({ name: 'JackettSearch' })">
            <template #icon><n-icon size="20"><SearchIcon /></n-icon></template>
          </n-button>
        </n-space>
      </div>

      <div class="view-wrapper">
        <router-view v-slot="{ Component, route }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </div>
    </n-layout-content>

    <!-- Mobile Bottom Navigation -->
    <div v-if="isMobile" class="mobile-bottom-nav">
      <div class="nav-item" :class="{ active: isNavActive('Explore') }" @click="handleMobileNav('Explore')">
        <n-icon size="24"><MovieIcon /></n-icon>
        <span class="label">首页</span>
      </div>
      <div class="nav-item" :class="{ active: isNavActive('Calendar') }" @click="handleMobileNav('Calendar')">
        <n-icon size="24"><CalendarIcon /></n-icon>
        <span class="label">日历</span>
      </div>
      <div class="nav-item" :class="{ active: isNavActive('Subscription') }" @click="handleMobileNav('Subscription')">
        <n-icon size="24"><RssIcon /></n-icon>
        <span class="label">订阅</span>
      </div>
      <div class="nav-item" :class="{ active: showMobileMenu }" @click="handleMobileNav('MORE')">
        <n-icon size="24"><HamburgerIcon /></n-icon>
        <span class="label">更多</span>
      </div>
    </div>

    <!-- Mobile Drawer for Menu -->
    <n-drawer v-model:show="showMobileMenu" placement="right" :width="260">
      <n-drawer-content title="功能菜单" :native-scrollbar="false">
         <n-menu
          :value="currentMenuKey"
          :options="menuOptions"
          :indent="18"
          @update:value="(key) => { handleMenuSelect(key); showMobileMenu = false; }"
        />
        <template #footer>
          <n-space justify="space-around" style="width: 100%; padding-bottom: var(--space-5);">
             <n-button 
                v-bind="getButtonStyle('iconPrimary')" 
                type="primary"
                @click="toggleThemeMode"
                :title="isDarkMode ? '切换白天模式' : '切换黑夜模式'"
              >
                <template #icon>
                  <n-icon>
                    <svg v-if="isDarkMode" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                      <path fill="currentColor" d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5s5-2.24 5-5s-2.24-5-5-5M2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1m18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1M11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1m0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1M5.99 4.58a.996.996 0 0 0-1.41 0a.996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41zm12.37 12.37a.996.996 0 0 0-1.41 0a.996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0c.39-.39.39-1.03 0-1.41zm1.06-10.96a.996.996 0 0 0 0-1.41a.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0zM7.05 18.36a.996.996 0 0 0 0-1.41a.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0z"/>
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                      <path fill="currentColor" d="M9 2c-1.05 0-2.05.16-3 .46c1.06.39 1.86 1.27 2.15 2.38A6.01 6.01 0 0 1 9 4c3.31 0 6 2.69 6 6s-2.69 6-6 6s-6-2.69-6-6c0-.6.09-1.18.25-1.73c-.87.33-1.54.99-1.93 1.85C1.16 11.95 1 12.95 1 14c0 4.42 3.58 8 8 8s8-3.58 8-8s-3.58-8-8-8"/>
                    </svg>
                  </n-icon>
                </template>
              </n-button>

              <n-button 
                v-bind="getButtonStyle('iconPrimary')"
                :type="route.name === 'Home' ? 'primary' : 'default'"
                @click="router.push({ name: 'Home' }); showMobileMenu = false;"
              >
                <template #icon><n-icon><MovieIcon /></n-icon></template>
              </n-button>

              <n-button v-bind="getButtonStyle('iconPrimary')" @click="router.push({ name: 'Settings' }); showMobileMenu = false;">
                <template #icon><n-icon><SettingIcon /></n-icon></template>
              </n-button>
              <n-button v-bind="getButtonStyle('iconPrimary')" @click="{ showLogConsole = true; showMobileMenu = false; }">
                <template #icon><n-icon><ConsoleIcon /></n-icon></template>
              </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>

  </n-layout>
  <LogConsoleModal v-model:show="showLogConsole" />
  <ReloadPrompt />
</template>

<style scoped>
.main-sider {
  background-color: var(--sidebar-bg-color);
  border-right: 1px solid var(--border-light) !important;
}

:deep(.n-layout-sider-trigger) {
  background: var(--app-surface-card-mixed) !important;
  color: var(--text-secondary) !important;
  border-color: var(--app-border-light) !important;
}

:deep(.n-layout-sider-trigger:hover) {
  background: var(--bg-surface-hover) !important;
  color: var(--text-primary) !important;
}

:deep(.n-layout-toggle-button) {
  background: var(--app-surface-card-mixed) !important;
  color: var(--text-secondary) !important;
  border-color: var(--app-border-light) !important;
}

:deep(.n-layout-toggle-button:hover) {
  background: var(--bg-surface-hover) !important;
  color: var(--text-primary) !important;
}

/* 菜单项动画 */
:deep(.n-menu-item) {
  transition: all var(--transition-fast) !important;
}

:deep(.n-menu-item:hover) {
  transform: translateX(4px);
}

:deep(.n-menu-item.n-menu-item--selected) {
  animation: menuPulse 0.3s ease;
}

@keyframes menuPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); }
}

.logo-container {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  height: 50px;
  box-sizing: border-box;
}
.logo-text .title {
  font-size: var(--text-md);
  font-weight: 800;
  letter-spacing: var(--tracking-wide);
}
.sidebar-footer {
  padding: var(--space-2);
  border-top: 1px solid var(--border-light);
}
.user-status-container {
  padding: 0 var(--m-1);
  margin-bottom: var(--m-1);
}
.user-status-trigger {
  display: flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  cursor: pointer;
  border-radius: var(--radius-lg);
  transition: all var(--transition-normal);
  gap: var(--space-2);
  border: 1px solid var(--border-light);
  background-color: var(--bg-surface);
}
.user-status-trigger:hover {
  background-color: var(--bg-surface-hover);
  border-color: var(--n-primary-color);
}
.user-status-trigger.is-collapsed {
  padding: var(--space-1) 0; 
  justify-content: center; 
}
.username-text {
  font-size: var(--text-sm);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
  color: var(--text-tertiary);
}

.sidebar-footer :deep(.n-button .n-icon) {
  color: var(--text-secondary) !important;
}

.sidebar-footer :deep(.n-button:hover .n-icon) {
  color: var(--text-primary) !important;
}

.view-wrapper {
  flex: 1;
  width: 100%;
  max-width: 100%;
  padding: 0 var(--m-1);
}

/* Mobile Specific Styles */
.mobile-header {
  padding: 0 0 var(--space-3) 0;
  margin-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}

.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background-color: var(--sidebar-bg-color); 
  /* Use sidebar color for bottom nav background */
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border-medium);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 2000;
  padding-bottom: env(safe-area-inset-bottom);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  color: var(--text-muted);
  transition: all var(--transition-normal);
  cursor: pointer;
  position: relative;
}

.nav-item::before {
  content: '';
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%) scale(0);
  width: 40px;
  height: 40px;
  background: var(--primary-subtle);
  border-radius: var(--radius-lg);
  transition: transform var(--transition-normal) var(--ease-spring);
  z-index: -1;
}

.nav-item.active {
  color: var(--n-primary-color);
}

.nav-item.active::before {
  transform: translateX(-50%) scale(1);
}

.nav-item:active {
  transform: scale(0.92);
}

.nav-item .label {
  font-size: var(--text-2xs);
  margin-top: 2px;
  transition: all var(--transition-fast);
}

.nav-item.active .label {
  font-weight: 600;
  transform: scale(1.05);
}

/* 页面过渡动画 - 淡入上浮 */
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

/* 页面内容进入动画 */
@keyframes pageEnter {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.view-wrapper > * {
  animation: pageEnter 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
