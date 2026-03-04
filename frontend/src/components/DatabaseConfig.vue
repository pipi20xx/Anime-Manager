<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import DatabaseConfigDesktop from './desktop/DatabaseConfigDesktop.vue'
import DatabaseConfigMobile from './mobile/DatabaseConfigMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <DatabaseConfigMobile v-if="isMobile" />
  <DatabaseConfigDesktop v-else />
</template>