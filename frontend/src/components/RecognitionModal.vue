<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import RecognitionModalDesktop from './desktop/RecognitionModalDesktop.vue'
import RecognitionModalMobile from '../views/mobile/RecognitionModalMobile.vue'

const props = defineProps<{
  show: boolean
  file: any
  data: any
  previewPath: string
  loading: boolean
  isRenaming: boolean
  apiBase: string
  availableRules: any[]
}>()

const emit = defineEmits(['update:show', 'recognize', 'rename'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onRecognize = (val: any) => emit('recognize', val)
const onRename = () => emit('rename')
</script>

<template>
  <RecognitionModalMobile
    v-if="isMobile"
    v-bind="props"
    @update:show="onUpdateShow"
    @recognize="onRecognize"
    @rename="onRename"
  />
  <RecognitionModalDesktop
    v-else
    v-bind="props"
    @update:show="onUpdateShow"
    @recognize="onRecognize"
    @rename="onRename"
  />
</template>

