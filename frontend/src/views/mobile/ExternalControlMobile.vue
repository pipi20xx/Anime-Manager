<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NFormItem, 
  NDivider, NTag, NSwitch, NTabs, NTabPane, NList, NListItem, NThing,
  NDrawer, NDrawerContent, NSpin
} from 'naive-ui'
import {
  ContentCopyOutlined as CopyIcon,
  RefreshOutlined as RefreshIcon,
  HistoryOutlined as LogIcon,
  SettingsOutlined as SettingIcon,
  DescriptionOutlined as DocIcon,
  VpnKeyOutlined as KeyIcon,
  InfoOutlined as DetailIcon
} from '@vicons/material'
import { useExternalControl } from '../../composables/views/useExternalControl'

const {
  API_BASE,
  webhookUrl,
  embyWebhookUrl,
  config,
  logs,
  pagination,
  loading,
  logLoading,
  fetchConfig,
  fetchLogs,
  saveConfig,
  generateToken,
  copyToClipboard
} = useExternalControl()

const activeTab = ref('keys')
const showLogDetail = ref(false)
const currentLogDetail = ref('')

// Mobile specific log rendering
const formatTime = (ts: string) => ts.replace('T', ' ').split('.')[0]

const openLogDetail = (row: any) => {
  try {
    const parsed = JSON.parse(row.details || '{}')
    currentLogDetail.value = JSON.stringify(parsed, null, 2)
  } catch {
    currentLogDetail.value = row.details || 'No details'
  }
  showLogDetail.value = true
}

onMounted(() => {
  fetchConfig()
  fetchLogs()
})
</script>

