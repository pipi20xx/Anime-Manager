<template>
  <div class="service-status-tab">
    <n-space vertical size="large">
      <n-card size="small" embedded>
        <template #header>
          <div class="section-header">
            <span>系统服务</span>
            <n-tag size="small" :bordered="false" type="info">{{ runningServicesCount }} / {{ data.services.length }} 运行中</n-tag>
          </div>
        </template>
        <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen">
          <n-gi v-for="service in data.services" :key="service.id">
            <div class="service-card" :class="{ 'is-running': service.running && service.enabled, 'is-stopped': !service.enabled }">
              <div class="service-header">
                <span class="service-name">{{ service.name }}</span>
                <n-tag :type="getStatusTag(service).type" size="small" round>
                  {{ getStatusTag(service).text }}
                </n-tag>
              </div>
              <div class="service-meta">
                <div class="meta-item">
                  <span class="label">间隔</span>
                  <span class="value">{{ service.interval }}</span>
                </div>
                <div class="meta-item" v-if="service.next_run">
                  <span class="label">下次执行</span>
                  <span class="value">{{ formatNextRun(service.next_run) }}</span>
                </div>
              </div>
              <div class="service-desc">{{ service.description }}</div>
            </div>
          </n-gi>
        </n-grid>
      </n-card>

      <n-card size="small" embedded v-if="data.monitors.length > 0">
        <template #header>
          <div class="section-header">
            <span>文件监控任务</span>
            <n-tag size="small" :bordered="false" type="warning">{{ runningMonitorsCount }} / {{ data.monitors.length }} 活跃</n-tag>
          </div>
        </template>
        <n-grid :cols="1" :x-gap="16" :y-gap="12">
          <n-gi v-for="monitor in data.monitors" :key="monitor.id">
            <div class="monitor-card" :class="{ 'is-running': monitor.running, 'is-stopped': !monitor.enabled }">
              <div class="monitor-header">
                <div class="monitor-info">
                  <n-tag :type="monitor.type === 'organize' ? 'info' : 'success'" size="small" :bordered="false">
                    {{ monitor.type === 'organize' ? '整理' : 'STRM' }}
                  </n-tag>
                  <span class="monitor-name">{{ monitor.name }}</span>
                  <n-tag :type="monitor.running ? 'success' : 'default'" size="tiny" round>
                    {{ monitor.mode }}
                  </n-tag>
                  <n-tag v-if="monitor.type === 'strm' && monitor.webhook_enabled" type="warning" size="tiny" round>
                    接受联动
                  </n-tag>
                  <n-tag v-if="monitor.type === 'organize' && monitor.check_emby_exists" type="info" size="tiny" round>
                    Emby检查
                  </n-tag>
                  <n-tag v-if="monitor.type === 'organize' && monitor.calculate_hash" type="error" size="tiny" round>
                    哈希计算
                  </n-tag>
                </div>
                <n-tag :type="getStatusTag(monitor).type" size="small" round>
                  {{ getStatusTag(monitor).text }}
                </n-tag>
              </div>
              <div class="monitor-paths">
                <div class="path-item">
                  <span class="label">源目录</span>
                  <code class="value">{{ monitor.source_dir || '-' }}</code>
                </div>
                <div class="path-item">
                  <span class="label">目标</span>
                  <code class="value">{{ monitor.target_dir || '-' }}</code>
                </div>
              </div>
              <div class="monitor-queue" v-if="monitor.running && monitor.queue_size > 0">
                <span>队列中: {{ monitor.queue_size }} 个文件待处理</span>
              </div>
            </div>
          </n-gi>
        </n-grid>
      </n-card>

      <n-card size="small" embedded>
        <template #header>
          <div class="section-header">
            <span>运行时统计</span>
          </div>
        </template>
        <n-grid :cols="3" :x-gap="16">
          <n-gi>
            <n-statistic label="文件观察器" :value="data.observers_count">
              <template #suffix>
                <n-text depth="3" style="font-size: 14px"> 个</n-text>
              </template>
            </n-statistic>
          </n-gi>
          <n-gi>
            <n-statistic label="工作线程" :value="data.workers_count">
              <template #suffix>
                <n-text depth="3" style="font-size: 14px"> 个</n-text>
              </template>
            </n-statistic>
          </n-gi>
          <n-gi>
            <n-statistic label="任务队列" :value="data.queues_count">
              <template #suffix>
                <n-text depth="3" style="font-size: 14px"> 个</n-text>
              </template>
            </n-statistic>
          </n-gi>
        </n-grid>
      </n-card>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  NSpace, NCard, NGrid, NGi, NTag, NStatistic, NText
} from 'naive-ui'
import { useServiceStatus } from '../../composables/views/useServiceStatus'

const { data, formatNextRun, getStatusTag } = useServiceStatus()

const runningServicesCount = computed(() => 
  data.value.services.filter(s => s.running && s.enabled).length
)

const runningMonitorsCount = computed(() => 
  data.value.monitors.filter(m => m.running).length
)
</script>

<style scoped>
.service-status-tab {
  padding-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.service-card {
  background: var(--bg-surface);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s ease;
}

.service-card.is-running {
  border-color: var(--color-success-border);
  background: var(--color-success-bg);
}

.service-card.is-stopped {
  opacity: 0.6;
}

.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.service-name {
  font-weight: 500;
  font-size: 14px;
}

.service-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 6px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.meta-item .label {
  color: var(--text-tertiary);
}

.meta-item .value {
  color: var(--text-secondary);
  font-family: monospace;
}

.service-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}

.monitor-card {
  background: var(--bg-surface);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s ease;
}

.monitor-card.is-running {
  border-color: var(--color-warning-border);
  background: var(--color-warning-bg);
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.monitor-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.monitor-name {
  font-weight: 500;
  font-size: 14px;
}

.monitor-paths {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.path-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.path-item .label {
  color: var(--text-tertiary);
  width: 48px;
  flex-shrink: 0;
}

.path-item .value {
  color: var(--text-muted);
  font-family: monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.monitor-queue {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 12px;
  color: var(--color-success);
}
</style>
