<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import BangumiDetailModalDesktop from './desktop/BangumiDetailModalDesktop.vue'
import BangumiDetailModalMobile from './mobile/BangumiDetailModalMobile.vue'

const props = defineProps<{
  show: boolean
  subjectId: string | number
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <BangumiDetailModalMobile v-if="isMobile" v-bind="props" @update:show="onUpdateShow" />
  <BangumiDetailModalDesktop v-else v-bind="props" @update:show="onUpdateShow" />
</template>
