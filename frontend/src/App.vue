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
