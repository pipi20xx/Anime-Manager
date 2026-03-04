<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import TaskEditModalDesktop from './desktop/TaskEditModalDesktop.vue'
import TaskEditModalMobile from './mobile/TaskEditModalMobile.vue'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  availableRules: any[]
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <TaskEditModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
  <TaskEditModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @save="onSave"
  />
</template>
