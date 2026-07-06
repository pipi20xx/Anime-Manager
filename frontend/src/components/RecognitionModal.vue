<script setup lang="ts">
import RecognitionModalDesktop from './desktop/RecognitionModalDesktop.vue'

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

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onRecognize = (val: any) => emit('recognize', val)
const onRename = () => emit('rename')
</script>

<template>
  <RecognitionModalDesktop
    v-bind="props"
    @update:show="onUpdateShow"
    @recognize="onRecognize"
    @rename="onRename"
  />
</template>
