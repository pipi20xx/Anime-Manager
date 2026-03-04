<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionRawCardDesktop from './desktop/RecognitionRawCardDesktop.vue'
import RecognitionRawCardMobile from './mobile/RecognitionRawCardMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <RecognitionRawCardMobile v-if="isMobile" />
  <RecognitionRawCardDesktop v-else />
</template>
