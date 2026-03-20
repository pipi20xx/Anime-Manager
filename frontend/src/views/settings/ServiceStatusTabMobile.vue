<template>
  <div class="service-status-mobile">
    <n-space vertical size="medium">
      <!-- 系统服务 -->
      <div class="m-card">
        <div class="m-card-header">
          <div class="header-title">
            <span class="m-card-title">系统服务</span>
            <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">{{ runningServicesCount }}/{{ data.services.length }}</n-tag>
          </div>
        </div>
        <div class="service-list">
          <div v-for="service in data.services" :key="service.id" class="service-item">
            <div class="service-info">
              <span class="service-name">{{ service.name }}</span>
              <div class="service-meta">
                <span>{{ service.interval }}</span>
                <span v-if="service.next_run">· {{ formatNextRun(service.next_run) }}</span>
              </div>
            </div>
            <n-tag size="tiny" round :bordered="false" :style="getStatusTagStyle(service)">
              {{ getStatusTag(service).text }}
            </n-tag>
          </div>
        </div>
      </div>

      <!-- 文件监控 -->
      <div class="m-card" v-if="data.monitors.length > 0">
        <div class="m-card-header">
          <div class="header-title">
            <span class="m-card-title">文件监控</span>
            <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' }">{{ runningMonitorsCount }}/{{ data.monitors.length }}</n-tag>
          </div>
        </div>
        <div class="monitor-list">
          <div v-for="monitor in data.monitors" :key="monitor.id" class="monitor-item">
            <div class="monitor-header">
              <div class="monitor-tags">
                <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: monitor.type === 'organize' ? '#0288d1' : '#2e7d32', borderColor: 'transparent' }">
                  {{ monitor.type === 'organize' ? '整理' : 'STRM' }}
                </n-tag>
                <span class="monitor-name">{{ monitor.name }}</span>
                <n-tag v-if="monitor.type === 'strm' && monitor.webhook_enabled" size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' }">
                  接受联动
                </n-tag>
                <n-tag v-if="monitor.type === 'organize' && monitor.check_emby_exists" size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">
                  Emby检查
                </n-tag>
                <n-tag v-if="monitor.type === 'organize' && monitor.calculate_hash" size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' }">
                  哈希计算
                </n-tag>
              </div>
              <n-tag size="tiny" round :bordered="false" :style="getStatusTagStyle(monitor)">
                {{ getStatusTag(monitor).text }}
              </n-tag>
            </div>
            <div class="monitor-meta">
              <div class="meta-line">
                <span class="label">源:</span>
                <code>{{ monitor.source_dir || '-' }}</code>
              </div>
              <div class="meta-line" v-if="monitor.running && monitor.queue_size > 0">
                <n-text type="success">队列: {{ monitor.queue_size }} 待处理</n-text>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 运行时 -->
      <div class="m-card">
        <div class="m-card-header">
          <span class="m-card-title">运行时</span>
        </div>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-value">{{ data.observers_count }}</div>
            <div class="stat-label">观察器</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ data.workers_count }}</div>
            <div class="stat-label">工作线程</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ data.queues_count }}</div>
            <div class="stat-label">队列</div>
          </div>
        </div>
      </div>

      <!-- 规则统计 -->
      <div class="m-card">
        <div class="m-card-header">
          <span class="m-card-title">规则统计</span>
        </div>
        <div class="rule-list">
          <div class="rule-item">
            <span class="rule-name">自定义识别词</span>
            <n-space :size="4">
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">本地 {{ data.rules.custom_noise.local }}</n-tag>
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">远程 {{ data.rules.custom_noise.remote }}</n-tag>
            </n-space>
          </div>
          <div class="rule-item">
            <span class="rule-name">自定义制作组</span>
            <n-space :size="4">
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">本地 {{ data.rules.custom_groups.local }}</n-tag>
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">远程 {{ data.rules.custom_groups.remote }}</n-tag>
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' }">内置 {{ data.rules.custom_groups.builtin || 0 }}</n-tag>
            </n-space>
          </div>
          <div class="rule-item">
            <span class="rule-name">自定义渲染词</span>
            <n-space :size="4">
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">本地 {{ data.rules.custom_render.local }}</n-tag>
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">远程 {{ data.rules.custom_render.remote }}</n-tag>
            </n-space>
          </div>
          <div class="rule-item">
            <span class="rule-name">特权规则</span>
            <n-space :size="4">
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">本地 {{ data.rules.privileged.local }}</n-tag>
              <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">远程 {{ data.rules.privileged.remote }}</n-tag>
            </n-space>
          </div>
        </div>
      </div>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  NSpace, NTag, NText
} from 'naive-ui'
import { useServiceStatus } from '../../composables/views/useServiceStatus'

const { data, formatNextRun, getStatusTag } = useServiceStatus()

const getStatusTagStyle = (service: any) => {
  const status = getStatusTag(service)
  const colorMap: Record<string, string> = {
    success: '#2e7d32',
    warning: '#f57c00',
    error: '#c62828',
    default: '#616161'
  }
  return {
    color: '#fff',
    backgroundColor: colorMap[status.type] || '#616161',
    borderColor: 'transparent'
  }
}

const runningServicesCount = computed(() =>
  data.value.services.filter(s => s.running && s.enabled).length
)

const runningMonitorsCount = computed(() =>
  data.value.monitors.filter(m => m.running).length
)
</script>

<style scoped>
.service-status-mobile {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

/* 卡片样式 */
.m-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
}

.m-card-header {
  margin-bottom: var(--m-spacing-md);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
}

.m-card-title {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
}

/* 服务列表 */
.service-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-sm) 0;
  border-bottom: 1px solid var(--app-border-light);
}

.service-item:last-child {
  border-bottom: none;
}

.service-info {
  flex: 1;
  min-width: 0;
}

.service-name {
  font-size: var(--m-text-sm);
  font-weight: 500;
  color: var(--text-primary);
  display: block;
}

.service-meta {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* 监控列表 */
.monitor-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}

.monitor-item {
  padding: var(--m-spacing-sm) 0;
  border-bottom: 1px solid var(--app-border-light);
}

.monitor-item:last-child {
  border-bottom: none;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-spacing-xs);
}

.monitor-tags {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-xs);
  flex-wrap: wrap;
  flex: 1;
}

.monitor-name {
  font-size: var(--m-text-sm);
  font-weight: 500;
  color: var(--text-primary);
}

.monitor-meta {
  font-size: var(--m-text-xs);
}

.meta-line {
  display: flex;
  gap: var(--m-spacing-xs);
  margin-bottom: 2px;
}

.meta-line .label {
  color: var(--text-tertiary);
}

.meta-line code {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--app-surface-inner);
  padding: 1px 4px;
  border-radius: 3px;
  word-break: break-all;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-spacing-md);
}

.stat-item {
  text-align: center;
  padding: var(--m-spacing-sm);
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* 规则列表 */
.rule-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.rule-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-sm) 0;
  border-bottom: 1px solid var(--app-border-light);
}

.rule-item:last-child {
  border-bottom: none;
}

.rule-name {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}
</style>
