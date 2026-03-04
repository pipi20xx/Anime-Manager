<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import SubscriptionEditModalDesktop from './desktop/SubscriptionEditModalDesktop.vue'
import SubscriptionEditModalMobile from './mobile/SubscriptionEditModalMobile.vue'

const props = defineProps<{
  show: boolean
  subData?: any
  isNew: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])

const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <SubscriptionEditModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
  <SubscriptionEditModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
