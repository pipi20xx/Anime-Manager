<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SettingsViewDesktop from '../components/desktop/SettingsViewDesktop.vue'
import SettingsViewMobile from '../components/mobile/SettingsViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <SettingsViewMobile v-if="isMobile" />
  <SettingsViewDesktop v-else />
</template>
