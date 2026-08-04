<script setup lang="ts">
/**
 * AppNotification — 全局通知组件
 *
 * 从 useNotification composable 读取队列，渲染 v-snackbar。
 * - 支持队列：当前通知关闭后自动显示下一条
 * - 每条通知有类型图标（success / error / warning / info）
 * - :scrim="false" 避免全屏遮罩
 * - :key 按 id 强制重建，保证 timeout 重新计时
 */
import { ref, watch } from 'vue'
import { useNotification } from '@/composables'

const { current, dismiss, getIcon } = useNotification()

/** snackbar 的可见状态，与 current 联动 */
const show = ref(false)

watch(current, (item) => {
  show.value = item !== null
}, { immediate: true })

/** snackbar 超时 / 外部关闭时回调 */
function onUpdate(val: boolean) {
  if (!val) dismiss()
}
</script>

<template>
  <v-snackbar
    v-if="current"
    :key="current.id"
    :model-value="show"
    @update:model-value="onUpdate"
    :color="current.type"
    :timeout="current.timeout"
    location="top right"
    :scrim="false"
  >
    <div class="d-flex align-center">
      <v-icon :icon="getIcon(current.type)" :color="current.type" class="mr-3" />
      <div>
        <div v-if="current.title" class="font-weight-bold mb-1">{{ current.title }}</div>
        <div>{{ current.message }}</div>
      </div>
    </div>
    <template #actions>
      <v-btn variant="text" icon="mdi-close" size="small" @click="dismiss()" />
    </template>
  </v-snackbar>
</template>
