<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import TmdbFullDataViewDesktop from '../components/desktop/TmdbFullDataViewDesktop.vue'
import TmdbFullDataViewMobile from '../components/mobile/TmdbFullDataViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <TmdbFullDataViewMobile v-if="isMobile" />
  <TmdbFullDataViewDesktop v-else />
</template>
