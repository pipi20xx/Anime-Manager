<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import CalendarViewDesktop from '../components/desktop/CalendarViewDesktop.vue'
import CalendarViewMobile from '../components/mobile/CalendarViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <CalendarViewMobile v-if="isMobile" />
  <CalendarViewDesktop v-else />
</template>
