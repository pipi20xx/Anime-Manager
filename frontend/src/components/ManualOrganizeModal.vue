<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import ManualOrganizeModalDesktop from './desktop/ManualOrganizeModalDesktop.vue'
import ManualOrganizeModalMobile from '../views/mobile/ManualOrganizeModalMobile.vue'

const props = defineProps<{
  show: boolean
  currentPath: string
  availableRules: any[]
  apiBase: string
  defaultTask: any
}>()

const emit = defineEmits(['update:show', 'run', 'run-background'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onRun = (val: any) => emit('run', val)
const onRunBackground = (val: any) => emit('run-background', val)
</script>

<template>
  <ManualOrganizeModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @run="onRun"
    @run-background="onRunBackground"
  />
  <ManualOrganizeModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @run="onRun"
    @run-background="onRunBackground"
  />
</template>