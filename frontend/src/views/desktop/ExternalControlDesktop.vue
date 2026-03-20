<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NFormItem, 
  NDivider, NTag, NDataTable, NSwitch, NTabs, NTabPane, NList, NListItem, NThing,
  NModal, NTooltip
} from 'naive-ui'
import {
  ContentCopyOutlined as CopyIcon,
  RefreshOutlined as RefreshIcon,
  DescriptionOutlined as DocIcon
} from '@vicons/material'
import { useExternalControl } from '../../composables/views/useExternalControl'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { isDarkMode } from '../../store/themeStore'
import { computed } from 'vue'

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

// --- Log Details UI State ---
const showLogDetail = ref(false)
const currentLogDetail = ref('')

// --- API Docs Iframe Management ---
const docsIframe = ref<HTMLIFrameElement | null>(null)
let heightTimer: any = null

// 计算 API 文档 URL，根据当前主题模式传递 light/dark 参数
const docsUrl = computed(() => {
  const theme = isDarkMode.value ? 'dark' : 'light'
  return `${API_BASE}/api/system/docs?theme=${theme}&token=${config.value.external_token || ''}`
})

const adjustIframeHeight = () => {
  if (docsIframe.value && docsIframe.value.contentWindow) {
    try {
      const doc = docsIframe.value.contentWindow.document
      const height = Math.max(
        doc.body.scrollHeight,
        doc.documentElement.scrollHeight,
        doc.body.offsetHeight,
        doc.documentElement.offsetHeight
      )
      if (height > 0) {
        docsIframe.value.style.height = height + 'px'
      }
    } catch (e) {
      // 跨域或未加载时会跳过
    }
  }
}

onMounted(() => {
  fetchConfig()
  fetchLogs()
  heightTimer = setInterval(adjustIframeHeight, 1000)
  window.addEventListener('resize', adjustIframeHeight)
})

import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (heightTimer) clearInterval(heightTimer)
  window.removeEventListener('resize', adjustIframeHeight)
})

