<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import StrmGeneratorViewDesktop from './desktop/StrmGeneratorViewDesktop.vue'
import StrmGeneratorViewMobile from './mobile/StrmGeneratorViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <StrmGeneratorViewMobile v-if="isMobile" />
  <StrmGeneratorViewDesktop v-else />
</template>