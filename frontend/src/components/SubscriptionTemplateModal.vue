<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SubscriptionTemplateModalDesktop from './desktop/SubscriptionTemplateModalDesktop.vue'
import SubscriptionTemplateModalMobile from './mobile/SubscriptionTemplateModalMobile.vue'

const props = defineProps<{
  show: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}
</script>

<template>
  <SubscriptionTemplateModalMobile 
    v-if="isMobile" 
    :show="show" 
    :clients="clients"
    @update:show="onUpdateShow" 
  />
  <SubscriptionTemplateModalDesktop 
    v-else 
    :show="show" 
    :clients="clients"
    @update:show="onUpdateShow" 
  />
</template>
