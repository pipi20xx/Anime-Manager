<script setup lang="ts">
/**
 * LogTerminal — 全局日志终端组件
 *
 * 使用 systemStore.showLogModal 控制显隐，
 * 底层使用 GlassDialog 弹窗 + Vuetify 组件
 */
import { ref, computed, nextTick, watch } from 'vue'
import { useSystemStore } from '@/stores'
import { useNotification } from '@/composables'
import GlassDialog from '@/components/common/GlassDialog.vue'

const systemStore = useSystemStore()
const { info, error: showError } = useNotification()
const logContainer = ref<HTMLElement>()

// 日志数据
const logFilter = ref('all')
const autoScroll = ref(true)

const filterOptions = [
  { title: '全部', value: 'all' },
  { title: 'INFO', value: 'INFO', color: '#4ecdc4' },
  { title: 'WARNING', value: 'WARNING', color: '#FFB74D' },
  { title: 'ERROR', value: 'ERROR', color: '#EF5350' },
]

const filteredLogs = computed(() => {
  if (logFilter.value === 'all') return systemStore.logs
  return systemStore.logs.filter(l => {
    // logs 是 string[]，简单匹配
    return l.toLowerCase().includes(logFilter.value.toLowerCase())
  })
})

// 弹窗打开时自动滚动到底部
watch(() => systemStore.showLogModal, async (val) => {
  if (val) {
    await nextTick()
    logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
  }
})

// 切换筛选时也滚动到底部
watch(logFilter, async () => {
  await nextTick()
  logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
})

// 新日志到达时自动滚动
watch(() => filteredLogs.value.length, async () => {
  if (autoScroll.value) {
    await nextTick()
    logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight })
  }
})

function clearLogs() {
  systemStore.clearLogs()
}

// 根据日志内容判断级别
function getLogLevel(entry: string): string {
  const upper = entry.toUpperCase()
  if (upper.includes('CRITICAL')) return 'critical'
  if (upper.includes('ERROR')) return 'error'
  if (upper.includes('WARNING')) return 'warning'
  if (upper.includes('SUCCESS')) return 'success'
  if (upper.includes('DEBUG')) return 'debug'
  return 'info'
}

// 根据级别返回 CSS class
function getLogLevelClass(entry: string): string {
  return `log-entry--${getLogLevel(entry)}`
}
</script>

<template>
  <GlassDialog v-model="systemStore.showLogModal" :max-width="900" :cancel-visible="false" :scrollable="false">
    <template #title>
      <v-icon start>mdi-card-text-outline</v-icon>
      系统日志
      <v-spacer />
      <v-btn-toggle v-model="logFilter" density="compact" variant="tonal" rounded="lg" class="mr-2">
        <v-btn 
          v-for="opt in filterOptions" 
          :key="opt.value" 
          :value="opt.value" 
          size="small"
          :style="logFilter === opt.value && opt.color ? { color: opt.color } : {}"
        >
          {{ opt.title }}
        </v-btn>
      </v-btn-toggle>
      <v-btn variant="tonal" size="small" color="error" prepend-icon="mdi-delete-outline" @click="clearLogs">清空</v-btn>
      <v-btn variant="text" size="small" icon="mdi-close" @click="systemStore.showLogModal = false" />
    </template>
    <div ref="logContainer" class="log-terminal">
      <div
        v-for="(entry, i) in filteredLogs"
        :key="i"
        class="log-entry"
        :class="getLogLevelClass(entry)"
      >
        <span class="log-entry__level" :data-level="getLogLevel(entry)">{{ getLogLevel(entry) }}</span>
        <span class="log-entry__msg">{{ entry }}</span>
      </div>
      <div v-if="!filteredLogs.length" class="log-terminal__empty">
        暂无日志
      </div>
    </div>
  </GlassDialog>
</template>
