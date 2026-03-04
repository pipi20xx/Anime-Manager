<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import LogConsoleModalDesktop from './desktop/LogConsoleModalDesktop.vue'
import LogConsoleModalMobile from './mobile/LogConsoleModalMobile.vue'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <LogConsoleModalMobile v-if="isMobile" v-bind="props" @update:show="onUpdateShow" />
  <LogConsoleModalDesktop v-else v-bind="props" @update:show="onUpdateShow" />
</template>
