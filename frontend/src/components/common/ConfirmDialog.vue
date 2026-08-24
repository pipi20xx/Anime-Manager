<script setup lang="ts">
import { useConfirm } from '@/composables'
import { GlassDialog } from '@/glass'

const { show, options, onConfirm, onCancel, onDismiss } = useConfirm()
</script>

<template>
  <GlassDialog v-model="show" :max-width="420" :scrollable="false"
    :title="options.title" :cancel-text="options.cancelText"
    @cancel="onCancel"
    @dismiss="onDismiss"
  >
    {{ options.content }}
    <template #actions>
      <v-btn :color="options.confirmColor" variant="tonal" prepend-icon="mdi-check" @click="onConfirm">
        {{ options.confirmText }}
      </v-btn>
    </template>
  </GlassDialog>
</template>
