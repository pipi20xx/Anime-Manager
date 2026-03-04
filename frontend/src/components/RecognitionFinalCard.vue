<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionFinalCardDesktop from './desktop/RecognitionFinalCardDesktop.vue'
import RecognitionFinalCardMobile from './mobile/RecognitionFinalCardMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <RecognitionFinalCardMobile v-if="isMobile" />
  <RecognitionFinalCardDesktop v-else />
</template>
