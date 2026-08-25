<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, defineAsyncComponent, nextTick, provide, isRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore, useSystemStore } from '@/stores'
import { ConfirmDialog, LogTerminal, AppNotification } from '@/components/common'
import {
  useGlassFixedShellBackplate,
  usePagePresentationMotion,
} from '@/glass'
import type { DynamicHeaderTabItem, DynamicHeaderTabButton } from '@/composables/useDynamicHeaderTab'

// 异步加载玻璃设置弹窗
const GlassSettingsDialog = defineAsyncComponent(() => import('@/glass/components/GlassSettingsDialog.vue'))
// 异步加载主题色设置弹窗
const PrimaryColorDialog = defineAsyncComponent(() => import('@/components/common/PrimaryColorDialog.vue'))
// 异步加载圆角设置弹窗
const BorderRadiusDialog = defineAsyncComponent(() => import('@/components/common/BorderRadiusDialog.vue'))
// 异步加载边框设置弹窗
const BorderDialog = defineAsyncComponent(() => import('@/components/common/BorderDialog.vue'))
// 异步加载阴影设置弹窗
const ShadowDialog = defineAsyncComponent(() => import('@/components/common/ShadowDialog.vue'))
// 异步加载 Fixed Shell Backplate 组件
const GlassFixedShellBackplate = defineAsyncComponent(() => import('@/glass/components/GlassFixedShellBackplate.vue'))


const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const systemStore = useSystemStore()
const appVersion = __APP_VERSION__ as string
const drawer = ref(true)
const rail = ref(false)
const isMobile = ref(false)
const showGlassSettings = ref(false)
const showPrimaryColorDialog = ref(false)
const showBorderRadiusDialog = ref(false)
const showBorderDialog = ref(false)
const showShadowDialog = ref(false)

// 玻璃 Fixed Shell Backplate —— 从 App 层注入的壁纸槽位
const fixedShellBackplate = useGlassFixedShellBackplate()
const isACG = computed(() => themeStore.glassTheme === 'acg')
const isOverlayNav = computed(() => isMobile.value)
const isOverlayNavActive = computed(() => isMobile.value && drawer.value)

// 页面呈现动画
const pagePresentationMotion = usePagePresentationMotion()
const layoutMainRef = ref<any>(null)

function getLayoutMainEl(): HTMLElement | null {
  const refValue = layoutMainRef.value
  if (!refValue) return null
  // Vuetify 组件实例的 $el 指向根 DOM 元素
  if ('$el' in refValue) return (refValue.$el as HTMLElement) ?? null
  // 原生 HTMLElement ref
  if (refValue instanceof HTMLElement) return refValue
  return null
}

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

// 路由变化时，移动端自动关闭抽屉 + 触发页面呈现动画
watch(() => route.path, () => {
  if (isMobile.value) drawer.value = false
  // ACG 主题下触发页面呈现动画
  if (isACG.value) {
    nextTick(() => {
      pagePresentationMotion.start(route.fullPath, getLayoutMainEl())
    })
  }
})

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  pagePresentationMotion.cancel()
})

// ═══════════════════════════════════════════════════════════════
// 动态顶栏 Tab — 页面通过 useDynamicHeaderTab 注册 Tab 到顶栏内部
// 参照 MoviePilot 的做法，Tab 渲染在 <header> 内部，
// 与顶栏共享玻璃材质和水纹效果。
// ═══════════════════════════════════════════════════════════════

interface DynamicHeaderTab {
  items: DynamicHeaderTabItem[]
  modelValue: string
  appendButtons?: DynamicHeaderTabButton[]
  routePath?: string
  onUpdateModelValue?: (value: string) => void
}

const dynamicHeaderTab = ref<DynamicHeaderTab | null>(null)

function registerDynamicHeaderTab(tab: DynamicHeaderTab) {
  tab.routePath = route.path
  dynamicHeaderTab.value = { ...tab }
}

function unregisterDynamicHeaderTab(routePath?: string) {
  if (routePath && dynamicHeaderTab.value?.routePath !== routePath) return
  dynamicHeaderTab.value = null
}

provide('registerDynamicHeaderTab', registerDynamicHeaderTab)
provide('unregisterDynamicHeaderTab', unregisterDynamicHeaderTab)

// 路由变化时清除不属于当前路由的 Tab
watch(
  () => route.path,
  () => {
    nextTick(() => {
      if (dynamicHeaderTab.value && dynamicHeaderTab.value.routePath !== route.path) {
        dynamicHeaderTab.value = null
      }
    })
  },
  { immediate: false },
)

const visibleTabItems = computed(() => {
  if (!dynamicHeaderTab.value || dynamicHeaderTab.value.routePath !== route.path) return []
  return dynamicHeaderTab.value.items
})

