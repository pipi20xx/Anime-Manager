<script setup lang="ts">
import { NEmpty } from 'naive-ui'
import { recognitionState } from '../store/recognitionStore'
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionResultDesktop from './desktop/RecognitionResultDesktop.vue'
import RecognitionResultMobile from './mobile/RecognitionResultMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <div class="recognition-result-container">
    <div v-if="!recognitionState.data" class="empty-state">
      <n-empty description="暂无识别结果，请在上方输入文件名开始解析" />
    </div>

    <div v-else class="content-body">
      <RecognitionResultMobile v-if="isMobile" />
      <RecognitionResultDesktop v-else />
    </div>
  </div>
</template>

<style scoped>
.recognition-result-container { width: 100%; margin-top: 12px; }
.empty-state { padding: 60px 0; }
</style>
