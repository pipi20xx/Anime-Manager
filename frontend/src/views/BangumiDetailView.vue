<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import BangumiDetailViewDesktop from './desktop/BangumiDetailViewDesktop.vue'
import BangumiDetailViewMobile from './mobile/BangumiDetailViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <BangumiDetailViewMobile v-if="isMobile" />
  <BangumiDetailViewDesktop v-else />
</template>
