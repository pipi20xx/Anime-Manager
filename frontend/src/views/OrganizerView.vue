<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import OrganizerViewDesktop from './desktop/OrganizerViewDesktop.vue'
import OrganizerViewMobile from './mobile/OrganizerViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <OrganizerViewMobile v-if="isMobile" />
  <OrganizerViewDesktop v-else />
</template>