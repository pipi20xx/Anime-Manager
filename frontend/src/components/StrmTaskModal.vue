<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import StrmTaskModalDesktop from './desktop/StrmTaskModalDesktop.vue'
import StrmTaskModalMobile from './mobile/StrmTaskModalMobile.vue'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <StrmTaskModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
  <StrmTaskModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
