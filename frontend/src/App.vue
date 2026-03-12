<script setup lang="ts">
import { onMounted } from 'vue'
import { 
  NConfigProvider, 
  NDialogProvider, 
  NMessageProvider, 
  NNotificationProvider,
  NGlobalStyle,
  darkTheme
} from 'naive-ui'

import MainLayout from './layouts/MainLayout.vue'

import LoginView from './views/LoginView.vue'

import { themeOverrides } from './store/themeStore'

import { isLoggedIn, uiAuthEnabled } from './store/navigationStore'



// --- 全局 Token 同步 ---

const syncToken = async () => {

  try {

    const API_BASE = (import.meta.env.VITE_API_BASE as string) || (window.location.origin)

    

    // 检查 Auth 状态

    const authStatusRes = await fetch(`${API_BASE}/api/auth/status`)

    if (authStatusRes.ok) {

        const authStatus = await authStatusRes.json()

        uiAuthEnabled.value = authStatus.ui_auth_enabled

        localStorage.setItem('apm_ui_auth_enabled', String(authStatus.ui_auth_enabled))

    }



    // 兼容性同步：如果没开启新版 Auth，或者已经有了 external_token，尝试同步

    if (!uiAuthEnabled.value) {

        const res = await fetch(`${API_BASE}/api/config`)

        if (res.ok) {

          const data = await res.json()

          if (data.external_token) {

            localStorage.setItem('apm_external_token', data.external_token)

          }

        }

    }

  } catch (e) {

    console.error('Failed to sync token:', e)

  }

}



onMounted(() => {

  syncToken()

})

</script>



<template>

  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">

    <n-global-style />

    <n-notification-provider>

      <n-dialog-provider>

        <n-message-provider>

          <LoginView v-if="uiAuthEnabled && !isLoggedIn" />

          <MainLayout v-else />

        </n-message-provider>

      </n-dialog-provider>

    </n-notification-provider>

  </n-config-provider>

</template>

<style>
/* 全局动画变量 */
:root {
  /* 动画时长 */
  --duration-instant: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 350ms;
  --duration-slower: 500ms;

  /* 动画缓动函数 */
  --ease-linear: linear;
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

/* 全局滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-medium);
  border-radius: var(--radius-full);
  transition: background var(--duration-fast);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--border-heavy);
}

/* 文本选中样式 */
::selection {
  background: var(--primary-medium, rgba(187, 134, 252, 0.4));
  color: var(--text-primary);
}

/* 焦点样式 */
:focus-visible {
  outline: 2px solid var(--n-primary-color);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* 脉冲动画 */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* 闪烁动画 */
@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

/* 弹跳动画 */
@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

/* 旋转动画 */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 缩放脉冲 */
@keyframes scale-pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

/* 骨架屏闪烁效果 */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-surface) 25%,
    var(--bg-surface-hover) 50%,
    var(--bg-surface) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* 悬停上浮效果 */
.hover-lift {
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

/* 按钮点击效果 */
.btn-press:active {
  transform: scale(0.96);
}

/* 图标悬停旋转 */
.icon-spin-hover {
  transition: transform var(--duration-normal) var(--ease-bounce);
}

.icon-spin-hover:hover {
  transform: rotate(15deg);
}

/* 渐变边框动画 */
.gradient-border {
  position: relative;
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
}

.gradient-border::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  background: linear-gradient(
    45deg,
    var(--n-primary-color),
    var(--color-info),
    var(--n-primary-color)
  );
  background-size: 200% 200%;
  animation: gradient-rotate 3s linear infinite;
  z-index: -1;
  opacity: 0;
  transition: opacity var(--duration-normal);
}

.gradient-border:hover::before {
  opacity: 1;
}

@keyframes gradient-rotate {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

/* 发光效果 */
.glow {
  transition: box-shadow var(--duration-normal);
}

.glow:hover {
  box-shadow: 0 0 20px var(--primary-medium, rgba(187, 134, 252, 0.5));
}

/* 平滑滚动 */
html {
  scroll-behavior: smooth;
}

/* 减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>
