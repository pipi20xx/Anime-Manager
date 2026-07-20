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
  FilmIcon as MovieIcon,
  FolderIcon as FileIcon,
  FolderArrowDownIcon as OrganizeIcon,
  RssIcon as RssIcon,
  LinkIcon as LinkIcon,
  ClockIcon as LogIcon,
  Cog6ToothIcon as SettingIcon,
  BookOpenIcon as GuideIcon,
  GlobeAltIcon as ApiIcon,
  PaintBrushIcon as ThemeIcon,
  CircleStackIcon as DbIcon,
  MagnifyingGlassIcon as SearchIcon,
  CalendarDaysIcon as CalendarIcon,
  ClipboardDocumentListIcon as TaskIcon,
  DocumentDuplicateIcon as HashIcon,
  DocumentTextIcon as ConsoleIcon,
  Bars3Icon as HamburgerIcon,
  UserIcon as ProfileIcon,
  ArrowLeftOnRectangleIcon as LogoutIcon,
  ArrowLeftIcon as ArrowBackIcon,
  SunIcon as SunIcon,
  MoonIcon as MoonIcon,
  BeakerIcon as DebugIcon
} from '@heroicons/vue/24/outline'

// Views - 不再需要导入，使用路由
import { useRouter, useRoute } from 'vue-router'

import LogConsoleModal from '../components/desktop/LogConsoleModalDesktop.vue'
import LogoIcon from '../components/LogoIcon.vue'
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
import { usePWA } from '../composables/usePWA'
import { currentPageRouteName, applyPageBackground, applyPageOverrides, appearanceConfig, previewPageKey } from '../store/appearanceStore'
import { getPageKeyByRouteName } from '../constants/appearanceKeys'

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

// PWA 三态导航: desktop / mobile-browser / pwa-app
const { isMobile, appMode } = usePWA()

/** 返回上一页 (PWA App 模式的返回按钮) */
function goBack() {
  if (window.history.length > 1) {
    window.history.back()
  } else {
    router.push({ name: 'Explore' })
  }
}

// --- History Management (Android Back Button Support) ---
// LogConsoleModal 内部的 AppGlassModal 已通过 useBackClose 自动管理 history，
// 无需在此重复调用。
// ----------------------------------------------------

const showMobileMenu = ref(false)

// ── 底部功能面板的 History 管理 (不使用 useBackClose, 避免与 router.push 冲突) ──
let panelNavKey: string | null = null
let isPanelPopStateClose = false

watch(showMobileMenu, (val) => {
  if (val) {
    // 打开时 push 一个 state, 使返回键能关闭面板
    window.history.pushState({ mobileMenu: true }, '')
  } else if (!panelNavKey && !isPanelPopStateClose) {
    // 通过遮罩层/关闭按钮关闭 → 消费 push 的 state
    window.history.back()
  }
  isPanelPopStateClose = false
})

const onPanelPopState = () => {
  if (showMobileMenu.value) {
    // 返回键关闭面板
    isPanelPopStateClose = true
    showMobileMenu.value = false
  } else if (panelNavKey) {
    // 点击功能项后的 popstate → 执行路由跳转
    const key = panelNavKey
    panelNavKey = null
    router.push({ name: key })
  }
}

onMounted(() => window.addEventListener('popstate', onPanelPopState))
onUnmounted(() => window.removeEventListener('popstate', onPanelPopState))

// 路由变化时更新当前路由名称，并重新应用页面级背景和组件覆盖
watch(() => route.name, (name) => {
  currentPageRouteName.value = (name as string) || null
  applyPageBackground(appearanceConfig.value)
  applyPageOverrides(appearanceConfig.value)
}, { immediate: true })

// 外观配置变化时也重新应用页面级背景和组件覆盖
watch(appearanceConfig, () => {
  applyPageBackground(appearanceConfig.value)
  applyPageOverrides(appearanceConfig.value)
}, { deep: true })

// 当前页面 key（用于设置 data-page-key 属性，驱动页面级组件覆盖）
// 同时设置在 document.documentElement 上，确保 teleport 到 body 的弹框也能继承页面级覆盖
const currentPageKey = computed(() => {
  // 优先使用预览 key（外观设置中选中的页面）
  if (previewPageKey.value) return previewPageKey.value
  const name = route.name as string
  return name ? getPageKeyByRouteName(name) : undefined
})
watch(currentPageKey, (key) => {
  const root = document.documentElement
  if (key) {
    root.setAttribute('data-page-key', key)
  } else {
    root.removeAttribute('data-page-key')
  }
}, { immediate: true })

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
  { label: '文件哈希记录', key: 'FileHashes', icon: renderIcon(HashIcon) },
  { label: '外部控制 (API)', key: 'ExternalControl', icon: renderIcon(ApiIcon) },
  { label: '系统数据中心', key: 'Database', icon: renderIcon(DbIcon) },
  { label: '外观设置', key: 'Appearance', icon: renderIcon(ThemeIcon) },
  { label: '规则说明', key: 'UsageGuide', icon: renderIcon(GuideIcon) },
]

