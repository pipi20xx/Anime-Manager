<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SystemLogsViewDesktop from './desktop/SystemLogsViewDesktop.vue'
import SystemLogsViewMobile from './mobile/SystemLogsViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <SystemLogsViewMobile v-if="isMobile" />
  <SystemLogsViewDesktop v-else />
</template>
