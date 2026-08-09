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

// 解析单条日志: "18:13:09 | INFO  | 消息内容" → { time, level, message }
function parseLog(raw: string): { raw: string; time: string; level: string; message: string } {
  const m = raw.match(/^(\d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*(.*)$/)
  if (m) return { raw, time: m[1], level: m[2].toLowerCase(), message: m[3] }
  return { raw, time: '', level: getLogLevel(raw), message: raw }
}

// 按秒分组的日志
const groupedLogs = computed(() => {
  const parsed = filteredLogs.value.map(parseLog)
  const groups = new Map<string, { raw: string; time: string; level: string; message: string }[]>()
  for (const log of parsed) {
    const key = log.time || '--:--:--'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(log)
  }
  return Array.from(groups.entries()).map(([key, logs]) => ({ key, logs }))
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
  <GlassDialog v-model="systemStore.showLogModal" :max-width="900" :cancel-visible="false">
    <template #title>
      <v-icon start>mdi-card-text-outline</v-icon>
      系统日志
      <v-spacer />
      <v-btn-toggle v-model="logFilter" density="compact" variant="tonal" rounded="lg" class="mr-2 align-self-center">
        <v-btn
          v-for="opt in filterOptions"
          :key="opt.value"
          :value="opt.value"
          density="compact"
          :style="logFilter === opt.value && opt.color ? { color: opt.color } : {}"
        >
          {{ opt.title }}
        </v-btn>
      </v-btn-toggle>
      <v-btn variant="tonal" density="compact" color="error" prepend-icon="mdi-delete-outline" class="clear-log-btn" @click="clearLogs">清空</v-btn>
    </template>
    <div ref="logContainer" class="log-terminal">
      <div v-for="group in groupedLogs" :key="group.key" class="log-group">
        <div class="log-group-line"></div>
        <div class="log-group-items">
          <div
            v-for="(log, i) in group.logs"
            :key="i"
            class="log-entry"
            :class="`log-entry--${log.level}`"
          >
            <span v-if="log.time" class="log-entry__time">{{ log.time }}</span>
            <span class="log-entry__level" :data-level="log.level">{{ log.level }}</span>
            <span class="log-entry__msg">{{ log.message }}</span>
          </div>
        </div>
      </div>
      <div v-if="!filteredLogs.length" class="log-terminal__empty">
        暂无日志
      </div>
    </div>
  </GlassDialog>
</template>

<style scoped>
.clear-log-btn {
  height: 32px !important;
}

/* 按秒分组的竖条布局 */
.log-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.log-group-line {
  width: 2px;
  background-color: rgb(var(--v-theme-primary));
  border-radius: 1px;
  flex-shrink: 0;
  align-self: stretch;
  margin: 2px 0;
  opacity: 0.4;
}
.log-group-items {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
