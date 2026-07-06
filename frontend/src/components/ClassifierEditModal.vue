<script setup lang="ts">
import ClassifierEditModalDesktop from './desktop/ClassifierEditModalDesktop.vue'

const props = defineProps<{
  show: boolean
  ruleData: any
  isNew: boolean
}>()

const emit = defineEmits(['update:show', 'save'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <ClassifierEditModalDesktop v-bind="props" @update:show="onUpdateShow" @save="onSave" />
</template>
