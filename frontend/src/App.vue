<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { 
  NConfigProvider, 
  NDialogProvider, 
  NMessageProvider, 
  NNotificationProvider,
  NGlobalStyle,
  darkTheme,
  lightTheme
} from 'naive-ui'

import MainLayout from './layouts/MainLayout.vue'

import LoginView from './views/LoginView.vue'

import { themeOverrides, isDarkMode } from './store/themeStore'

import { isLoggedIn } from './store/navigationStore'

const currentNaiveTheme = computed(() => isDarkMode.value ? darkTheme : lightTheme)

onMounted(() => {
  localStorage.setItem('apm_ui_auth_enabled', 'true')
})
</script>

<template>
  <n-config-provider :theme="currentNaiveTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <n-notification-provider>
      <n-dialog-provider>
        <n-message-provider>
          <LoginView v-if="!isLoggedIn" />
          <MainLayout v-else />
        </n-message-provider>
      </n-dialog-provider>
    </n-notification-provider>
  </n-config-provider>
</template>

<style>
:root {
  --duration-instant: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 350ms;
  --duration-slower: 500ms;

  --ease-linear: linear;
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

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

::selection {
  background: var(--primary-medium, rgba(187, 134, 252, 0.4));
  color: var(--text-primary);
}

:focus-visible {
  outline: 2px solid var(--n-primary-color);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes scale-pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

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

.hover-lift {
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.btn-press:active {
  transform: scale(0.96);
}

.icon-spin-hover {
  transition: transform var(--duration-normal) var(--ease-bounce);
}

.icon-spin-hover:hover {
  transform: rotate(15deg);
}

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

.glow {
  transition: box-shadow var(--duration-normal);
}

.glow:hover {
  box-shadow: 0 0 20px var(--primary-medium, rgba(187, 134, 252, 0.5));
}

html {
  scroll-behavior: smooth;
}

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
