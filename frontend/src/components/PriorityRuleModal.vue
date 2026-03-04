<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import PriorityRuleModalDesktop from './desktop/PriorityRuleModalDesktop.vue'
import PriorityRuleModalMobile from './mobile/PriorityRuleModalMobile.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}
</script>

<template>
  <PriorityRuleModalMobile 
    v-if="isMobile" 
    :show="show" 
    @update:show="onUpdateShow" 
  />
  <PriorityRuleModalDesktop 
    v-else 
    :show="show" 
    @update:show="onUpdateShow" 
  />
</template>
