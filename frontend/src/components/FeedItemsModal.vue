<script setup lang="ts">
import FeedItemsModalMobile from './mobile/FeedItemsModalMobile.vue'

const props = defineProps<{
  show: boolean
  feed: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <FeedItemsModalMobile
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
