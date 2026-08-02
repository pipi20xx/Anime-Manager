<script setup lang="ts">
/**
 * ExternalControlView — 外部控制
 *
 * 标签页（与旧前端一致）:
 * 1. API 密钥 — 访问令牌管理、Webhook 推送、Emby Webhook
 * 2. 设置 — API 功能开关、访问审计、Swagger
 * 3. 访问日志 — API 审计日志表格
 * 4. API 文档 — 内嵌 Swagger UI
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { configApi, systemApi } from '@/api'
import { useNotification, useClipboard } from '@/composables'
import { useThemeStore } from '@/stores'

defineOptions({ name: 'ExternalControlView' })

const { success, error: showError } = useNotification()
const { copy } = useClipboard()
const themeStore = useThemeStore()

const activeTab = ref('keys')
const loading = ref(false)
const logLoading = ref(false)
const showToken = ref(false)
const showLogDetail = ref(false)
const currentLogDetail = ref('')

// 配置状态
const config = ref<any>({
  external_token: '',
  enable_api: true,
  api_logging: true,
})

// 审计日志
const logs = ref<any[]>([])
const page = ref(1)
const itemsPerPage = ref(15)

// API 文档 iframe
const docsIframe = ref<HTMLIFrameElement | null>(null)
let heightTimer: ReturnType<typeof setInterval> | null = null

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || window.location.origin
const webhookUrl = computed(() => `${window.location.origin}/api/webhook/cd2/file_notify`)
const embyWebhookUrl = computed(() => `${window.location.origin}/api/webhook/emby`)

const docsUrl = computed(() => {
  const theme = themeStore.isDarkMode ? 'dark' : 'light'
  return `${API_BASE}/api/system/docs?theme=${theme}&token=${config.value.external_token || ''}`
})

const logHeaders = [
  { title: '请求时间', key: 'timestamp', width: 180 },
  { title: 'IP 地址', key: 'ip', width: 140 },
  { title: '方法', key: 'action', width: 90 },
  { title: '接口路径', key: 'message' },
  { title: '详情', key: 'details', width: 80, sortable: false },
  { title: '状态', key: 'level', width: 100 },
]

function formatTimestamp(ts: string): string {
  if (!ts) return '-'
  return ts.replace('T', ' ').split('.')[0]
}

function getIp(row: any): string {
  try {
    const details = JSON.parse(row.details || '{}')
    return details.ip || 'unknown'
  } catch {
    return 'unknown'
  }
}

function getLevelColor(level: string): string {
  if (level === 'ERROR') return 'error'
  if (level === 'WARN') return 'warning'
  return 'success'
}

function openLogDetail(row: any) {
  if (!row.details) return
  try {
    const parsed = JSON.parse(row.details)
    currentLogDetail.value = JSON.stringify(parsed, null, 2)
  } catch {
    currentLogDetail.value = row.details
  }
  showLogDetail.value = true
}

async function fetchConfig() {
  loading.value = true
  try {
    const data = await configApi.getConfig()
    config.value = {
      external_token: data.external_token || '',
      enable_api: data.enable_api !== undefined ? data.enable_api : true,
      api_logging: data.api_logging !== undefined ? data.api_logging : true,
    }
    if (config.value.external_token) {
      localStorage.setItem('apm_external_token', config.value.external_token)
    }
  } catch {
    showError('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function fetchLogs() {
  logLoading.value = true
  try {
    const data = await systemApi.getLogs({
      module: 'API',
      limit: itemsPerPage.value,
      offset: (page.value - 1) * itemsPerPage.value,
    })
    logs.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('获取 API 日志失败', e)
  } finally {
    logLoading.value = false
  }
}

async function saveConfig() {
  try {
    const fullConfig = await configApi.getConfig()
    Object.assign(fullConfig, config.value)
    await configApi.saveConfig(fullConfig)
    success('配置已更新')
  } catch {
    showError('保存失败')
  }
}

function generateToken() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let token = 'ak-'
  for (let i = 0; i < 28; i++) {
    token += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  config.value.external_token = token
  localStorage.setItem('apm_external_token', token)
  saveConfig()
}

function adjustIframeHeight() {
  if (docsIframe.value && docsIframe.value.contentWindow) {
    try {
      const doc = docsIframe.value.contentWindow.document
      const height = Math.max(
        doc.body.scrollHeight,
        doc.documentElement.scrollHeight,
        doc.body.offsetHeight,
        doc.documentElement.offsetHeight,
      )
      if (height > 0) {
        docsIframe.value.style.height = height + 'px'
      }
    } catch {
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

onUnmounted(() => {
  if (heightTimer) clearInterval(heightTimer)
  window.removeEventListener('resize', adjustIframeHeight)
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <h1 class="text-h5 font-weight-bold">外部控制</h1>
      <div class="text-body-2 text-medium-emphasis mt-1">API 管理与集成设置</div>
    </div>

    <div class="sticky-tabs">
      <v-tabs v-model="activeTab" color="primary">
        <v-tab value="keys">
          <v-icon start size="18">mdi-key-outline</v-icon>
          API 密钥
        </v-tab>
        <v-tab value="settings">
          <v-icon start size="18">mdi-tune-vertical</v-icon>
          设置
        </v-tab>
        <v-tab value="logs">
          <v-icon start size="18">mdi-file-document-outline</v-icon>
          访问日志
        </v-tab>
        <v-tab value="docs">
          <v-icon start size="18">mdi-book-open-variant</v-icon>
          API 文档
        </v-tab>
      </v-tabs>
    </div>

    <v-card class="glass-card" rounded="xl">
      <v-window v-model="activeTab">
        <!-- 板块 1: API 密钥 -->
        <v-window-item value="keys" class="pa-6">
          <!-- 访问令牌管理 -->
          <div class="mb-6">
            <h3 class="text-subtitle-1 font-weight-bold mb-2">访问令牌管理</h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              密钥用于身份验证，请妥善保管。在请求头中加入
              <code>Authorization: Bearer [您的密钥]</code> 即可调用接口。
            </p>
            <v-text-field
              v-model="config.external_token"
              :type="showToken ? 'text' : 'password'"
              label="当前生效的密钥"
              placeholder="尚未生成密钥"
              readonly
              variant="outlined"
              density="comfortable"
              hide-details
            >
              <template #append-inner>
                <v-tooltip text="显示/隐藏密钥">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      variant="text"
                      size="small"
                      :icon="showToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                      @click="showToken = !showToken"
                    />
                  </template>
                </v-tooltip>
                <v-tooltip text="复制访问密钥">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      variant="text"
                      size="small"
                      icon="mdi-content-copy"
                      @click="copy(config.external_token, '已复制访问密钥')"
                    />
                  </template>
                </v-tooltip>
              </template>
            </v-text-field>
            <v-btn
              color="primary"
              size="large"
              block
              class="mt-3"
              @click="generateToken"
            >
              <v-icon start>mdi-refresh</v-icon>
              重新生成访问令牌 (Token)
            </v-btn>
          </div>

          <v-divider class="my-6" />

          <!-- CD2 Webhook -->
          <div class="mb-6">
            <h3 class="text-subtitle-1 font-weight-bold mb-2">Webhook 推送</h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              当您的云盘文件发生变动时，CD2 会通过此 Webhook 通知番剧管家立即刷新。
              必须要有 CloudDrive2 会员才可以使用此功能。
            </p>
            <v-text-field
              :model-value="webhookUrl"
              label="回调 URL"
              readonly
              variant="outlined"
              density="comfortable"
              hide-details
            >
              <template #append-inner>
                <v-tooltip text="复制回调链接">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      variant="text"
                      size="small"
                      icon="mdi-content-copy"
                      @click="copy(webhookUrl, '已复制回调链接')"
                    />
                  </template>
                </v-tooltip>
              </template>
            </v-text-field>
          </div>

          <v-divider class="my-6" />

          <!-- Emby Webhook -->
          <div>
            <h3 class="text-subtitle-1 font-weight-bold mb-2">Emby Webhook</h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              在 Emby 设置的 <code>控制面板 -> Webhook</code> 中添加该地址，并确保发送格式为
              <b>JSON</b>、勾选事件 <b>媒体库 - 已添加新媒体</b> 与行为
              <b>按剧集和专辑对通知进行分组</b>。
            </p>
            <v-text-field
              :model-value="embyWebhookUrl"
              label="Emby 通知地址"
              readonly
              variant="outlined"
              density="comfortable"
              hide-details
            >
              <template #append-inner>
                <v-tooltip text="复制 Emby 回调链接">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      variant="text"
                      size="small"
                      icon="mdi-content-copy"
                      @click="copy(embyWebhookUrl, '已复制 Emby 回调链接')"
                    />
                  </template>
                </v-tooltip>
              </template>
            </v-text-field>
          </div>
        </v-window-item>

        <!-- 板块 2: 设置 -->
        <v-window-item value="settings" class="pa-6">
          <div style="max-width: 800px">
            <h3 class="text-subtitle-1 font-weight-bold mb-2">API 功能配置</h3>
            <p class="text-body-2 text-medium-emphasis mb-6">
              配置外部接口的访问策略与安全限制。
            </p>

            <v-list class="bg-transparent rounded-lg" border>
              <v-list-item>
                <div class="d-flex align-center w-100">
                  <div class="flex-grow-1">
                    <div class="text-body-1 font-weight-medium">开放 API 访问</div>
                    <div class="text-caption text-medium-emphasis">
                      允许第三方客户端连接。关闭后所有外部 API 将失效。
                    </div>
                  </div>
                  <v-switch
                    v-model="config.enable_api"
                    color="primary"
                    hide-details
                    density="compact"
                    @update:model-value="saveConfig"
                  />
                </div>
              </v-list-item>
              <v-divider />
              <v-list-item>
                <div class="d-flex align-center w-100">
                  <div class="flex-grow-1">
                    <div class="text-body-1 font-weight-medium">开启访问审计</div>
                    <div class="text-caption text-medium-emphasis">
                      在系统日志中详细记录每一次外部 API 的请求信息。
                    </div>
                  </div>
                  <v-switch
                    v-model="config.api_logging"
                    color="primary"
                    hide-details
                    density="compact"
                    @update:model-value="saveConfig"
                  />
                </div>
              </v-list-item>
              <v-divider />
              <v-list-item>
                <div class="d-flex align-center w-100">
                  <div class="flex-grow-1">
                    <div class="text-body-1 font-weight-medium">开启 Swagger (OpenAPI)</div>
                    <div class="text-caption text-medium-emphasis">
                      启用基于 Swagger UI 的交互式文档界面。(/docs)
                    </div>
                  </div>
                  <v-chip size="small" color="success" variant="tonal" label>运行中</v-chip>
                </div>
              </v-list-item>
            </v-list>
          </div>
        </v-window-item>

        <!-- 板块 3: 访问日志 -->
        <v-window-item value="logs" class="pa-6">
          <div class="d-flex justify-end mb-4">
            <v-btn variant="tonal" color="primary" :loading="logLoading" @click="fetchLogs">
              <v-icon start>mdi-refresh</v-icon>
              刷新审计日志
            </v-btn>
          </div>

          <v-data-table
            :headers="logHeaders"
            :items="logs"
            :loading="logLoading"
            :items-per-page="itemsPerPage"
            :page="page"
            density="compact"
            class="bg-transparent"
            @update:page="page = $event; fetchLogs()"
          >
            <template #item.timestamp="{ item }">
              <span class="text-caption font-monospace">{{ formatTimestamp(item.timestamp) }}</span>
            </template>
            <template #item.ip="{ item }">
              <span class="text-caption font-monospace">{{ getIp(item) }}</span>
            </template>
            <template #item.action="{ item }">
              <v-chip size="x-small" color="info" variant="tonal" label>{{ item.action }}</v-chip>
            </template>
            <template #item.message="{ item }">
              <span class="text-caption font-monospace">{{ item.message }}</span>
            </template>
            <template #item.details="{ item }">
              <v-btn
                v-if="item.details"
                variant="text"
                size="x-small"
                icon="mdi-file-document-outline"
                color="primary"
                @click="openLogDetail(item)"
              />
              <span v-else class="text-medium-emphasis">-</span>
            </template>
            <template #item.level="{ item }">
              <v-chip size="x-small" :color="getLevelColor(item.level)" variant="tonal" label>
                {{ item.level }}
              </v-chip>
            </template>
          </v-data-table>
        </v-window-item>

        <!-- 板块 4: API 文档 -->
        <v-window-item value="docs">
          <div v-if="config.external_token" class="pa-2">
            <iframe
              ref="docsIframe"
              :src="docsUrl"
              class="docs-iframe"
              frameborder="0"
              scrolling="no"
              @load="adjustIframeHeight"
            />
          </div>
          <div v-else class="d-flex align-center justify-center pa-12">
            <v-progress-circular indeterminate size="small" class="mr-3" />
            <span class="text-medium-emphasis">请先生成访问令牌以加载 API 文档...</span>
          </div>
        </v-window-item>
      </v-window>
    </v-card>

    <!-- 日志详情弹窗 -->
    <v-dialog v-model="showLogDetail" max-width="600">
      <v-card rounded="xl">
<v-card-title class="d-flex align-center">
<v-icon start color="primary">mdi-file-document-outline</v-icon>
请求详情
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showLogDetail = false" />
</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <pre class="log-detail-pre">{{ currentLogDetail }}</pre>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showLogDetail = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.docs-iframe {
  width: 100%;
  min-height: 800px;
  display: block;
  border: none;
  border-radius: 12px;
}

.log-detail-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: rgba(var(--v-theme-surface-variant), 0.15);
  padding: 16px;
  border-radius: 8px;
}

.font-monospace {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
}
</style>
