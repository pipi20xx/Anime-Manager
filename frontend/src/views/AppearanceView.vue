<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import AppearanceViewDesktop from './desktop/AppearanceViewDesktop.vue'
import AppearanceViewMobile from './mobile/AppearanceViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <AppearanceViewMobile v-if="isMobile" />
  <AppearanceViewDesktop v-else />
</template>
