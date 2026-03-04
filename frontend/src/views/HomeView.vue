<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import HomeViewDesktop from './desktop/HomeViewDesktop.vue'
import HomeViewMobile from './mobile/HomeViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <HomeViewMobile v-if="isMobile" />
  <HomeViewDesktop v-else />
</template>