const currentMenuKey = computed(() => route.name as string)

// 详情页不再使用 full-bleed，统一由 n-layout-content 提供 padding，
// 避免桌面端/移动端顶部间隙丢失的问题
const isFullBleedPage = computed(() => false)

const handleMenuSelect = (key: string) => {
  router.push({ name: key })
}

// 底部导航主菜单 (最多5个, 超出的放入"更多"面板)
const bottomNavItems = [
  { key: 'Explore', label: '首页', icon: MovieIcon },
  { key: 'Calendar', label: '日历', icon: CalendarIcon },
  { key: 'Subscription', label: '订阅', icon: RssIcon },
  { key: 'Home', label: '控制台', icon: DebugIcon },
]

// "更多"面板的网格功能列表 (包含所有功能, 使用原始图标组件)
const gridMenuItems = [
  { label: '首页', key: 'Explore', icon: MovieIcon },
  { label: '控制台', key: 'Home', icon: DebugIcon },
  { label: 'Jackett 搜索', key: 'JackettSearch', icon: SearchIcon },
  { label: '追剧日历', key: 'Calendar', icon: CalendarIcon },
  { label: '文件浏览', key: 'FileBrowser', icon: FileIcon },
  { label: '整理重命名', key: 'Organizer', icon: OrganizeIcon },
  { label: '整理历史', key: 'OrganizeHistory', icon: LogIcon },
  { label: '订阅与下载', key: 'Subscription', icon: RssIcon },
  { label: '虚拟库 (STRM)', key: 'StrmGenerator', icon: LinkIcon },
  { label: '任务中心', key: 'TaskHistory', icon: TaskIcon },
  { label: '文件哈希记录', key: 'FileHashes', icon: HashIcon },
  { label: '外部控制 (API)', key: 'ExternalControl', icon: ApiIcon },
  { label: '系统数据中心', key: 'Database', icon: DbIcon },
  { label: '外观设置', key: 'Appearance', icon: ThemeIcon },
  { label: '系统设置', key: 'Settings', icon: SettingIcon },
  { label: '规则说明', key: 'UsageGuide', icon: GuideIcon },
]

// Mobile Nav Helpers
const handleMobileNav = (key: string) => {
  if (key === 'MORE') {
    showMobileMenu.value = true
  } else {
    router.push({ name: key })
  }
}

const isNavActive = (key: string) => {
  if (key === 'Explore') return route.name === 'Explore' || route.name === 'ExploreRecommend' || route.name === 'ExploreDiscover' || route.name === 'ExploreSearch'
  return route.name === key
}

/** 从"更多"面板选择功能: 先关闭面板再跳转 (避免 history 冲突) */
const handlePanelSelect = (key: string) => {
  panelNavKey = key
  showMobileMenu.value = false
  // 消费打开面板时 push 的 history state, popstate 中执行 router.push
  window.history.back()
}

/** 面板底部快捷操作: 跳转路由 + 关闭面板 (同上机制) */
const handlePanelAction = (key: string) => {
  panelNavKey = key
  showMobileMenu.value = false
  window.history.back()
}

/** 面板底部非路由操作: 仅关闭面板 (watch 会自动消费 history state) */
const handlePanelClose = () => {
  showMobileMenu.value = false
  // watch 中 !panelNavKey && !isPanelPopStateClose → 自动 history.back()
}

/** 面板内打开弹窗等非路由操作: 关闭面板但不调用 history.back(),
 *  避免与弹窗自身的 useBackClose history 管理冲突。
 *  用 replaceState 将面板的 pushState 替换为干净状态,
 *  这样弹窗关闭后 history.back() 回到的是干净状态而非过期的 panel state。 */
const handlePanelModalAction = (callback: () => void) => {
  isPanelPopStateClose = true  // 阻止 watch 调用 history.back()
  showMobileMenu.value = false
  // 将面板的 pushState({ mobileMenu: true }) 替换为 null, 清除残留状态
  window.history.replaceState(null, '')
  callback()
}
</script>

