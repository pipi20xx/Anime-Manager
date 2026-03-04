<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import BangumiQuickSubscribeModalDesktop from './desktop/BangumiQuickSubscribeModalDesktop.vue'
import BangumiQuickSubscribeModalMobile from './mobile/BangumiQuickSubscribeModalMobile.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show', 'finish'])

const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => {
  emit('update:show', val)
}

const onFinish = () => {
  emit('finish')
}
</script>

<template>
  <BangumiQuickSubscribeModalMobile 
    v-if="isMobile" 
    :show="show" 
    @update:show="onUpdateShow"
    @finish="onFinish"
  />
  <BangumiQuickSubscribeModalDesktop 
    v-else 
    :show="show" 
    @update:show="onUpdateShow"
    @finish="onFinish"
  />
</template>
