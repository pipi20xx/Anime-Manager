<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import OrganizeHistoryDesktop from '../components/desktop/OrganizeHistoryDesktop.vue'
import OrganizeHistoryMobile from '../components/mobile/OrganizeHistoryMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <OrganizeHistoryMobile v-if="isMobile" />
  <OrganizeHistoryDesktop v-else />
</template>