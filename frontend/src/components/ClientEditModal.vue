<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import ClientEditModalDesktop from './desktop/ClientEditModalDesktop.vue'
import ClientEditModalMobile from './mobile/ClientEditModalMobile.vue'

const props = defineProps<{
  show: boolean
  clientData: any
  isNew: boolean
  allClients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <ClientEditModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
  <ClientEditModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>