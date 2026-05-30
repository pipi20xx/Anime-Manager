<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RuleHistoryModalDesktop from './desktop/RuleHistoryModalDesktop.vue'
import RuleHistoryModalMobile from './mobile/RuleHistoryModalMobile.vue'

const props = defineProps<{
  show: boolean
  rule: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <RuleHistoryModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
  />
  <RuleHistoryModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
