<script setup lang="ts">
import { useIsMobile } from '../../composables/useIsMobile'
import DiscoveryTabDesktop from './desktop/DiscoveryTabDesktop.vue'
import DiscoveryTabMobile from './mobile/DiscoveryTabMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <DiscoveryTabMobile v-if="isMobile" />
  <DiscoveryTabDesktop v-else />
</template>
