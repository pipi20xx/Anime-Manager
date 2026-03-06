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

// Views
import ExploreView from '../views/ExploreView.vue'
import HomeView from '../views/HomeView.vue'
import CacheView from '../views/CacheView.vue'
import SettingsView from '../views/SettingsView.vue'
import UsageGuideView from '../views/UsageGuideView.vue'
import FileBrowserView from '../views/FileBrowserView.vue'
import OrganizerView from '../views/OrganizerView.vue'
import OrganizeHistoryView from '../views/OrganizeHistoryView.vue'
import SubscriptionView from '../views/SubscriptionView.vue'
import StrmGeneratorView from '../views/StrmGeneratorView.vue'
import CalendarView from '../views/CalendarView.vue'
import DatabaseView from '../views/DatabaseView.vue'
import TmdbFullDataView from '../views/TmdbFullDataView.vue'
import TaskHistoryView from '../views/TaskHistoryView.vue'
import ExternalControlView from '../views/ExternalControlView.vue'

import JackettSearchModal from '../components/JackettSearchModal.vue'
import LogConsoleModal from '../components/LogConsoleModal.vue'
import ReloadPrompt from '../components/ReloadPrompt.vue'
import { systemApi } from '../api/system'
import { APP_VERSION } from '../version'

import { 
  currentViewKey, isSearchOpen, isLogConsoleOpen, 
  isLoggedIn, logout, username, uiAuthEnabled 
} from '../store/navigationStore'
import { currentThemeType, logoColor } from '../store/themeStore'
import { themeOptions } from '../themes'
import { useIsMobile } from '../composables/useIsMobile'

const notification = useNotification()

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
  if (!uiAuthEnabled.value) return '管理员 (免密)'
  return username.value || '管理员'
})

import { useBackClose } from '../composables/useBackClose'

// ... existing code ...

const { isMobile } = useIsMobile()

// --- History Management (Android Back Button Support) ---
// ... (keep existing history logic) ...
// ----------------------------------------------------

// Apply Back Button support to Global Modals
useBackClose(isSearchOpen)
useBackClose(isLogConsoleOpen)

const showMobileMenu = ref(false)

const collapsed = ref(localStorage.getItem('apm_sidebar_collapsed') === 'true')
watch(collapsed, (val) => localStorage.setItem('apm_sidebar_collapsed', String(val)))

const showSearchModal = isSearchOpen
const showLogConsole = isLogConsoleOpen

const menuOptions: MenuOption[] = [
  { label: '追剧日历', key: 'CalendarView', icon: renderIcon(CalendarIcon) },
  { label: '文件浏览', key: 'FileBrowserView', icon: renderIcon(FileIcon) },
  { label: '整理重命名', key: 'OrganizerView', icon: renderIcon(OrganizeIcon) },
  { label: '整理历史', key: 'OrganizeHistoryView', icon: renderIcon(LogIcon) },
  { label: '订阅与下载', key: 'SubscriptionView', icon: renderIcon(RssIcon) },
  { label: '虚拟库 (STRM)', key: 'StrmGeneratorView', icon: renderIcon(LinkIcon) },
  { label: '任务中心', key: 'TaskHistoryView', icon: renderIcon(TaskIcon) },
  { label: '外部控制 (API)', key: 'ExternalControlView', icon: renderIcon(ApiIcon) },
  { label: '系统数据中心', key: 'DatabaseView', icon: renderIcon(DbIcon) },
  { label: '规则说明', key: 'UsageGuideView', icon: renderIcon(GuideIcon) },
]

const currentView = computed(() => {
  const views: Record<string, any> = {
    ExploreView, HomeView, CacheView, SettingsView, UsageGuideView,
    FileBrowserView, OrganizerView, OrganizeHistoryView, SubscriptionView, StrmGeneratorView, DatabaseView, 
    TmdbFullDataView, ExternalControlView, CalendarView, TaskHistoryView
  }
  return views[currentViewKey.value] || ExploreView
})

// Mobile Bottom Nav Helpers
const handleMobileNav = (key: string) => {
  if (key === 'MORE') {
    showMobileMenu.value = true
  } else {
    currentViewKey.value = key
  }
}

const isNavActive = (key: string) => currentViewKey.value === key
</script>

