<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import TmdbDetailViewDesktop from './desktop/TmdbDetailViewDesktop.vue'
import TmdbDetailViewMobile from './mobile/TmdbDetailViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <TmdbDetailViewMobile v-if="isMobile" />
  <TmdbDetailViewDesktop v-else />
</template>
