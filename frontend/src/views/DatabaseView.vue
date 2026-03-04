<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import DatabaseViewDesktop from '../components/desktop/DatabaseViewDesktop.vue'
import DatabaseViewMobile from '../components/mobile/DatabaseViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <DatabaseViewMobile v-if="isMobile" />
  <DatabaseViewDesktop v-else />
</template>