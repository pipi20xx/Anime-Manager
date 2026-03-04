<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionTmdbCardDesktop from './desktop/RecognitionTmdbCardDesktop.vue'
import RecognitionTmdbCardMobile from './mobile/RecognitionTmdbCardMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <RecognitionTmdbCardMobile v-if="isMobile" />
  <RecognitionTmdbCardDesktop v-else />
</template>
