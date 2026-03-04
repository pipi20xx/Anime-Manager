<script setup lang="ts">
import { useIsMobile } from '../../composables/useIsMobile'
import SearchTabDesktop from './desktop/SearchTabDesktop.vue'
import SearchTabMobile from './mobile/SearchTabMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <SearchTabMobile v-if="isMobile" />
  <SearchTabDesktop v-else />
</template>
