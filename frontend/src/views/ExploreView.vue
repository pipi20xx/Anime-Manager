<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import ExploreViewDesktop from './desktop/ExploreViewDesktop.vue'
import ExploreViewMobile from './mobile/ExploreViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <ExploreViewMobile v-if="isMobile" />
  <ExploreViewDesktop v-else />
</template>