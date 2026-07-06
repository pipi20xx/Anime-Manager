<script setup lang="ts">
import LogConsoleModalDesktop from './desktop/LogConsoleModalDesktop.vue'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <LogConsoleModalDesktop v-bind="props" @update:show="onUpdateShow" />
</template>
