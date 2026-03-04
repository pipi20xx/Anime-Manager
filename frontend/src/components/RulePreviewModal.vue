<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RulePreviewModalDesktop from './desktop/RulePreviewModalDesktop.vue'
import RulePreviewModalMobile from './mobile/RulePreviewModalMobile.vue'

const props = defineProps<{
  show: boolean
  ruleData: any
  clients: any[]
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()
const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <RulePreviewModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
  />
  <RulePreviewModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
  />
</template>
