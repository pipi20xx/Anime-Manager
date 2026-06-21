<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import AiLabViewDesktop from './desktop/AiLabViewDesktop.vue'
import AiLabViewMobile from './mobile/AiLabViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <AiLabViewMobile v-if="isMobile" />
  <AiLabViewDesktop v-else />
</template>
