<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import HealthCheckManagerDesktop from './desktop/HealthCheckManagerDesktop.vue'
import HealthCheckManagerMobile from './mobile/HealthCheckManagerMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <HealthCheckManagerMobile v-if="isMobile" />
  <HealthCheckManagerDesktop v-else />
</template>