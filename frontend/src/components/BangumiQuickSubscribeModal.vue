<script setup lang="ts">
import BangumiQuickSubscribeModalDesktop from './desktop/BangumiQuickSubscribeModalDesktop.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show', 'finish'])

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}

const onFinish = () => {
  emit('finish')
}
</script>

<template>
  <BangumiQuickSubscribeModalDesktop
    :show="show"
    @update:show="onUpdateShow"
    @finish="onFinish"
  />
</template>
