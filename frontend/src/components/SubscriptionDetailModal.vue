<script setup lang="ts">
import SubscriptionDetailModalDesktop from './desktop/SubscriptionDetailModalDesktop.vue'

const props = defineProps<{
  show: boolean
  sub: any
  apiBase: string
}>()

const emit = defineEmits(['update:show'])
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <SubscriptionDetailModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
