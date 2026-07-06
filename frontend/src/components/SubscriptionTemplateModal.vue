<script setup lang="ts">
import SubscriptionTemplateModalDesktop from './desktop/SubscriptionTemplateModalDesktop.vue'

const props = defineProps<{
  show: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}
</script>

<template>
  <SubscriptionTemplateModalDesktop
    :show="show"
    :clients="clients"
    @update:show="onUpdateShow"
  />
</template>