<template>
  <n-layout :has-sider="!isMobile" position="absolute">
    <!-- Desktop Sidebar -->
    <n-layout-sider
      v-if="!isMobile"
      bordered
      collapse-mode="width"
      :collapsed-width="56"
      :width="170"
      show-trigger="arrow-circle"
      content-style="padding: 8px 0; display: flex; flex-direction: column; height: 100%;"
      v-model:collapsed="collapsed"
      class="main-sider"
    >
      <div class="logo-container">
        <n-space align="center" :size="10" :wrap="false">
          <div @click="currentViewKey = 'ExploreView'" style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
            <n-icon size="24" :color="logoColor"><MovieIcon /></n-icon>
            <div v-if="!collapsed" class="logo-text">
              <span class="title" :style="{ color: logoColor }">番剧管家</span>
              <div class="version">v{{ APP_VERSION }}</div>
            </div>
          </div>
          <n-button 
            v-if="!collapsed"
            circle 
            quaternary 
            size="small" 
            @click="isSearchOpen = true"
            style="margin-left: 4px"
          >
            <template #icon><n-icon><SearchIcon /></n-icon></template>
          </n-button>
        </n-space>
      </div>
      
      <n-scrollbar style="flex-grow: 1;">
        <n-menu
          v-model:value="currentViewKey"
          :collapsed-width="56"
          :collapsed-icon-size="18"
          :options="menuOptions"
          :indent="14"
        />
      </n-scrollbar>

      <div class="sidebar-footer">
        <n-space vertical align="stretch" :size="[4, 8]">
          <!-- 用户状态与退出 (集成下拉菜单) -->
          <div class="user-status-container">
            <n-dropdown 
              trigger="click" 
              :options="uiAuthEnabled ? userOptions : []" 
              @select="handleUserSelect"
              :disabled="!uiAuthEnabled"
            >
              <div class="user-status-trigger" :class="{ 'is-collapsed': collapsed, 'is-disabled': !uiAuthEnabled }">
                <n-icon size="20" color="var(--n-primary-color)"><ProfileIcon /></n-icon>
                <div v-if="!collapsed" class="username-text">{{ displayUsername }}</div>
              </div>
            </n-dropdown>
          </div>

          <n-space :vertical="collapsed" justify="space-around" align="center" :size="[4, 8]">
            <n-dropdown 
              trigger="click" 
              :options="themeOptions" 
              @select="val => currentThemeType = val"
            >
              <n-button circle secondary size="small" :type="currentThemeType === 'modern' ? 'primary' : 'info'">
                <template #icon><n-icon><ThemeIcon /></n-icon></template>
              </n-button>
            </n-dropdown>

            <n-button 
              circle 
              secondary 
              size="small"
              :type="currentViewKey === 'HomeView' ? 'primary' : 'default'"
              @click="currentViewKey = 'HomeView'"
              title="识别控制台"
            >
              <template #icon><n-icon><MovieIcon /></n-icon></template>
            </n-button>

            <n-button 
              circle 
              secondary 
              size="small"
              :type="currentViewKey === 'SettingsView' ? 'primary' : 'default'"
              @click="currentViewKey = 'SettingsView'"
              title="系统设置"
            >
              <template #icon><n-icon><SettingIcon /></n-icon></template>
            </n-button>

            <n-button 
              circle 
              secondary 
              size="small"
              type="info" 
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
      :content-style="`padding: 16px; padding-bottom: ${isMobile ? '80px' : '16px'}; min-height: 100vh; display: flex; flex-direction: column; background-color: var(--app-bg-color);`"
    >
      <!-- Mobile Top Bar (Optional, for Logo/Search if needed, or keep clean) -->
      <div v-if="isMobile" class="mobile-header">
        <n-space align="center" justify="space-between" style="width: 100%">
          <div style="display: flex; align-items: center; gap: 8px;">
            <n-icon size="22" :color="logoColor"><MovieIcon /></n-icon>
            <div style="display: flex; flex-direction: column;">
              <span class="title" :style="{ color: logoColor, fontWeight: '800', lineHeight: '1.2' }">番剧管家</span>
              <span style="font-size: 10px; opacity: 0.6; margin-top: -2px;">v{{ APP_VERSION }}</span>
            </div>
          </div>
          <n-button circle quaternary size="small" @click="isSearchOpen = true">
            <template #icon><n-icon size="20"><SearchIcon /></n-icon></template>
          </n-button>
        </n-space>
      </div>

      <div class="view-wrapper">
        <transition name="fade" mode="out-in">
          <component :is="currentView" />
        </transition>
      </div>
    </n-layout-content>

    <!-- Mobile Bottom Navigation -->
    <div v-if="isMobile" class="mobile-bottom-nav">
      <div class="nav-item" :class="{ active: isNavActive('ExploreView') }" @click="handleMobileNav('ExploreView')">
        <n-icon size="24"><MovieIcon /></n-icon>
        <span class="label">首页</span>
      </div>
      <div class="nav-item" :class="{ active: isNavActive('CalendarView') }" @click="handleMobileNav('CalendarView')">
        <n-icon size="24"><CalendarIcon /></n-icon>
        <span class="label">日历</span>
      </div>
      <div class="nav-item" :class="{ active: isNavActive('SubscriptionView') }" @click="handleMobileNav('SubscriptionView')">
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
          v-model:value="currentViewKey"
          :options="menuOptions"
          :indent="18"
          @update:value="showMobileMenu = false"
        />
        <template #footer>
          <n-space justify="space-around" style="width: 100%; padding-bottom: 20px;">
             <n-dropdown 
                trigger="click" 
                :options="themeOptions" 
                @select="val => currentThemeType = val"
              >
                <n-button circle secondary :type="currentThemeType === 'modern' ? 'primary' : 'info'">
                  <template #icon><n-icon><ThemeIcon /></n-icon></template>
                </n-button>
              </n-dropdown>

              <n-button 
                circle 
                secondary 
                :type="currentViewKey === 'HomeView' ? 'primary' : 'default'"
                @click="{ currentViewKey = 'HomeView'; showMobileMenu = false; }"
              >
                <template #icon><n-icon><MovieIcon /></n-icon></template>
              </n-button>

              <n-button circle secondary @click="{ currentViewKey = 'SettingsView'; showMobileMenu = false; }">
                <template #icon><n-icon><SettingIcon /></n-icon></template>
              </n-button>
              <n-button circle secondary type="info" @click="{ showLogConsole = true; showMobileMenu = false; }">
                <template #icon><n-icon><ConsoleIcon /></n-icon></template>
              </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>

  </n-layout>
  <JackettSearchModal v-model:show="showSearchModal" />
  <LogConsoleModal v-model:show="showLogConsole" />
  <ReloadPrompt />
