<script setup lang="ts">
import ClientEditModalDesktop from './desktop/ClientEditModalDesktop.vue'

const props = defineProps<{
  show: boolean
  clientData: any
  isNew: boolean
  allClients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <ClientEditModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
