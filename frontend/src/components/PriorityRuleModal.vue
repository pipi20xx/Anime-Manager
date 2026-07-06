<script setup lang="ts">
import PriorityRuleModalDesktop from './desktop/PriorityRuleModalDesktop.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}
</script>

<template>
  <PriorityRuleModalDesktop
    :show="show"
    @update:show="onUpdateShow"
  />
</template>
