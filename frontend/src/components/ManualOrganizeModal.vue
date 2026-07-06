<script setup lang="ts">
import ManualOrganizeModalDesktop from './desktop/ManualOrganizeModalDesktop.vue'

const props = defineProps<{
  show: boolean
  currentPath: string
  availableRules: any[]
  apiBase: string
  defaultTask: any
}>()

const emit = defineEmits(['update:show', 'run', 'run-background'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onRun = (val: any) => emit('run', val)
const onRunBackground = (val: any) => emit('run-background', val)
</script>

<template>
  <ManualOrganizeModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @run="onRun"
    @run-background="onRunBackground"
  />
</template>
