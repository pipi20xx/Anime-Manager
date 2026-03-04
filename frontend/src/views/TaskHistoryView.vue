<script setup lang="ts">
import { computed } from 'vue'
import TaskHistoryViewDesktop from './desktop/TaskHistoryViewDesktop.vue'
import TaskHistoryViewMobile from './mobile/TaskHistoryViewMobile.vue'
import { useIsMobile } from '../composables/useIsMobile'

const { isMobile } = useIsMobile()
</script>

<template>
  <TaskHistoryViewDesktop v-if="!isMobile" />
  <TaskHistoryViewMobile v-else />
</template>