<template>
  <!-- 全局背景图片层 -->
  <div class="app-global-bg-layer" />
  <!-- 页面级背景图片层（覆盖在全局背景之上，仅当页面有独立背景时显示） -->
  <div class="app-page-bg-layer" />
  <n-layout :has-sider="!isMobile" position="absolute">
    <!-- Desktop Sidebar -->
    <n-layout-sider
      v-if="!isMobile"
      bordered
      collapse-mode="width"
      :collapsed-width="56"
      :width="220"
      show-trigger="arrow-circle"
      content-style="padding: var(--space-2) var(--space-3); display: flex; flex-direction: column; height: 100%;"
      v-model:collapsed="collapsed"
      class="main-sider"
    >
      <div class="logo-container">
        <n-space align="center" :size="10" :wrap="false">
          <div @click="router.push({ name: 'Explore' })" style="cursor: pointer; display: flex; align-items: center; gap: var(--space-2);">
            <LogoIcon :size="24" :color="logoColor" />
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
          :collapsed-width="32"
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
                  <SunIcon v-if="isDarkMode" />
                  <MoonIcon v-else />
                </n-icon>
              </template>
            </n-button>

            <n-button 
              v-bind="getButtonStyle('iconPrimary')"
              size="small"
              :type="route.name === 'Home' ? 'primary' : 'default'"
              @click="router.push({ name: 'Home' })"
              title="识别调试台"
            >
              <template #icon><n-icon><DebugIcon /></n-icon></template>
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
      :native-scrollbar="isMobile"
      :content-style="`padding: var(--space-4); padding-bottom: ${isMobile ? '90px' : 'var(--space-4)'}; min-height: 100vh; display: flex; flex-direction: column;`"
    >
      <!-- Mobile Top Bar -->
      <div v-if="isMobile" class="mobile-header">
        <n-space align="center" justify="space-between" style="width: 100%">
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            <!-- PWA App 模式: 返回按钮 -->
            <n-button v-if="appMode" v-bind="getButtonStyle('icon')" size="small" @click="goBack" title="返回">
              <template #icon><n-icon size="24"><ArrowBackIcon /></n-icon></template>
            </n-button>
            <!-- 移动浏览器模式: 汉堡菜单 -->
            <n-button v-else v-bind="getButtonStyle('icon')" size="small" @click="showMobileMenu = true" title="菜单">
              <template #icon><n-icon size="24"><HamburgerIcon /></n-icon></template>
            </n-button>
            <LogoIcon :size="22" :color="logoColor" />
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

      <div class="view-wrapper" :class="{ 'view-wrapper--full-bleed': isFullBleedPage }" :data-page-key="currentPageKey || undefined">
        <router-view v-slot="{ Component, route }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </div>
    </n-layout-content>

    <!-- Mobile Floating Bottom Nav (胶囊浮动卡片) -->
    <Teleport v-if="isMobile" to="body">
      <Transition name="nav-slide-up">
        <div v-if="isMobile" class="mobile-nav-container">
          <div class="mobile-nav-card">
            <div class="nav-item" 
              v-for="item in bottomNavItems" 
              :key="item.key"
              :class="{ active: isNavActive(item.key) }" 
              @click="handleMobileNav(item.key)"
            >
              <n-icon size="26"><component :is="item.icon" /></n-icon>
              <span class="label">{{ item.label }}</span>
            </div>
            <!-- 更多按钮 -->
            <div class="nav-item" :class="{ active: showMobileMenu }" @click="handleMobileNav('MORE')">
              <n-icon size="26"><HamburgerIcon /></n-icon>
              <span class="label">更多</span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Mobile Full-Screen Panel (更多功能面板) -->
    <n-drawer v-model:show="showMobileMenu" placement="bottom" :height="'100dvh'" :style="{ '--n-drawer-body-padding': '0' }">
      <div class="full-panel">
        <!-- 顶部标题栏 -->
        <div class="full-panel-header">
          <div class="full-panel-title">
            <LogoIcon :size="22" :color="logoColor" />
            <span>全部功能</span>
          </div>
          <n-button v-bind="getButtonStyle('icon')" size="small" @click="handlePanelClose" class="full-panel-close">
            <template #icon><n-icon size="24"><ArrowBackIcon /></n-icon></template>
          </n-button>
        </div>

        <!-- 可滚动功能网格 -->
        <div class="full-panel-body">
          <div class="app-grid-panel">
            <div 
              v-for="item in gridMenuItems" 
              :key="item.key"
              class="app-grid-item"
              :class="{ active: currentMenuKey === item.key }"
              @click="handlePanelSelect(item.key)"
            >
              <div class="app-grid-icon">
                <n-icon size="28"><component :is="item.icon" /></n-icon>
              </div>
              <div class="app-grid-label">{{ item.label }}</div>
            </div>
          </div>
        </div>

        <!-- 底部快捷操作栏 -->
        <div class="full-panel-footer">
          <div class="panel-footer">
            <div class="panel-footer-item" @click="handlePanelClose(); toggleThemeMode();">
              <n-icon size="24" :color="isDarkMode ? 'var(--n-primary-color)' : 'var(--text-secondary)'">
                <SunIcon v-if="isDarkMode" />
                <MoonIcon v-else />
              </n-icon>
              <span>{{ isDarkMode ? '夜间' : '日间' }}</span>
            </div>
            <div class="panel-footer-item" @click="handlePanelAction('Home')">
              <n-icon size="24"><DebugIcon /></n-icon>
              <span>控制台</span>
            </div>
            <div class="panel-footer-item" @click="handlePanelAction('Settings')">
              <n-icon size="24"><SettingIcon /></n-icon>
              <span>设置</span>
            </div>
            <div class="panel-footer-item" @click="handlePanelModalAction(() => showLogConsole = true);">
              <n-icon size="24"><ConsoleIcon /></n-icon>
              <span>日志</span>
            </div>
            <div class="panel-footer-item" @click="handlePanelModalAction(() => logout());">
              <n-icon size="24" color="var(--n-error-color, #ff4d4f)"><LogoutIcon /></n-icon>
              <span>退出</span>
            </div>
          </div>
        </div>
      </div>
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
.view-wrapper--full-bleed {
  padding: 0;
}

