<script setup lang="ts">
/**
 * BasicConfigTab — 基础配置
 *
 * 包含: TMDB、Bangumi、SYTMDB、识别偏好、Jackett、Emby、Telegram通知、代理设置、自动化设置
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { configApi, systemApi } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'BasicConfigTab' })

const { success, error: showError } = useNotification()

const loading = ref(false)
const saving = ref(false)
const testTgLoading = ref(false)
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

onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div v-if="loading" class="d-flex justify-center pa-8">
    <v-progress-circular indeterminate color="primary" size="32" />
  </div>

  <div v-else class="settings-basic-tab">
    <!-- 保存按钮 -->
    <div class="d-flex justify-end mb-4">
      <v-btn color="primary" variant="flat" :loading="saving" @click="saveAll" prepend-icon="mdi-content-save-outline">
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
        <v-text-field
          v-model="config.tmdb_api_key"
          label="TMDB API Key"
          type="password"
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
        <v-text-field
          v-model="config.bangumi_token"
          label="BGM Token"
          type="password"
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

        <v-text-field
          v-model="config.sytmdb_token"
          label="API Token"
          type="password"
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

        <v-text-field
          v-model="config.jackett_api_key"
          label="API Key"
          type="password"
          variant="outlined"
          density="compact"
          class="mb-3"
          hide-details
        />

        <v-text-field
          v-model="config.jackett_password"
          label="管理密码"
          type="password"
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

        <v-text-field
          v-model="config.emby_api_key"
          label="API Key"
          type="password"
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

        <v-text-field
          v-model="config.emby_password"
          label="密码"
          type="password"
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
        <v-text-field
          v-model="config.telegram.bot_token"
          label="Bot Token"
          type="password"
          variant="outlined"
          density="compact"
          class="mb-1"
          hide-details
        />
        <a href="https://t.me/BotFather" target="_blank" class="text-caption text-primary text-decoration-none d-block mb-3">
          从 @BotFather 获取的 Bot Token，用于发送消息。
        </a>

        <v-text-field
          v-model="config.telegram.chat_id"
          label="Chat ID"
          type="password"
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
  </div>
</template>
