<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import UserMappingViewDesktop from '../components/desktop/UserMappingViewDesktop.vue'
import UserMappingViewMobile from '../components/mobile/UserMappingViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <UserMappingViewMobile v-if="isMobile" />
  <UserMappingViewDesktop v-else />
</template>
