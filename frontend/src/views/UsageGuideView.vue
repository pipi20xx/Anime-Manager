<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import UsageGuideDesktop from './desktop/UsageGuideDesktop.vue'
import UsageGuideMobile from './mobile/UsageGuideMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <UsageGuideMobile v-if="isMobile" />
  <UsageGuideDesktop v-else />
</template>


