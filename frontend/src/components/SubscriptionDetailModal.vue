<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SubscriptionDetailModalDesktop from './desktop/SubscriptionDetailModalDesktop.vue'
import SubscriptionDetailModalMobile from './mobile/SubscriptionDetailModalMobile.vue'

const props = defineProps<{
  show: boolean
  sub: any
  apiBase: string
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <SubscriptionDetailModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
  />
  <SubscriptionDetailModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
