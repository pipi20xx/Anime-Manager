<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionLogsDesktop from './desktop/RecognitionLogsDesktop.vue'
import RecognitionLogsMobile from './mobile/RecognitionLogsMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <RecognitionLogsMobile v-if="isMobile" />
  <RecognitionLogsDesktop v-else />
</template>