</template>

<style scoped>
.main-sider {
  background-color: var(--sidebar-bg-color);
  border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}
.logo-container {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 12px 16px;
  height: 50px;
  box-sizing: border-box;
}
.logo-text .title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.5px;
}
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.user-status-container {
  padding: 0 4px;
  margin-bottom: 4px;
}
.user-status-trigger {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.3s ease;
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background-color: rgba(255, 255, 255, 0.02);
}
.user-status-trigger:hover {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: var(--n-primary-color);
}
.user-status-trigger.is-disabled {
  cursor: default;
}
.user-status-trigger.is-disabled:hover {
  background-color: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.05);
}
.user-status-trigger.is-collapsed {
  padding: 6px 0; 
  justify-content: center; 
}
.username-text {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
  color: #ccc;
}
.view-wrapper {
  flex: 1;
  width: 100%;
  max-width: 100%;
  padding: 0 4px;
}

/* Mobile Specific Styles */
.mobile-header {
  padding: 0 0 12px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
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
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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
  color: rgba(255, 255, 255, 0.5);
  transition: all 0.3s ease;
  cursor: pointer;
}

.nav-item.active {
  color: var(--n-color-target); /* Will be replaced by dynamic color if needed, or use primary */
  color: #63e2b7; /* Fallback/Default Primary */
}

/* Dynamic color binding via style is tricky in scoped css without v-bind, 
   but we can use the variable usually provided by naive-ui or just hardcode/use theme var */
.nav-item.active {
  color: v-bind('logoColor');
}

.nav-item .label {
  font-size: 10px;
  margin-top: 2px;
}
</style>
