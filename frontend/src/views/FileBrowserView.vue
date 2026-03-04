<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import FileBrowserViewDesktop from './desktop/FileBrowserViewDesktop.vue'
import FileBrowserViewMobile from './mobile/FileBrowserViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <FileBrowserViewMobile v-if="isMobile" />
  <FileBrowserViewDesktop v-else />
</template>