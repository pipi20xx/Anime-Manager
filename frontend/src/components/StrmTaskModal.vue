<script setup lang="ts">
import StrmTaskModalDesktop from './desktop/StrmTaskModalDesktop.vue'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <StrmTaskModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
