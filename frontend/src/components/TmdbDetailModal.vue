<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import TmdbDetailModalDesktop from './desktop/TmdbDetailModalDesktop.vue'
import TmdbDetailModalMobile from './mobile/TmdbDetailModalMobile.vue'

const props = defineProps<{
  show: boolean
  tmdbId: string | number
  mediaType: 'movie' | 'tv' | string
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
</script>

<template>
  <TmdbDetailModalMobile v-if="isMobile" v-bind="props" @update:show="onUpdateShow" />
  <TmdbDetailModalDesktop v-else v-bind="props" @update:show="onUpdateShow" />
</template>
