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

const levelColors: Record<string, string> = {
  INFO: '#4ecdc4',
  WARNING: '#FFB74D',
  ERROR: '#EF5350',
  CRITICAL: '#F48FB1',
  DEBUG: 'rgba(255,255,255,0.4)',
  SUCCESS: '#81C784',
}

const filterOptions = [
  { title: '全部', value: 'all', color: '#ffffff' },
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

// 根据日志内容判断级别并返回颜色
function getLogColor(entry: string): string {
  const upper = entry.toUpperCase()
  if (upper.includes('CRITICAL')) return levelColors.CRITICAL
  if (upper.includes('ERROR')) return levelColors.ERROR
  if (upper.includes('WARNING')) return levelColors.WARNING
  if (upper.includes('SUCCESS')) return levelColors.SUCCESS
  if (upper.includes('DEBUG')) return levelColors.DEBUG
  return levelColors.INFO
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
          :style="logFilter === opt.value ? { color: opt.color } : {}"
        >
          <span :style="{ color: opt.color }">{{ opt.title }}</span>
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
        :style="{ color: getLogColor(entry) }"
      >
        <span class="log-entry__msg">{{ entry }}</span>
      </div>
      <div v-if="!filteredLogs.length" class="text-center pa-8 text-medium-emphasis">
        暂无日志
      </div>
    </div>
  </GlassDialog>
</template>
