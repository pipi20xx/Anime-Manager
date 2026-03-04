<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import MaintenanceManagerDesktop from './desktop/MaintenanceManagerDesktop.vue'
import MaintenanceManagerMobile from './mobile/MaintenanceManagerMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <MaintenanceManagerMobile v-if="isMobile" />
  <MaintenanceManagerDesktop v-else />
</template>