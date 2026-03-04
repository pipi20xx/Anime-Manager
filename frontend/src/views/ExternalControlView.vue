<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import ExternalControlDesktop from './desktop/ExternalControlDesktop.vue'
import ExternalControlMobile from './mobile/ExternalControlMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <ExternalControlMobile v-if="isMobile" />
  <ExternalControlDesktop v-else />
</template>