const hasDynamicHeaderTab = computed(() => visibleTabItems.value.length > 0)

const visibleTabButtons = computed(() => {
  if (!hasDynamicHeaderTab.value) return []
  return (dynamicHeaderTab.value?.appendButtons ?? []).filter(button => {
    const show = isRef(button.show) ? button.show.value : button.show
    return show !== false
  })
})

function handleTabChange(newValue: string) {
  if (dynamicHeaderTab.value) {
    dynamicHeaderTab.value.modelValue = newValue
    dynamicHeaderTab.value.onUpdateModelValue?.(newValue)
  }
}

function resolveButtonColor(button: DynamicHeaderTabButton) {
  return isRef(button.color) ? button.color.value : (button.color ?? 'default')
}

function resolveButtonLoading(button: DynamicHeaderTabButton) {
  return isRef(button.loading) ? button.loading.value : (button.loading ?? false)
}
</script>

<template>
  <v-app>
    <div class="glass-grain" />

    <!-- 玻璃 Fixed Shell Backplate —— 在固定导航栏后面渲染壁纸背板 -->
    <GlassFixedShellBackplate
      v-if="isACG && fixedShellBackplate.layers.value.length > 0"
      :is-overlay-nav-active="isOverlayNavActive"
      :is-overlay-nav="isOverlayNav"
      :layers="fixedShellBackplate.layers.value"
      :transition-duration-ms="fixedShellBackplate.transitionDurationMs"
    />

    <!-- 布局根容器 —— MP 使用 layout-wrapper 包裹全部内容，玻璃渲染器依赖此 class 发现固定表面 -->
    <div
      class="layout-wrapper layout-nav-type-vertical layout-navbar-fixed layout-content-width-fluid"
      :class="{
        'layout-overlay-nav': isMobile,
        'layout-vertical-nav-collapsed': rail && !isMobile,
        'layout-fixed-shell-backplate-active': isACG && fixedShellBackplate.layers.value.length > 0,
      }"
    >
    <!-- 侧边导航 —— 添加 layout-vertical-nav class 供渲染器表面发现 -->
    <v-navigation-drawer
      v-model="drawer"
      :rail="rail && !isMobile"
      :permanent="!isMobile"
      :temporary="isMobile"
      width="256"
      rail-width="72"
      :class="['layout-vertical-nav', { 'overlay-nav': isMobile }]"
    >
      <!-- Logo 区域 -->
      <div class="logo-header" :class="{ 'logo-header--rail': rail && !isMobile }">
        <v-avatar class="liquid-avatar" rounded="xl" size="40">
          <div class="app-logo" role="img" aria-label="番剧管家" />
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

    <!-- 顶栏 —— 添加 layout-navbar class 供渲染器表面发现 -->
    <v-app-bar
      elevation="0"
      density="comfortable"
      class="layout-navbar navbar-blur"
      :extension-height="hasDynamicHeaderTab ? 44 : undefined"
    >
      <v-app-bar-nav-icon v-if="isMobile" @click="drawer = !drawer" />
      <v-app-bar-title class="font-weight-bold text-body-1">{{ currentTitle }}</v-app-bar-title>

      <!-- 动态顶栏 Tab —— 通过 extension 插槽渲染在顶栏第二行，与顶栏共享玻璃材质和水纹效果 -->
      <template #extension v-if="hasDynamicHeaderTab">
        <div class="layout-dynamic-header-tab">
          <div
            v-for="item in visibleTabItems"
            :key="item.tab"
            class="header-tab"
            :class="{ 'header-tab--active': dynamicHeaderTab!.modelValue === item.tab }"
            @click="handleTabChange(item.tab)"
          >
            <v-icon v-if="item.icon" start size="18">{{ item.icon }}</v-icon>
            <span>{{ item.title }}</span>
          </div>
          <!-- 附加按钮 -->
          <v-spacer v-if="visibleTabButtons.length" />
          <template v-for="button in visibleTabButtons" :key="button.icon">
            <v-btn
              v-if="button.text"
              :prepend-icon="button.icon"
              :variant="button.variant || 'text'"
              :color="resolveButtonColor(button)"
              :size="button.size || 'small'"
              :class="button.class"
              :loading="resolveButtonLoading(button)"
              density="comfortable"
              @click="button.action?.()"
            >
              {{ button.text }}
            </v-btn>
            <v-btn
              v-else
              :icon="button.icon"
              :variant="button.variant || 'text'"
              :color="resolveButtonColor(button)"
              :size="button.size || 'small'"
              :class="button.class"
              :loading="resolveButtonLoading(button)"
              density="comfortable"
              @click="button.action?.()"
            />
          </template>
        </div>
      </template>

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
                base-color="primary"
                @click="themeStore.setGlassTheme('liquid')"
              />
              <v-list-item
                prepend-icon="mdi-image-multiple"
                title="ACG 毛玻璃"
                subtitle="二次元壁纸 + 暗色毛玻璃"
                :active="themeStore.glassTheme === 'acg'"
                base-color="primary"
                @click="themeStore.setGlassTheme('acg')"
              />
              <v-list-item
                prepend-icon="mdi-contrast-box"
                title="经典实色"
                subtitle="纯白/纯黑 最简风格"
                :active="themeStore.glassTheme === 'classic'"
                base-color="primary"
                @click="themeStore.setGlassTheme('classic')"
              />
              <v-divider class="my-2 mx-2" />
              <v-list-item
                prepend-icon="mdi-palette"
                title="主题色"
                subtitle="选择应用主色调"
                base-color="primary"
                @click="showPrimaryColorDialog = true"
              />
              <v-list-item
                prepend-icon="mdi-border-radius"
                title="圆角"
                subtitle="无 / 小 / 默认 / 大 / 更大"
                base-color="primary"
                @click="showBorderRadiusDialog = true"
              />
