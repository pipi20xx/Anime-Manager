<script setup lang="ts">
import { useIsMobile } from '../composables/useIsMobile'
import ClassifierEditModalDesktop from './desktop/ClassifierEditModalDesktop.vue'
import ClassifierEditModalMobile from './mobile/ClassifierEditModalMobile.vue'

const props = defineProps<{
  show: boolean
  ruleData: any
  isNew: boolean
}>()

const emit = defineEmits(['update:show', 'save'])
const { isMobile } = useIsMobile()

const onUpdateShow = (val: boolean) => emit('update:show', val)
const onSave = (val: any) => emit('save', val)
</script>

<template>
  <ClassifierEditModalMobile v-if="isMobile" v-bind="props" @update:show="onUpdateShow" @save="onSave" />
  <ClassifierEditModalDesktop v-else v-bind="props" @update:show="onUpdateShow" @save="onSave" />
</template>