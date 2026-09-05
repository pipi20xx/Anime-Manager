<script setup lang="ts">
/**
 * BasicConfigTab — 基础配置
 *
 * 包含: TMDB、Bangumi、SYTMDB、识别偏好、Jackett、Emby、Telegram通知、代理设置、自动化设置
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { configApi, systemApi, clientsApi } from '@/api'
import { useNotification } from '@/composables'
import { PasswordInput } from '@/components/common'

defineOptions({ name: 'BasicConfigTab' })

const { success, error: showError } = useNotification()

const loading = ref(false)
const saving = ref(false)
const testTgLoading = ref(false)
const spaceCleanupPreview = ref<any>(null)
const spaceCleanupLoading = ref(false)
const spaceCleanupRunning = ref(false)
// 按规则索引存储预览结果
const rulePreviews = ref<Record<number, any>>({})
const ruleLoading = ref<Record<number, boolean>>({})
const ruleRunning = ref<Record<number, boolean>>({})
const qbClients = ref<any[]>([])
const config = reactive<any>({})

/* ========== 识别与订阅规则：本地/远程文本双向绑定 ========== */
function arrayToText(arr: string[] | undefined) {
  return (arr || []).join('\n')
}
function textToArray(val: string) {
  return String(val || '').split('\n').map((s: string) => s.trim()).filter(Boolean)
}

const noiseLocalText = computed({
  get() { return arrayToText(config.custom_noise_words) },
  set(v) { config.custom_noise_words = textToArray(v) }
})
const noiseRemoteText = computed({
  get() { return arrayToText(config.remote_noise_urls) },
  set(v) { config.remote_noise_urls = textToArray(v) }
})

const groupLocalText = computed({
  get() { return arrayToText(config.custom_release_groups) },
  set(v) { config.custom_release_groups = textToArray(v) }
})
const groupRemoteText = computed({
  get() { return arrayToText(config.remote_group_urls) },
  set(v) { config.remote_group_urls = textToArray(v) }
})

const renderLocalText = computed({
  get() { return arrayToText(config.custom_render_words) },
  set(v) { config.custom_render_words = textToArray(v) }
})
const renderRemoteText = computed({
  get() { return arrayToText(config.remote_render_urls) },
  set(v) { config.remote_render_urls = textToArray(v) }
})

const privilegedLocalText = computed({
  get() { return arrayToText(config.custom_privileged_rules) },
  set(v) { config.custom_privileged_rules = textToArray(v) }
})
const privilegedRemoteText = computed({
  get() { return arrayToText(config.remote_privileged_urls) },
  set(v) { config.remote_privileged_urls = textToArray(v) }
})