<v-list-item
prepend-icon="mdi-border-all-variant"
title="边框"
subtitle="无 / 轻微 / 默认 / 明显 / 强边框"
base-color="primary"
@click="showBorderDialog = true"
/>
<v-list-item
prepend-icon="mdi-box-shadow"
title="阴影"
subtitle="无 / 轻微 / 默认 / 明显 / 夸张"
base-color="primary"
@click="showShadowDialog = true"
/>
              <v-list-item
                prepend-icon="mdi-tune-variant"
                title="玻璃材质设置"
                subtitle="材质 / 质量 / 动态效果 / 参数"
                :disabled="themeStore.glassTheme !== 'acg'"
                base-color="primary"
                @click="showGlassSettings = true"
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

    <!-- 主内容 —— 添加 layout-page-content / page-content-container 供渲染器发现滚动表面 -->
    <v-main ref="layoutMainRef" class="layout-content-wrapper">
      <main class="layout-page-content">
        <section class="page-content-container">
          <router-view v-slot="{ Component, route: r }">
            <keep-alive :include="[]">
              <component :is="Component" :key="r.fullPath" />
            </keep-alive>
          </router-view>
        </section>
      </main>
    </v-main>

    <!-- 全局组件 -->
    <LogTerminal />
    <ConfirmDialog />

    <!-- 全局通知 -->
    <AppNotification />

    <!-- 玻璃材质设置弹窗 -->
    <GlassSettingsDialog
      v-model="showGlassSettings"
      @close="showGlassSettings = false"
    />

    <!-- 主题色设置弹窗 -->
    <PrimaryColorDialog
      v-model="showPrimaryColorDialog"
      @close="showPrimaryColorDialog = false"
    />

<!-- 圆角设置弹窗 -->
<BorderRadiusDialog
v-model="showBorderRadiusDialog"
@close="showBorderRadiusDialog = false"
/>

<!-- 边框设置弹窗 -->
<BorderDialog
v-model="showBorderDialog"
@close="showBorderDialog = false"
/>

<!-- 阴影设置弹窗 -->
<ShadowDialog
v-model="showShadowDialog"
@close="showShadowDialog = false"
/>
    </div><!-- /layout-wrapper -->
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
  /* 使用 mask 让 SVG 跟随主题色，不再用 filter hack 硬编码紫色 */
  -webkit-mask: url('/favicon.svg') center / contain no-repeat;
  mask: url('/favicon.svg') center / contain no-repeat;
  background-color: rgb(var(--v-theme-primary));
}

/* ═══════════════════════════════════════════════════════════════
 * 动态顶栏 Tab — 参照 MoviePilot HeaderTab.vue
 * Tab 渲染在顶栏内部，与顶栏共享玻璃材质。
 * ═══════════════════════════════════════════════════════════════ */
.layout-dynamic-header-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  padding-inline: 16px;
  overflow-x: auto;
  scrollbar-width: none;
}
.layout-dynamic-header-tab::-webkit-scrollbar {
  display: none;
}

.header-tab {
  display: flex;
  align-items: center;
  border-radius: var(--am-tab-radius, 20px);
  background-color: transparent;
  color: rgba(var(--v-theme-on-surface), 0.7);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 6px 14px;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.header-tab:hover:not(.header-tab--active) {
  background-color: rgba(var(--v-theme-primary), 0.06);
  color: rgba(var(--v-theme-on-surface), 1);
}

.header-tab--active {
  color: rgb(var(--v-theme-primary));
}

@media (hover: none) and (pointer: coarse) {
  .header-tab:hover:not(.header-tab--active) {
    background-color: transparent;
  }
}
</style>
