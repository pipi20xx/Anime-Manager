<script setup lang="ts">
import { useRegisterSW } from 'virtual:pwa-register/vue'
import { NButton, NNotificationProvider, useNotification } from 'naive-ui'
import { watch } from 'vue'

const {
  offlineReady,
  needRefresh,
  updateServiceWorker,
} = useRegisterSW()

const notification = useNotification()

const close = () => {
  offlineReady.value = false
  needRefresh.value = false
}

watch(needRefresh, (val) => {
  if (val) {
    notification.info({
      title: '发现新版本',
      content: '应用内容已更新，是否立即刷新以加载新功能？',
      action: () => [
        NButton,
        {
          secondary: true,
          size: 'small',
          onClick: () => updateServiceWorker(true)
        },
        { default: () => '立即更新' }
      ],
      onClose: close
    })
  }
})

watch(offlineReady, (val) => {
  if (val) {
    notification.success({
      title: '离线就绪',
      content: '应用已缓存，现在可以在无网络状态下快速启动。',
      duration: 3000
    })
  }
})
</script>

<template>
  <div v-if="false"></div>
</template>
