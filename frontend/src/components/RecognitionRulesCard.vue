<script setup lang="ts">
/**
 * RecognitionRulesCard - 规则应用日志卡片
 *
 * 展示识别过程中应用的规则替换、渲染词处理等日志
 */
import { computed } from 'vue'
import { NCard, NIcon, NScrollbar } from 'naive-ui'
import {
  ScaleIcon as RuleIcon
} from '@heroicons/vue/24/outline'
import { recognitionState } from '../store/recognitionStore'

// 过滤出规则相关的日志行
const ruleLogs = computed(() => {
  const logs = recognitionState.logs || []
  return logs.filter(log => {
    const logStr = String(log)
    return logStr.includes('[规则]') ||
           logStr.includes('[Render]') ||
           logStr.includes('[特权]') ||
           logStr.includes('🧠') ||
           logStr.includes('🏷️')
  })
})

// 解析日志行，提取类型和内容
const parsedLogs = computed(() => {
  return ruleLogs.value.map(log => {
    const logStr = String(log)
    let type = 'other'
    let icon = '⚙️'

    if (logStr.includes('[特权]')) {
      type = 'privilege'
      icon = '⚡'
    } else if (logStr.includes('[规则][社区]')) {
      type = 'community'
      icon = '🌐'
    } else if (logStr.includes('[规则][内置]')) {
      type = 'builtin'
      icon = '🔧'
    } else if (logStr.includes('[Render]')) {
      type = 'render'
      icon = '🏷️'
    } else if (logStr.includes('🧠')) {
      type = 'memory'
      icon = '🧠'
    }

    return { type, icon, content: logStr }
  })
})
</script>

<template>
  <n-card
    v-if="parsedLogs.length > 0"
    bordered
    title="规则应用日志"
    size="small"
    class="rules-card"
  >
    <template #header-extra>
      <n-icon class="rules-icon" size="20"><RuleIcon /></n-icon>
    </template>

    <div class="rules-list">
      <div
        v-for="(item, index) in parsedLogs"
        :key="index"
        :class="['rule-item', `rule-item--${item.type}`]"
      >
        <span class="rule-icon">{{ item.icon }}</span>
        <span class="rule-content">{{ item.content }}</span>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.rules-card {
  background: var(--bg-surface);
  border-radius: var(--card-border-radius, 8px);
}

.rules-icon {
  color: var(--n-primary-color);
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.rule-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  background: var(--app-surface-inner);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  line-height: 1.4;
}

.rule-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.rule-content {
  color: var(--text-secondary);
  word-break: break-all;
}

/* 类型样式 */
.rule-item--privilege {
  background: rgba(255, 152, 0, 0.08);
  border-left: 2px solid #ff9800;
}

.rule-item--community {
  background: rgba(33, 150, 243, 0.08);
  border-left: 2px solid #2196f3;
}

.rule-item--builtin {
  background: rgba(76, 175, 80, 0.08);
  border-left: 2px solid #4caf50;
}

.rule-item--render {
  background: rgba(156, 39, 176, 0.08);
  border-left: 2px solid #9c27b0;
}

.rule-item--memory {
  background: rgba(0, 188, 212, 0.08);
  border-left: 2px solid #00bcd4;
}

/* 移动端适配 */
@media (max-width: 767px) {
  .rule-item {
    font-size: var(--text-xs);
    padding: var(--space-1);
  }
}
</style>