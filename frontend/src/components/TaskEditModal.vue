<script setup lang="ts">
import TaskEditModalDesktop from './desktop/TaskEditModalDesktop.vue'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  availableRules: any[]
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <TaskEditModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
