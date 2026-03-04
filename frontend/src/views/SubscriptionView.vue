<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SubscriptionViewDesktop from './desktop/SubscriptionViewDesktop.vue'
import SubscriptionViewMobile from './mobile/SubscriptionViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <SubscriptionViewMobile v-if="isMobile" />
  <SubscriptionViewDesktop v-else />
</template>