const logColumns = [
  { title: '请求时间', key: 'timestamp', width: 170, render: (row: any) => row.timestamp.replace('T', ' ').split('.')[0] },
  { 
    title: 'IP 地址', 
    key: 'ip', 
    width: 130, 
    render: (row: any) => {
      try {
        const details = JSON.parse(row.details || '{}')
        return h('span', { style: 'font-family: monospace; font-size: 12px' }, details.ip || 'unknown')
      } catch {
        return 'unknown'
      }
    } 
  },
  { title: '方法', key: 'action', width: 80, render: (row: any) => h(NTag, { size: 'small', round: true, bordered: false, style: { color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' } }, { default: () => row.action }) },
  { title: '接口路径', key: 'message', render: (row: any) => h('span', { style: 'font-family: monospace; font-size: 12px' }, row.message) },
  { 
    title: '详情', 
    key: 'details',
    width: 80,
    render: (row: any) => {
      if (!row.details) return '-'
      return h(NButton, {
        size: 'tiny',
        quaternary: true,
        circle: true,
        style: { 
          color: '#3B82F6 !important', 
          backgroundColor: 'transparent !important', 
          borderColor: 'transparent !important',
          border: 'none !important'
        },
        onClick: () => {
          try {
            const parsed = JSON.parse(row.details)
            currentLogDetail.value = JSON.stringify(parsed, null, 2)
          } catch {
            currentLogDetail.value = row.details
          }
          showLogDetail.value = true
        }
      }, { default: () => h(NIcon, null, { default: () => h(DocIcon) }) })
    }
  },
  { 
    title: '状态', 
    key: 'level', 
    width: 90,
    render: (row: any) => {
      const style = row.level === 'ERROR' 
        ? { color: '#fff', backgroundColor: '#c62828', borderColor: 'transparent' } 
        : (row.level === 'WARN' ? { color: '#fff', backgroundColor: '#f57c00', borderColor: 'transparent' } : { color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' })
      return h(NTag, { size: 'small', round: true, bordered: false, style }, { default: () => row.level })
    }
  }
]
</script>

<template>
  <div class="external-control-view">
    <div class="page-header">
      <div>
        <h1>外部控制</h1>
        <div class="subtitle">API 管理与集成设置</div>
      </div>
    </div>

    <n-card :bordered="false" class="main-card">
      <n-tabs
        v-model:value="activeTab"
        type="segment"
        animated
        class="custom-tabs"
      >
        <!-- 板块 1: API 密钥 -->
        <n-tab-pane name="keys" tab="API 密钥">
          <div class="tab-content">
            <div class="content-header">
              <h3>访问令牌管理</h3>
              <p>密钥用于身份验证，请妥善保管。在请求头中加入 <code>Authorization: Bearer [您的密钥]</code> 即可调用接口。</p>
            </div>

            <n-form-item label="当前生效的密钥" label-placement="top">
              <n-space vertical style="width: 100%" :size="12">
                <n-input 
                  v-model:value="config.external_token" 
                  type="password" 
                  show-password-on="click" 
                  placeholder="尚未生成密钥" 
                  readonly
                  size="large"
                  style="width: 100%; font-family: monospace; font-size: 13px;"
                >
                  <template #suffix>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button 
                          v-bind="getButtonStyle('icon')"
                          style="margin-right: -4px"
                          @click.stop="copyToClipboard(config.external_token)"
                        >
                          <template #icon><n-icon><CopyIcon /></n-icon></template>
                        </n-button>
                      </template>
                      复制访问密钥
                    </n-tooltip>
                  </template>
                </n-input>
                
                <n-button v-bind="getButtonStyle('primary')" size="large" @click="generateToken" style="width: 100%">
                  重新生成访问令牌 (Token)
                </n-button>
              </n-space>
            </n-form-item>

            <n-divider title-placement="left">Webhook 推送</n-divider>
            
            <n-alert type="success" title="CloudDrive2 联动" :show-icon="true">
              当您的云盘文件发生变动时，CD2 会通过此 Webhook 通知番剧管家立即刷新。必须要有CloudDrive2会员才可以使用此功能。
            </n-alert>
            
            <div class="webhook-section">
              <n-form-item label="回调 URL" label-placement="top">
                <n-input 
                  :value="webhookUrl" 
                  readonly 
                  size="large" 
                  style="width: 100%; font-family: monospace; font-size: 13px;"
                >
                  <template #suffix>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button 
                          v-bind="getButtonStyle('icon')"
                          style="margin-right: -4px"
                          @click.stop="copyToClipboard(webhookUrl)"
                        >
                          <template #icon><n-icon><CopyIcon /></n-icon></template>
                        </n-button>
                      </template>
                      复制回调链接
                    </n-tooltip>
                  </template>
                </n-input>
              </n-form-item>
            </div>

            <n-divider title-placement="left">Emby Webhook</n-divider>
            <n-alert title="Emby 配置指引" type="info" style="margin-bottom: 12px">
              在 Emby 设置的 <b>控制面板 -> Webhook</b> 中添加该地址，并确保以下设置：
              <ul style="margin: 8px 0 0 16px; padding: 0;">
                <li>发送格式：<b>JSON</b></li>
                <li>勾选事件：<b>媒体库 - 已添加新媒体</b></li>
                <li>勾选行为：<b>按剧集和专辑对通知进行分组</b></li>
              </ul>
            </n-alert>
            <div class="webhook-section">
              <n-form-item label="Emby 通知地址" label-placement="top">
                <n-input 
                  :value="embyWebhookUrl" 
                  readonly 
                  size="large" 
                  style="width: 100%; font-family: monospace; font-size: 13px;"
                >
                  <template #suffix>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <n-button 
                          v-bind="getButtonStyle('icon')"
                          style="margin-right: -4px"
                          @click.stop="copyToClipboard(embyWebhookUrl)"
                        >
                          <template #icon><n-icon><CopyIcon /></n-icon></template>
                        </n-button>
                      </template>
                      复制 Emby 回调链接
                    </n-tooltip>
                  </template>
                </n-input>
              </n-form-item>
            </div>
          </div>
        </n-tab-pane>

        <!-- 板块 2: 设置 -->
        <n-tab-pane name="settings" tab="设置">
          <div class="tab-content small-content">
            <div class="content-header">
              <h3>API 功能配置</h3>
              <p>配置外部接口的访问策略与安全限制。</p>
            </div>

            <n-list bordered>
              <n-list-item>
                <n-thing title="开放 API 访问" description="允许第三方客户端连接。关闭后所有外部 API 将失效。" />
                <template #suffix>
                  <n-switch v-model:value="config.enable_api" @update:value="saveConfig" />
                </template>
              </n-list-item>
              <n-list-item>
                <n-thing title="开启访问审计" description="在系统日志中详细记录每一次外部 API 的请求信息。" />
                <template #suffix>
                  <n-switch v-model:value="config.api_logging" @update:value="saveConfig" />
                </template>
              </n-list-item>
              <n-list-item>
                <n-thing title="开启 Swagger (OpenAPI)" description="启用基于 Swagger UI 的交互式文档界面。(/docs)" />
                <template #suffix>
                  <n-tag size="small" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">运行中</n-tag>
                </template>
              </n-list-item>
            </n-list>
          </div>
        </n-tab-pane>

        <!-- 板块 3: 访问日志 -->
        <n-tab-pane name="logs" tab="访问日志">
          <div class="tab-content full-width">
            <div class="table-actions">
              <n-button v-bind="getButtonStyle('secondary')" @click="fetchLogs" :loading="logLoading">
                刷新审计日志
              </n-button>
            </div>
            
            <n-data-table
              remote
              :loading="logLoading"
              :columns="logColumns"
              :data="logs"
              :pagination="pagination"
              :max-height="500"
            />
          </div>
        </n-tab-pane>

        <!-- 板块 4: API 文档 -->
        <n-tab-pane name="docs" tab="API 文档">
          <div class="tab-content docs-container">
            <div class="docs-wrapper">
              <iframe
                v-if="config.external_token"
                ref="docsIframe"
                :src="docsUrl"
                class="docs-iframe"
                frameborder="0"
                scrolling="no"
                @load="adjustIframeHeight"
              ></iframe>
              <div v-else class="docs-loading" style="display: flex; align-items: center; justify-content: center; height: 200px; color: var(--text-tertiary);">
                <n-spin size="small" /> <span style="margin-left: 8px;">加载 API 文档...</span>
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-modal v-model:show="showLogDetail" preset="card" title="请求详情" style="width: 600px">
      <div style="background: var(--bg-surface); padding: 12px; border-radius: 8px">
        <pre style="margin: 0; white-space: pre-wrap; font-family: monospace; font-size: 13px">{{ currentLogDetail }}</pre>
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showLogDetail = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.external-control-view { width: 100%; height: 100%; display: flex; flex-direction: column; }
.page-header { margin-bottom: 20px; flex-shrink: 0; }
.page-header h1 { margin: 0; font-size: 26px; font-weight: 800; }
.page-header .subtitle { color: var(--text-tertiary); font-size: 14px; }

.main-card {
  border-radius: 12px;
  background-color: var(--app-surface-card);
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-card-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0 !important;
}

:deep(.n-tabs) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-nav) {
  padding: 4px;
  background: transparent !important;
  border-radius: var(--button-border-radius, 8px);
  margin: 16px 20px 0;
}

/* Tabs 样式已移至 global.css 统一管理 */

:deep(.n-tabs-pane-wrapper) {
  flex: 1;
}

:deep(.n-tab-pane) {
  height: 100%;
}

.tab-content { padding: 24px; max-width: 1200px; }
.tab-content.small-content { max-width: 800px; }
.tab-content.full-width { padding: 24px; max-width: 100%; }

.content-header { margin-bottom: 24px; }
.content-header h3 { margin: 0 0 8px 0; font-size: 18px; }
.content-header p { margin: 0; color: var(--text-tertiary); font-size: 13px; line-height: 1.6; }

.webhook-section { margin-top: 20px; }
.table-actions { margin-bottom: 16px; display: flex; justify-content: flex-end; }

.docs-container {
  padding: 0;
  max-width: 100%;
}

.docs-wrapper {
  width: 100%;
  min-height: 800px;
  background-color: var(--sidebar-bg-color);
  border-radius: 0 0 12px 12px;
  overflow: hidden;
}

.docs-iframe {
  width: 100%;
  height: 800px;
  display: block;
  border: none;
  background: var(--bg-primary);
}
</style>
