<script setup lang="ts">
import RulePreviewModalDesktop from './desktop/RulePreviewModalDesktop.vue'

const props = defineProps<{
  show: boolean
  ruleData: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <RulePreviewModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
