<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import JackettSearchViewDesktop from './desktop/JackettSearchViewDesktop.vue'
import JackettSearchViewMobile from './mobile/JackettSearchViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <JackettSearchViewMobile v-if="isMobile" />
  <JackettSearchViewDesktop v-else />
</template>