async function fetchConfig() {
  loading.value = true
  try {
    const data = await configApi.getConfig()
    Object.keys(data).forEach(key => {
      config[key] = data[key]
    })
  } catch (e) {
    showError('获取配置失败')
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  saving.value = true
  try {
    await configApi.saveConfig({ ...config })
    success('配置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function testTelegram() {
  testTgLoading.value = true
  try {
    await systemApi.testTelegram()
    success('测试消息已发送')
  } catch (e: any) {
    showError(e?.message || '发送失败')
  } finally {
    testTgLoading.value = false
  }
}

// 确保 telegram 和 proxy_services 对象存在
function ensureTelegram() {
  if (!config.telegram) {
    config.telegram = {
      bot_token: '',
      chat_id: '',
      enabled: false,
      notify_on_startup: false,
      notify_on_sub_add: false,
      notify_on_sub_del: false,
      notify_on_sub_complete: false,
      notify_on_sub_push: false,
      notify_on_rule_push: false,
      notify_on_organize: false,
      notify_on_strm_finish: false,
      notify_on_strm_link: false,
    }
  }
}

function ensureProxyServices() {
  if (!config.proxy_services) {
    config.proxy_services = {
      tmdb: false,
      bangumi: false,
      remote_rules: false,
      docker_hub: false,
      jackett: false,
      telegram: false,
      rss: false,
    }
  }
}

// 确保 space_cleanup_rules 数组存在
function ensureSpaceCleanupRules() {
  if (!config.space_cleanup_rules) {
    config.space_cleanup_rules = []
  }
  // 为已有规则补充 protected_tags_str 辅助字段
  for (const rule of config.space_cleanup_rules) {
    if (!rule.protected_tags_str && rule.protected_tags) {
      rule.protected_tags_str = rule.protected_tags.join(', ')
    }
    if (rule.delete_files === undefined) {
      rule.delete_files = true
    }
  }
}

function addSpaceCleanupRule() {
  ensureSpaceCleanupRules()
  config.space_cleanup_rules.push({
    client_id: '',
    path: '',
    max_size_gb: 500,
    delete_files: true,
    min_seeders: 0,
    protected_tags: [],
    protected_tags_str: '',
  })
}

async function previewRule(index: number) {
  ruleLoading.value[index] = true
  try {
    rulePreviews.value[index] = await clientsApi.previewSpaceCleanup(index)
  } catch (e: any) {
    showError(e?.message || '预览失败')
  } finally {
    ruleLoading.value[index] = false
  }
}

async function runRule(index: number) {
  ruleRunning.value[index] = true
  try {
    const res = await clientsApi.triggerSpaceCleanup(index)
    const stats = res?.stats || {}
    if (stats.total_deleted > 0) {
      success(`回收完成: 删除 ${stats.total_deleted} 个种子，释放 ${stats.total_freed_display}`)
    } else {
      success('回收完成: 无需删除')
    }
    // 自动刷新该规则预览
    await previewRule(index)
  } catch (e: any) {
    showError(e?.message || '执行失败')
  } finally {
    ruleRunning.value[index] = false
  }
}

onMounted(() => {
  fetchConfig().then(() => {
    ensureSpaceCleanupRules()
  })
  // 加载 QB 客户端列表供规则选择
  clientsApi.getClients().then((list: any[]) => {
    qbClients.value = list.filter((c: any) => c.type === 'qbittorrent')
  }).catch(() => {})
})
</script>

<template>
  <div v-if="loading" class="d-flex justify-center pa-8">
    <v-progress-circular indeterminate color="primary" size="32" />
  </div>

  <div v-else class="settings-basic-tab">
    <!-- 保存按钮 -->
    <div class="d-flex justify-end mb-4">
      <v-btn variant="tonal" color="primary" :loading="saving" @click="saveAll" prepend-icon="mdi-content-save-outline">
        保存全部修改
      </v-btn>
    </div>

    <!-- TMDB 设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-movie-search-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">TMDB 设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <PasswordInput
          v-model="config.tmdb_api_key"
          label="TMDB API Key"
          variant="outlined"
          density="compact"
          class="mb-2"
          hide-details
        />
        <a href="https://www.themoviedb.org/settings/api" target="_blank" class="text-caption text-primary text-decoration-none">
          这是 TMDB API KEY，从 https://www.themoviedb.org/settings/api 申请。
        </a>

        <v-text-field
          v-model="config.tmdb_image_domain"
          label="图片域名"
          variant="outlined"
          density="compact"
          class="mt-4 mb-1"
          hide-details
        />
        <div class="text-caption text-medium-emphasis">可替换为国内镜像站加速图片加载</div>

        <div class="d-flex align-center ga-3 mt-4">
          <v-switch v-model="config.tmdb_image_proxy" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">启用图片代理</div>
            <div class="text-caption text-medium-emphasis">使用国内镜像站时建议关闭，直连更快</div>
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- Bangumi 设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-star-four-points-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">Bangumi 设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <PasswordInput
          v-model="config.bangumi_token"
          label="BGM Token"
          variant="outlined"
          density="compact"
          hide-details
        />
        <a href="https://next.bgm.tv/demo/access-token" target="_blank" class="text-caption text-primary text-decoration-none mt-1 d-block">
          从 https://next.bgm.tv/demo/access-token 获取。
        </a>
      </v-card-text>
    </v-card>

    <!-- SYTMDB 设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-sync-circle-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">SYTMDB 设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
          作者的另一个项目，用于同步修正后的元数据，非必要无需填写。
        </v-alert>
        <v-text-field
          v-model="config.sytmdb_host"
          label="服务地址"
          variant="outlined"
          density="compact"
          class="mb-2"
          hide-details
        />
        <div class="text-caption text-medium-emphasis mb-3">SYTMDB 服务地址，用于同步修正后的元数据</div>

        <PasswordInput
          v-model="config.sytmdb_token"
          label="API Token"
          variant="outlined"
          density="compact"
          hide-details
        />
        <div class="text-caption text-medium-emphasis mt-1">如果 SYTMDB 服务配置了认证，请填写 Token</div>
      </v-card-text>
    </v-card>

    <!-- 识别偏好设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-tune-vertical</v-icon>
        <span class="text-subtitle-1 font-weight-bold">识别偏好设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.anime_priority" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">动漫识别优化</div>
            <div class="text-caption text-medium-emphasis">优先使用动漫专用搜索策略，提高动漫识别准确率</div>
          </div>
        </div>

        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.offline_priority" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">本地数据中心优先</div>
            <div class="text-caption text-medium-emphasis">优先从本地数据中心匹配数据，速度极快且节省 API，无数据时再联网搜索</div>
          </div>
        </div>

        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.batch_enhancement" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">合集识别增强</div>
            <div class="text-caption text-medium-emphasis">增强对合集类资源的识别能力，自动解析多剧集合集</div>
          </div>
        </div>

        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.bangumi_priority" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">Bangumi 数据源优先</div>
            <div class="text-caption text-medium-emphasis">优先使用 Bangumi 数据源，更适合中文动漫信息</div>
          </div>
        </div>

        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.bangumi_failover" :disabled="config.bangumi_priority" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">Bangumi 故障转移</div>
            <div class="text-caption text-medium-emphasis">TMDB 匹配失败时自动使用 Bangumi 进行识别</div>
          </div>
        </div>

        <div class="d-flex align-center ga-3">
          <v-switch v-model="config.series_fingerprint" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">智能记忆</div>
            <div class="text-caption text-medium-emphasis">记住已识别剧集的匹配结果，后续自动应用相同匹配</div>
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- Jackett 设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-magnify-scan</v-icon>
        <span class="text-subtitle-1 font-weight-bold">Jackett 设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field
          v-model="config.jackett_url"
          label="Jackett URL"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
          placeholder="http://192.168.50.12:9117/"
        />
        <div class="text-caption text-medium-emphasis mb-3">示例: http://192.168.50.12:9117/ (请确保包含端口号)</div>

        <PasswordInput
          v-model="config.jackett_api_key"
          label="API Key"
          variant="outlined"
          density="compact"
          class="mb-3"
          hide-details
        />

        <PasswordInput
          v-model="config.jackett_password"
          label="管理密码"
          variant="outlined"
          density="compact"
          hide-details
        />
        <div class="text-caption text-medium-emphasis mt-1">如果你的 Jackett 设置了访问密码，请在此填写以获取完整站点列表。</div>
      </v-card-text>
    </v-card>

    <!-- Emby 设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-filmstrip-box</v-icon>
        <span class="text-subtitle-1 font-weight-bold">Emby 设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field
          v-model="config.emby_url"
          label="服务地址"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
          placeholder="http://localhost:8096"
        />
        <div class="text-caption text-medium-emphasis mb-3">Emby 服务器地址，包含端口号</div>

        <PasswordInput
          v-model="config.emby_api_key"
          label="API Key"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
        />
        <div class="text-caption text-medium-emphasis mb-3">在 Emby 设置中生成 API Key</div>

        <v-text-field
          v-model="config.emby_username"
          label="用户名"
          variant="outlined"
          density="compact"
          class="mb-3"
          hide-details
        />

        <PasswordInput
          v-model="config.emby_password"
          label="密码"
          variant="outlined"
          density="compact"
          class="mb-3"
          hide-details
        />

        <v-text-field
          v-model="config.emby_user_id"
          label="用户 ID"
          variant="outlined"
          density="compact"
          hide-details
        />
        <div class="text-caption text-medium-emphasis mt-1">在 Emby 用户配置页面，从浏览器地址栏复制 userId 参数值</div>
      </v-card-text>
    </v-card>

    <!-- Telegram 通知设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-send-circle-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">通知设置 (Telegram)</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4" v-if="(ensureTelegram(), true)">
        <PasswordInput
          v-model="config.telegram.bot_token"
          label="Bot Token"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
        />
        <a href="https://t.me/BotFather" target="_blank" class="text-caption text-primary text-decoration-none d-block mb-3">
          从 @BotFather 获取的 Bot Token，用于发送消息。
        </a>

        <PasswordInput
          v-model="config.telegram.chat_id"
          label="Chat ID"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
        />
        <a href="https://t.me/userinfobot" target="_blank" class="text-caption text-primary text-decoration-none d-block mb-4">
          发送消息给 @userinfobot 获取你的个人 Chat ID，或获取群组/频道的 Chat ID (通常以 -100 开头)。
        </a>

        <div class="text-body-2 font-weight-medium mb-2">通知类型</div>
        <v-row class="mb-4">
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_startup" label="系统启动" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_sub_add" label="新增订阅" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_sub_del" label="删除订阅" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_sub_complete" label="订阅完结" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_sub_push" label="订阅推送" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_rule_push" label="规则下载" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_organize" label="整理完成" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_strm_finish" label="STRM 完成" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.telegram.notify_on_strm_link" label="STRM 联动" density="compact" hide-details color="primary" />
          </v-col>
        </v-row>

        <div class="d-flex align-center ga-3">
          <v-switch v-model="config.telegram.enabled" density="compact" hide-details color="primary" />
          <v-btn
            variant="tonal"
            color="primary"
            size="small"
            :loading="testTgLoading"
            :disabled="!config.telegram.bot_token"
            prepend-icon="mdi-send"
            @click="testTelegram"
          >
            发送测试消息
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <!-- 代理设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-vpn</v-icon>
        <span class="text-subtitle-1 font-weight-bold">网络代理设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4" v-if="(ensureProxyServices(), true)">
        <v-text-field
          v-model="config.http_proxy"
          label="HTTP 代理"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
          placeholder="http://ip:port 或 http://user:pass@ip:port"
        />
        <div class="text-caption text-medium-emphasis mb-4">支持 http://ip:port 或 http://user:pass@ip:port</div>

        <div class="text-body-2 font-weight-medium mb-2">代理服务</div>
        <v-row>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.tmdb" label="TMDB" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.bangumi" label="Bangumi" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.remote_rules" label="远程规则" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.docker_hub" label="Docker Hub" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.jackett" label="Jackett" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.telegram" label="Telegram" density="compact" hide-details color="primary" />
          </v-col>
          <v-col cols="6" sm="4" md="3" class="py-1">
            <v-checkbox v-model="config.proxy_services.rss" label="RSS 订阅" density="compact" hide-details color="primary" />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 自动化设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-cog-transfer-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">自动化设置</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-row>
          <!-- RSS 自动刷新 -->
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-3 mb-2">
              <v-switch v-model="config.rss_auto_refresh" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">RSS 自动刷新</div>
                <div class="text-caption text-medium-emphasis">定时拉取 RSS 源，检测新发布的资源</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.rss_refresh_interval"
              label="刷新间隔 (分)"
              type="number"
              variant="outlined"
              density="compact"
              :disabled="!config.rss_auto_refresh"
              hide-details
              min="1"
              max="1440"
            />
          </v-col>

          <!-- 规则自动同步 -->
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-3 mb-2">
              <v-switch v-model="config.rule_auto_update" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">规则自动同步</div>
                <div class="text-caption text-medium-emphasis">定时从远程地址同步社区识别规则</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.rule_update_interval"
              label="同步周期 (时)"
              type="number"
              variant="outlined"
              density="compact"
              :disabled="!config.rule_auto_update"
              hide-details
              min="1"
            />
          </v-col>

          <!-- 自动搜寻补全 -->
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-3 mb-2">
              <v-switch v-model="config.sub_auto_fill" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">自动搜寻补全</div>
                <div class="text-caption text-medium-emphasis">自动搜寻补全缺失的订阅集数</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.sub_fill_interval"
              label="补全周期 (时)"
              type="number"
              variant="outlined"
              density="compact"
              :disabled="!config.sub_auto_fill"
              hide-details
              min="1"
            />
          </v-col>

          <!-- 定时清理缓存 -->
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-3 mb-2">
              <v-switch v-model="config.auto_clear_recognition" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">定时清理缓存</div>
                <div class="text-caption text-medium-emphasis">定时清空 RSS 订阅项缓存</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.auto_clear_interval"
              label="清理周期 (时)"
              type="number"
              variant="outlined"
              density="compact"
              :disabled="!config.auto_clear_recognition"
              hide-details
              min="1"
            />
          </v-col>

          <!-- 死种超时清理 -->
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.stalled_timeout_minutes"
              label="死种超时清理 (分钟)"
              type="number"
              variant="outlined"
              density="compact"
              hide-details
              min="0"
              max="43200"
              placeholder="0 为禁用"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.stalled_monitor_interval"
              label="巡检频率 (分钟)"
              type="number"
              variant="outlined"
              density="compact"
              hide-details
              min="0"
              max="1440"
              placeholder="0 为禁用，建议 15-60"
            />
          </v-col>

          <v-col cols="12">
            <v-alert type="info" variant="tonal" density="compact">
              定时检查 qBittorrent 下载器，发现运行超过 <strong>{{ config.stalled_timeout_minutes || 0 }}</strong> 分钟且进度未完成的任务，将自动删除并加入黑名单，同时回滚订阅状态以便重新下载。
            </v-alert>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 磁盘空间回收 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-database-remove-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">磁盘空间回收</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <div class="d-flex align-center ga-3 mb-4">
          <v-switch v-model="config.space_cleanup_enabled" density="compact" hide-details color="primary" />
          <div>
            <div class="text-body-2 font-weight-medium">启用磁盘空间自动回收</div>
            <div class="text-caption text-medium-emphasis">监控 QB 种子占用体积，超过阈值后从最老的种子开始删除</div>
          </div>
        </div>

        <v-row class="mb-2">
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.space_cleanup_interval"
              label="巡检频率 (分钟)"
              type="number"
              variant="outlined"
              density="compact"
              :disabled="!config.space_cleanup_enabled"
              hide-details
              min="1"
              placeholder="0 为禁用，建议 15-60"
            />
          </v-col>
        </v-row>

        <!-- 规则列表 -->
        <div v-if="!config.space_cleanup_rules || config.space_cleanup_rules.length === 0" class="text-center text-medium-emphasis py-4">
          暂无回收规则，点击下方按钮添加
        </div>

        <div
          v-for="(rule, index) in (config.space_cleanup_rules || [])"
          :key="index"
          class="rule-item mb-3 pa-3 rounded border"
          style="border-color: rgba(var(--v-theme-primary), 0.15); background: rgba(var(--v-theme-surface-variant), 0.3);"
        >
          <div class="d-flex align-center justify-space-between mb-2">
            <span class="text-body-2 font-weight-medium">规则 {{ Number(index) + 1 }}</span>
            <div class="d-flex ga-1">
              <v-btn
                size="x-small"
                variant="tonal"
                color="info"
                prepend-icon="mdi-eye-outline"
                :loading="ruleLoading[Number(index)]"
                @click="previewRule(Number(index))"
              >
                预览
              </v-btn>
              <v-btn
                size="x-small"
                variant="tonal"
                color="warning"
                prepend-icon="mdi-broom"
                :loading="ruleRunning[Number(index)]"
                @click="runRule(Number(index))"
              >
                执行
              </v-btn>
              <v-btn
                size="x-small"
                variant="tonal"
                color="error"
                prepend-icon="mdi-delete-outline"
                @click="config.space_cleanup_rules.splice(index, 1); rulePreviews[Number(index)] = null"
              >
                删除
              </v-btn>
            </div>
          </div>

          <v-row dense>
            <v-col cols="12" md="6">
              <v-select
                v-model="rule.client_id"
                :items="qbClients"
                item-title="name"
                item-value="id"
                label="指定下载器"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                placeholder="不选则对所有 QB 生效"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="rule.path"
                label="监控路径"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="/downloads"
              />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field
                v-model="rule.max_size_gb"
                label="体积上限 (GB)"
                type="number"
                variant="outlined"
                density="compact"
                hide-details
                min="1"
                placeholder="500"
              />
            </v-col>
            <v-col cols="6" md="3">
              <v-switch
                v-model="rule.delete_files"
                label="同时删文件"
                density="compact"
                hide-details
                color="primary"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="rule.min_seeders"
                label="最少做种数保护 (0=不保护)"
                type="number"
                variant="outlined"
                density="compact"
                hide-details
                min="0"
                placeholder="0"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="rule.protected_tags_str"
                label="保护标签 (逗号分隔)"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="keep,important"
                @blur="rule.protected_tags = (rule.protected_tags_str || '').split(',').map((s: string) => s.trim()).filter(Boolean)"
              />
            </v-col>
          </v-row>

          <!-- 单规则预览结果 -->
          <div v-if="rulePreviews[Number(index)]" class="mt-3">
            <v-divider class="mb-2" />
            <div
              v-for="(group, gi) in rulePreviews[Number(index)].groups"
              :key="gi"
              class="mb-2 pa-2 rounded"
              style="background: rgba(var(--v-theme-surface), 0.5);"
            >
              <div class="text-caption mb-1">
                <v-icon size="14" class="mr-1">mdi-server</v-icon>
                {{ group.client_name }} → {{ group.path }}
              </div>
              <div class="text-body-2 mb-2">
                占用 <strong>{{ group.total_size_gb }} GB</strong> / 上限 <strong>{{ group.max_size_gb }} GB</strong>
                <v-chip v-if="group.over_limit" size="x-small" color="error" class="ml-2">超限 {{ group.over_by_gb }} GB</v-chip>
                <v-chip v-else size="x-small" color="success" class="ml-2">正常</v-chip>
              </div>
              <div v-if="group.torrents_to_delete && group.torrents_to_delete.length > 0">
                <div class="text-caption text-medium-emphasis mb-1">
                  计划删除 ({{ group.torrents_to_delete.length }} 个):
                </div>
                <div
                  v-for="(t, ti) in group.torrents_to_delete"
                  :key="ti"
                  class="text-caption d-flex align-center ga-2 py-1"
                  style="border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);"
                >
                  <v-icon size="12" color="error">mdi-file-remove</v-icon>
                  <span class="flex-fill">{{ t.name }}</span>
                  <span class="text-medium-emphasis">{{ t.size_display }}</span>
                </div>
              </div>
              <div v-else class="text-caption text-success">
                无需删除
              </div>
            </div>
          </div>
        </div>

        <div class="d-flex ga-2 mt-2">
          <v-btn
            variant="tonal"
            color="primary"
            size="small"
            prepend-icon="mdi-plus"
            @click="addSpaceCleanupRule"
          >
            添加规则
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>
