<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import TmdbPersonDetailViewDesktop from './desktop/TmdbPersonDetailViewDesktop.vue'
import TmdbPersonDetailViewMobile from './mobile/TmdbPersonDetailViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <TmdbPersonDetailViewMobile v-if="isMobile" />
  <TmdbPersonDetailViewDesktop v-else />
</template>
