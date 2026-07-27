<script setup lang="ts">
defineOptions({ name: 'HomeView' })

const appVersion = __APP_VERSION__ as string
</script>

<template>
  <v-container fluid class="pa-6">
    <div class="text-center pa-8">
      <v-icon size="80" color="primary">mdi-animation-play</v-icon>
      <h2 class="text-h5 font-weight-bold mt-4">欢迎使用番剧管家</h2>
      <p class="text-body-2 text-medium-emphasis mt-2">Anime Manager v{{ appVersion }}</p>
      <p class="text-body-2 text-medium-emphasis mt-1">前端重写进行中...</p>
    </div>
  </v-container>
</template>
