<template>
  <div class="service-status-mobile">
    <n-space vertical size="small">
      <n-card size="small" :bordered="false">
        <template #header>
          <div class="section-title">
            <span>系统服务</span>
            <n-tag size="tiny" :bordered="false" type="info">{{ runningServicesCount }}/{{ data.services.length }}</n-tag>
          </div>
        </template>
        <n-list size="small">
          <n-list-item v-for="service in data.services" :key="service.id">
            <n-thing>
              <template #header>
                <div class="service-row">
                  <span class="service-name">{{ service.name }}</span>
                  <n-tag :type="getStatusTag(service).type" size="tiny" round>
                    {{ getStatusTag(service).text }}
                  </n-tag>
                </div>
              </template>
              <template #description>
                <div class="service-meta">
                  <span>{{ service.interval }}</span>
                  <span v-if="service.next_run">· {{ formatNextRun(service.next_run) }}</span>
                </div>
              </template>
            </n-thing>
          </n-list-item>
        </n-list>
      </n-card>

      <n-card size="small" :bordered="false" v-if="data.monitors.length > 0">
        <template #header>
          <div class="section-title">
            <span>文件监控</span>
            <n-tag size="tiny" :bordered="false" type="warning">{{ runningMonitorsCount }}/{{ data.monitors.length }}</n-tag>
          </div>
        </template>
        <n-list size="small">
          <n-list-item v-for="monitor in data.monitors" :key="monitor.id">
            <n-thing>
              <template #header>
                <div class="monitor-row">
                  <n-space align="center" :size="6">
                    <n-tag :type="monitor.type === 'organize' ? 'info' : 'success'" size="tiny" :bordered="false">
                      {{ monitor.type === 'organize' ? '整理' : 'STRM' }}
                    </n-tag>
                    <span class="monitor-name">{{ monitor.name }}</span>
                    <n-tag v-if="monitor.type === 'strm' && monitor.webhook_enabled" type="warning" size="tiny" round>
                      接受联动
                    </n-tag>
                    <n-tag v-if="monitor.type === 'organize' && monitor.check_emby_exists" type="info" size="tiny" round>
                      Emby检查
                    </n-tag>
                    <n-tag v-if="monitor.type === 'organize' && monitor.calculate_hash" type="error" size="tiny" round>
                      哈希计算
                    </n-tag>
                  </n-space>
                  <n-tag :type="getStatusTag(monitor).type" size="tiny" round>
                    {{ getStatusTag(monitor).text }}
                  </n-tag>
                </div>
              </template>
              <template #description>
                <div class="monitor-meta">
                  <div class="meta-line">
                    <span class="label">源:</span>
                    <code>{{ monitor.source_dir || '-' }}</code>
                  </div>
                  <div class="meta-line" v-if="monitor.running && monitor.queue_size > 0">
                    <n-text type="success">队列: {{ monitor.queue_size }} 待处理</n-text>
                  </div>
                </div>
              </template>
            </n-thing>
          </n-list-item>
        </n-list>
      </n-card>

      <n-card size="small" :bordered="false">
        <template #header>
          <div class="section-title">
            <span>运行时</span>
          </div>
        </template>
        <n-grid :cols="3" :x-gap="8">
          <n-gi>
            <div class="stat-item">
              <div class="stat-value">{{ data.observers_count }}</div>
              <div class="stat-label">观察器</div>
            </div>
          </n-gi>
          <n-gi>
            <div class="stat-item">
              <div class="stat-value">{{ data.workers_count }}</div>
              <div class="stat-label">工作线程</div>
            </div>
          </n-gi>
          <n-gi>
            <div class="stat-item">
              <div class="stat-value">{{ data.queues_count }}</div>
              <div class="stat-label">队列</div>
            </div>
          </n-gi>
        </n-grid>
      </n-card>

      <n-card size="small" :bordered="false">
        <template #header>
          <div class="section-title">
            <span>规则统计</span>
          </div>
        </template>
        <n-list size="small">
          <n-list-item>
            <div class="rule-row">
              <span class="rule-name">自定义识别词</span>
              <n-space :size="4">
                <n-tag type="info" size="tiny">本地 {{ data.rules.custom_noise.local }}</n-tag>
                <n-tag type="success" size="tiny">远程 {{ data.rules.custom_noise.remote }}</n-tag>
              </n-space>
            </div>
          </n-list-item>
          <n-list-item>
            <div class="rule-row">
              <span class="rule-name">自定义制作组</span>
              <n-space :size="4">
                <n-tag type="info" size="tiny">本地 {{ data.rules.custom_groups.local }}</n-tag>
                <n-tag type="success" size="tiny">远程 {{ data.rules.custom_groups.remote }}</n-tag>
                <n-tag type="warning" size="tiny">内置 {{ data.rules.custom_groups.builtin || 0 }}</n-tag>
              </n-space>
            </div>
          </n-list-item>
          <n-list-item>
            <div class="rule-row">
              <span class="rule-name">自定义渲染词</span>
              <n-space :size="4">
                <n-tag type="info" size="tiny">本地 {{ data.rules.custom_render.local }}</n-tag>
                <n-tag type="success" size="tiny">远程 {{ data.rules.custom_render.remote }}</n-tag>
              </n-space>
            </div>
          </n-list-item>
          <n-list-item>
            <div class="rule-row">
              <span class="rule-name">特权规则</span>
              <n-space :size="4">
                <n-tag type="info" size="tiny">本地 {{ data.rules.privileged.local }}</n-tag>
                <n-tag type="success" size="tiny">远程 {{ data.rules.privileged.remote }}</n-tag>
              </n-space>
            </div>
          </n-list-item>
        </n-list>
      </n-card>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  NSpace, NCard, NGrid, NGi, NTag, NList, NListItem, NThing, NText
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
.service-status-mobile {
  padding: 8px 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.service-row, .monitor-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.service-name, .monitor-name {
  font-size: 13px;
  font-weight: 500;
}

.service-meta {
  font-size: 11px;
  color: var(--text-tertiary);
}

.monitor-meta {
  font-size: 11px;
}

.meta-line {
  display: flex;
  gap: 4px;
  margin-bottom: 2px;
}

.meta-line .label {
  color: var(--text-tertiary);
}

.meta-line code {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-surface);
  padding: 1px 4px;
  border-radius: 3px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 20px;
  font-weight: bold;
  color: var(--n-primary-color);
}

.stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.rule-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.rule-name {
  font-size: 13px;
  font-weight: 500;
}
</style>