<template>
  <div class="mobile-container">
    <div class="mobile-header">
      <h2>外部控制</h2>
    </div>

    <n-tabs 
      v-model:value="activeTab" 
      type="line" 
      animated
      pane-class="mobile-tab-pane"
      justify-content="space-evenly"
    >
      <!-- 密钥 -->
      <n-tab-pane name="keys" tab="密钥">
        <template #tab><n-icon size="20"><KeyIcon /></n-icon></template>
        <div class="content-body">
          <n-card :bordered="false" title="访问令牌" size="small">
            <n-input 
              v-model:value="config.external_token" 
              type="password" 
              show-password-on="click" 
              readonly 
              placeholder="未生成"
            >
              <template #suffix>
                 <n-button quaternary circle size="small" @click="copyToClipboard(config.external_token)">
                   <n-icon><CopyIcon /></n-icon>
                 </n-button>
              </template>
            </n-input>
            <n-button dashed block style="margin-top: 10px" @click="generateToken">
              <template #icon><n-icon><RefreshIcon /></n-icon></template>
              重置令牌
            </n-button>
          </n-card>

          <n-card :bordered="false" title="CD2 Webhook" size="small" style="margin-top: 12px">
             <div class="info-text">云盘文件变动通知</div>
             <n-input :value="webhookUrl" readonly size="small">
                <template #suffix>
                 <n-button quaternary circle size="small" @click="copyToClipboard(webhookUrl)">
                   <n-icon><CopyIcon /></n-icon>
                 </n-button>
              </template>
             </n-input>
          </n-card>

          <n-card :bordered="false" title="Emby Webhook" size="small" style="margin-top: 12px">
             <div class="info-text">Emby 媒体库通知</div>
             <n-input :value="embyWebhookUrl" readonly size="small">
                <template #suffix>
                 <n-button quaternary circle size="small" @click="copyToClipboard(embyWebhookUrl)">
                   <n-icon><CopyIcon /></n-icon>
                 </n-button>
              </template>
             </n-input>
          </n-card>
        </div>
      </n-tab-pane>

      <!-- 设置 -->
      <n-tab-pane name="settings" tab="设置">
        <template #tab><n-icon size="20"><SettingIcon /></n-icon></template>
        <div class="content-body">
          <n-list clickable>
            <n-list-item>
              <div class="setting-item">
                <div class="setting-label">开放 API</div>
                <n-switch v-model:value="config.enable_api" @update:value="saveConfig" />
              </div>
            </n-list-item>
            <n-list-item>
              <div class="setting-item">
                <div class="setting-label">强制身份认证</div>
                <n-switch v-model:value="config.api_auth_required" @update:value="saveConfig" />
              </div>
            </n-list-item>
            <n-list-item>
              <div class="setting-item">
                <div class="setting-label">开启审计日志</div>
                <n-switch v-model:value="config.api_logging" @update:value="saveConfig" />
              </div>
            </n-list-item>
            <n-list-item>
              <div class="setting-item">
                <div class="setting-label">Swagger UI</div>
                <n-tag type="success" size="small">运行中</n-tag>
              </div>
            </n-list-item>
          </n-list>
        </div>
      </n-tab-pane>

      <!-- 日志 -->
      <n-tab-pane name="logs" tab="日志">
        <template #tab><n-icon size="20"><LogIcon /></n-icon></template>
        <div class="content-body no-pad">
          <div class="refresh-bar">
             <n-button size="small" dashed block @click="fetchLogs" :loading="logLoading">刷新日志</n-button>
          </div>
          <n-spin :show="logLoading">
            <n-list>
              <n-list-item v-for="log in logs" :key="log.id" @click="openLogDetail(log)">
                <n-thing>
                  <template #header>
                    <n-tag size="small" :type="log.level === 'ERROR' ? 'error' : (log.level === 'WARN' ? 'warning' : 'success')" bordered={false}>
                      {{ log.action }}
                    </n-tag>
                    <span style="margin-left: 8px; font-size: 13px; font-weight: bold">{{ log.message }}</span>
                  </template>
                  <template #description>
                    <div style="font-size: 12px; color: #888">
                      {{ formatTime(log.timestamp) }}
                    </div>
                  </template>
                  <template #suffix>
                    <n-button quaternary circle size="small" @click.stop="openLogDetail(log)">
                       <n-icon><DetailIcon /></n-icon>
                    </n-button>
                  </template>
                </n-thing>
              </n-list-item>
            </n-list>
          </n-spin>
        </div>
      </n-tab-pane>

      <!-- 文档 -->
      <n-tab-pane name="docs" tab="文档">
        <template #tab><n-icon size="20"><DocIcon /></n-icon></template>
         <div class="content-body no-pad docs-body">
            <iframe 
              :key="config.external_token"
              :src="`${API_BASE}/api/system/docs?theme=cyan&token=${config.external_token}`" 
              class="mobile-iframe"
            ></iframe>
         </div>
      </n-tab-pane>
    </n-tabs>

    <n-drawer v-model:show="showLogDetail" placement="bottom" height="60vh">
      <n-drawer-content title="日志详情">
        <pre class="log-detail-pre">{{ currentLogDetail }}</pre>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.mobile-container {
  padding-bottom: 80px; /* Space for bottom nav */
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--app-background);
}

.mobile-header {
  padding: 16px 16px 0 16px;
}
.mobile-header h2 { margin: 0; font-size: 20px; }

:deep(.n-tabs-nav) {
  padding: 0 16px; 
}

.content-body {
  padding: 16px;
  overflow-y: auto;
  height: calc(100vh - 120px);
}
.content-body.no-pad { padding: 0; }

.info-text { font-size: 12px; color: #666; margin-bottom: 4px; }

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}
.setting-label { font-size: 15px; font-weight: 500; }

.refresh-bar { padding: 8px 16px; background: var(--app-surface-color); position: sticky; top: 0; z-index: 10; }

.log-detail-pre {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 10px;
  border-radius: 8px;
  color: #333;
}
/* Dark mode adaptation for pre block */
@media (prefers-color-scheme: dark) {
  .log-detail-pre { background: #333; color: #eee; }
}

.docs-body { height: calc(100vh - 100px); }
.mobile-iframe { width: 100%; height: 100%; border: none; }
</style>
