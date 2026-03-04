<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SecondaryRuleViewDesktop from '../components/desktop/SecondaryRuleViewDesktop.vue'
import SecondaryRuleViewMobile from '../components/mobile/SecondaryRuleViewMobile.vue'

const { isMobile } = useIsMobile()
</script>

<template>
  <SecondaryRuleViewMobile v-if="isMobile" />
  <SecondaryRuleViewDesktop v-else />
</template>