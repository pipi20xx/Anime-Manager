<script setup lang="ts">
import SubscriptionEditModalDesktop from './desktop/SubscriptionEditModalDesktop.vue'

const props = defineProps<{
  show: boolean
  subData?: any
  isNew: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <SubscriptionEditModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
