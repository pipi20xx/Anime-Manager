<script setup lang="ts">
import { useIsMobile } from '../../composables/useIsMobile'
import RecommendTabDesktop from './desktop/RecommendTabDesktop.vue'
import RecommendTabMobile from './mobile/RecommendTabMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <RecommendTabMobile v-if="isMobile" />
  <RecommendTabDesktop v-else />
</template>
