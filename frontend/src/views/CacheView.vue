<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import CacheViewDesktop from './desktop/CacheViewDesktop.vue'
import CacheViewMobile from './mobile/CacheViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <CacheViewMobile v-if="isMobile" />
  <CacheViewDesktop v-else />
</template>
