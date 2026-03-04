<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import FeedItemsModalDesktop from './desktop/FeedItemsModalDesktop.vue'
import FeedItemsModalMobile from './mobile/FeedItemsModalMobile.vue'

const props = defineProps<{
  show: boolean
  feed: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <FeedItemsModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
  />
  <FeedItemsModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>