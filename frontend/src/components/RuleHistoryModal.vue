<script setup lang="ts">
import RuleHistoryModalMobile from './mobile/RuleHistoryModalMobile.vue'

const props = defineProps<{
  show: boolean
  rule: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <RuleHistoryModalMobile
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