/* Mobile Specific Styles */
.mobile-header {
  padding: 0 0 var(--space-3) 0;
  margin-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}

/* 胶囊浮动底部导航 */
.mobile-nav-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2000;
  padding: 0 12px max(8px, env(safe-area-inset-bottom)) 12px;
  pointer-events: none;
}

.mobile-nav-card {
  pointer-events: auto;
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 58px;
  background-color: color-mix(in srgb, var(--sidebar-bg-color) 85%, transparent);
  backdrop-filter: blur(24px) saturate(1.8);
  -webkit-backdrop-filter: blur(24px) saturate(1.8);
  border: 1px solid var(--border-light);
  border-radius: 28px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25), 0 1px 4px rgba(0, 0, 0, 0.15);
  overflow: hidden;
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
  top: 6px;
  left: 50%;
  transform: translateX(-50%) scale(0);
  width: 44px;
  height: 32px;
  background: var(--primary-subtle);
  border-radius: 16px;
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
  font-size: 10px;
  margin-top: 2px;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.nav-item.active .label {
  font-weight: 600;
  transform: scale(1.05);
}

/* 全屏功能面板 */
.full-panel {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  height: 100vh;
  background: var(--app-surface-card-mixed);
  overflow: hidden;
}

.full-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  padding-top: max(12px, env(safe-area-inset-top, 0px));
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
  background: color-mix(in srgb, var(--sidebar-bg-color) 90%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.full-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.full-panel-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  padding: 20px 16px;
}

.full-panel-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--sidebar-bg-color) 90%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* 底部弹出功能面板 */
.app-grid-panel {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding: 0;
}

.app-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px 4px;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-surface);
  border: 1px solid transparent;
}

.app-grid-item:active {
  transform: scale(0.94);
}

.app-grid-item.active {
  background: var(--primary-subtle);
  border-color: var(--n-primary-color);
}

.app-grid-item.active .app-grid-icon {
  color: var(--n-primary-color);
}

.app-grid-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: var(--text-secondary);
  transition: color var(--transition-normal);
}

.app-grid-item:hover .app-grid-icon {
  color: var(--n-primary-color);
}

.app-grid-label {
  font-size: 11px;
  text-align: center;
  color: var(--text-secondary);
  line-height: 1.3;
  word-break: break-all;
}

.app-grid-item.active .app-grid-label {
  color: var(--n-primary-color);
  font-weight: 600;
}

/* 面板底部快捷操作 */
.panel-footer {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 8px 0 max(8px, env(safe-area-inset-bottom)) 0;
}

.panel-footer-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  transition: all var(--transition-normal);
  color: var(--text-secondary);
}

.panel-footer-item:active {
  transform: scale(0.92);
  background: var(--bg-surface-hover);
}

.panel-footer-item span {
  font-size: 10px;
}

/* 导航栏滑入动画 */
.nav-slide-up-enter-active {
  transition: transform 0.35s var(--ease-spring), opacity 0.25s ease;
}
.nav-slide-up-leave-active {
  transition: transform 0.2s ease, opacity 0.15s ease;
}
.nav-slide-up-enter-from {
  transform: translateY(100%);
  opacity: 0;
}
.nav-slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
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
