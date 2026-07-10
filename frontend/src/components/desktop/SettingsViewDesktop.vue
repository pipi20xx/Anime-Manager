<script setup lang="ts">
import { computed } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NForm, NFormItem, 
  NDivider, NGrid, NGi, NSwitch, NTabs, NTabPane,
  NSpin, NCheckbox, NInput, NTag, useDialog
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  DeleteOutlined as DeleteIcon
} from '@vicons/material'
import ClientEditModal from './ClientEditModalDesktop.vue'
import HealthCheckManager from './HealthCheckManagerDesktop.vue'
import EmbyConfig from '../../components/EmbyConfig.vue'
import AppTextField from '../../components/AppTextField.vue'
import AiLabView from '../../views/desktop/AiLabViewDesktop.vue'
import AccountTab from '../../views/settings/AccountTab.vue'
import ServiceStatusTab from '../../views/settings/ServiceStatusTab.vue'
import { useSettings } from '../../composables/views/useSettings'
import { getButtonStyle } from '../../composables/useButtonStyles'

const dialog = useDialog()

const handleDeleteClientWithConfirm = (client: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除下载客户端「${client.name}」吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => handleDeleteClient(client.id)
  })
}

const {
  loading,
  syncLoading,
  testTgLoading,
  config,
  clients,
  showClientModal,
  currentClient,
  isNewClient,
  testTelegram,
  openAddClient,
  openEditClient,
  handleClientSave,
  handleDeleteClient,
  saveAll,
  refreshRemoteRules
} = useSettings()

/* ========== 识别与订阅规则：本地/远程文本双向绑定 ========== */
function arrayToText(arr: string[] | undefined) {
  return (arr || []).join('\n')
}
function textToArray(val: string) {
  return String(val || '').split('\n').map(s => s.trim())
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
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <div>
        <h1>系统设置</h1>
        <div class="subtitle">系统配置与选项</div>
      </div>
      <n-button v-bind="getButtonStyle('primary')" size="large" :loading="loading" @click="saveAll">
        保存全部修改
      </n-button>
    </div>

    <n-spin :show="loading">
      <n-tabs type="line" animated class="custom-tabs">
        <!-- 基础配置 -->
        <n-tab-pane name="basic" tab="基础配置">
          <n-space vertical size="large">
            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">TMDB 设置</span>
                </div>
              </template>
              <n-form>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.tmdb_api_key" label="TMDB API" type="password" />
                    <a href="https://www.themoviedb.org/settings/api" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">这是 TMDB API KEY https://www.themoviedb.org/settings/api 申请。</a>
                  </n-space>
                </n-form-item>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.tmdb_image_domain" label="图片域名" />
                    <span style="font-size: 12px; color: var(--n-text-color-3);">可替换为国内镜像站加速图片加载</span>
                  </n-space>
                </n-form-item>
                <n-form-item>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.tmdb_image_proxy" />
                    <span class="switch-label">启用图片代理</span>
                    <span class="switch-desc">使用国内镜像站时建议关闭，直连更快</span>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">Bangumi 设置</span>
                </div>
              </template>
              <n-form>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.bangumi_token" label="BGM Token" type="password" />
                    <a href="https://next.bgm.tv/demo/access-token" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">从 https://next.bgm.tv/demo/access-token 获取。</a>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">SYTMDB 设置</span>
                </div>
              </template>
              <n-form>
                <div style="margin-bottom: 12px; padding: 8px 12px; background: var(--n-color); border-radius: 4px; border-left: 3px solid var(--n-warning-color);">
                  <span style="font-size: 13px; color: var(--n-text-color-2);">作者的另一个项目，用于同步修正后的元数据，非必要无需填写。</span>
                </div>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.sytmdb_host" label="服务地址" />
                    <span style="font-size: 12px; color: var(--n-text-color-3);">SYTMDB 服务地址，用于同步修正后的元数据</span>
                  </n-space>
                </n-form-item>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.sytmdb_token" label="API Token" type="password" />
                    <span style="font-size: 12px; color: var(--n-text-color-3);">如果 SYTMDB 服务配置了认证，请填写 Token</span>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">识别偏好设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="100">
                <n-space vertical :size="16" style="width: 100%">
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.anime_priority" />
                    <span class="switch-label">动漫识别优化</span>
                    <span class="switch-desc">优先使用动漫专用搜索策略，提高动漫识别准确率</span>
                  </n-space>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.offline_priority" />
                    <span class="switch-label">本地数据中心优先</span>
                    <span class="switch-desc">优先从本地数据中心匹配数据，速度极快且节省 API，无数据时再联网搜索</span>
                  </n-space>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.batch_enhancement" />
                    <span class="switch-label">合集识别增强</span>
                    <span class="switch-desc">增强对合集类资源的识别能力，自动解析多剧集合集</span>
                  </n-space>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.bangumi_priority" />
                    <span class="switch-label">Bangumi 数据源优先</span>
                    <span class="switch-desc">优先使用 Bangumi 数据源，更适合中文动漫信息</span>
                  </n-space>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.bangumi_failover" :disabled="config.bangumi_priority" />
                    <span class="switch-label">Bangumi 故障转移</span>
                    <span class="switch-desc">TMDB 匹配失败时自动使用 Bangumi 进行识别</span>
                  </n-space>
                  <n-space align="center" :size="12">
                    <n-switch v-model:value="config.series_fingerprint" />
                    <span class="switch-label">智能记忆</span>
                    <span class="switch-desc">记住已识别剧集的匹配结果，后续自动应用相同匹配</span>
                  </n-space>
                </n-space>
              </n-form>
            </n-card>

            <!-- Jackett 设置 -->
            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">Jackett 设置</span>
                </div>
              </template>
              <n-form>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.jackett_url" label="Jackett URL" />
                    <span style="font-size: 12px; color: var(--text-muted);">示例: http://192.168.50.12:9117/ (请确保包含端口号)</span>
                  </n-space>
                </n-form-item>
                <n-form-item>
                  <AppTextField v-model:value="config.jackett_api_key" label="API Key" type="password" />
                </n-form-item>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.jackett_password" label="管理密码" type="password" />
                    <span style="font-size: 12px; color: var(--text-muted);">如果你的 Jackett 设置了访问密码，请在此填写以获取完整站点列表。</span>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <!-- Emby 设置 -->
            <EmbyConfig
              :emby-url="config.emby_url || ''"
              :emby-api-key="config.emby_api_key || ''"
              :emby-username="config.emby_username || ''"
              :emby-password="config.emby_password || ''"
              :emby-user-id="config.emby_user_id || ''"
              @update:emby-url="(val: string) => config.emby_url = val"
              @update:emby-api-key="(val: string) => config.emby_api_key = val"
              @update:emby-username="(val: string) => config.emby_username = val"
              @update:emby-password="(val: string) => config.emby_password = val"
              @update:emby-user-id="(val: string) => config.emby_user_id = val"
            />

            <!-- Telegram 通知设置 -->
            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">通知设置 (Telegram)</span>
                </div>
              </template>
              <n-form>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                     <AppTextField v-model:value="config.telegram.bot_token" label="Bot Token" type="password" />
                     <a href="https://t.me/BotFather" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">从 @BotFather 获取的 Bot Token，用于发送消息。</a>
                  </n-space>
                </n-form-item>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.telegram.chat_id" label="Chat ID" type="password" />
                    <a href="https://t.me/userinfobot" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">发送消息给 @userinfobot 获取你的个人 Chat ID，或获取群组/频道的 Chat ID (通常以 -100 开头)。</a>
                  </n-space>
                </n-form-item>
                <n-form-item label="通知类型">
                  <n-space item-style="display: flex;">
                    <n-checkbox v-model:checked="config.telegram.notify_on_startup">系统启动</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_add">新增订阅</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_del">删除订阅</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_complete">订阅完结</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_push">订阅推送</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_rule_push">规则下载</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_organize">整理完成</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_strm_finish">STRM 完成</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_strm_link">STRM 联动</n-checkbox>
                  </n-space>
                </n-form-item>
                <n-form-item label="功能开关">
                  <n-space align="center">
                    <n-switch v-model:value="config.telegram.enabled" />
                    <n-button v-bind="getButtonStyle('secondary')" size="small" :loading="testTgLoading" @click="testTelegram" :disabled="!config.telegram.bot_token">
                      发送测试消息
                    </n-button>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <!-- 代理设置 -->
            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">网络代理设置</span>
                </div>
              </template>
              <n-form>
                <n-form-item>
                  <n-space vertical :size="2" style="width: 100%">
                    <AppTextField v-model:value="config.http_proxy" label="HTTP 代理" />
                    <span style="font-size: 12px; color: var(--text-muted);">支持 http://ip:port 或 http://user:pass@ip:port</span>
                  </n-space>
                </n-form-item>
                <n-form-item label="代理服务">
                  <n-space>
                    <n-checkbox v-model:checked="config.proxy_services.tmdb">TMDB</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.bangumi">Bangumi</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.remote_rules">远程规则</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.docker_hub">Docker Hub</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.jackett">Jackett</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.telegram">Telegram</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.rss">RSS 订阅</n-checkbox>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自动化设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="120">
                <n-grid :cols="2" :x-gap="24" :y-gap="16" style="align-items: center">
                  <!-- 第一行: RSS 刷新 -->
                  <n-gi>
                    <div class="switch-row">
                      <n-switch v-model:value="config.rss_auto_refresh" />
                      <span class="switch-row__label">RSS 自动刷新</span>
                      <span class="switch-row__desc">定时拉取 RSS 源，检测新发布的资源</span>
                    </div>
                  </n-gi>
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.rss_refresh_interval" 
                        label="刷新间隔 (分)"
                        type="number"
                        :min="1" :max="1440" 
                        :disabled="!config.rss_auto_refresh"
                        placeholder="请输入分钟数" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第二行: 规则同步 -->
                  <n-gi>
                    <div class="switch-row">
                      <n-switch v-model:value="config.rule_auto_update" />
                      <span class="switch-row__label">规则自动同步</span>
                      <span class="switch-row__desc">定时从远程地址同步社区识别规则</span>
                    </div>
                  </n-gi>
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.rule_update_interval" 
                        label="同步周期 (时)"
                        type="number"
                        :min="1" 
                        :disabled="!config.rule_auto_update"
                        placeholder="请输入小时数" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第三行: 自动补全 -->
                  <n-gi>
                    <div class="switch-row">
                      <n-switch v-model:value="config.sub_auto_fill" />
                      <span class="switch-row__label">自动搜寻补全</span>
                      <span class="switch-row__desc">自动搜寻补全缺失的订阅集数</span>
                    </div>
                  </n-gi>
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.sub_fill_interval" 
                        label="补全周期 (时)"
                        type="number"
                        :min="1" 
                        :disabled="!config.sub_auto_fill"
                        placeholder="请输入小时数" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第四行: 定时清理 -->
                  <n-gi>
                    <div class="switch-row">
                      <n-switch v-model:value="config.auto_clear_recognition" />
                      <span class="switch-row__label">定时清理缓存</span>
                      <span class="switch-row__desc">定时清空 RSS 订阅项缓存</span>
                    </div>
                  </n-gi>
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.auto_clear_interval" 
                        label="清理周期 (时)"
                        type="number"
                        :min="1" 
                        :disabled="!config.auto_clear_recognition"
                        placeholder="请输入小时数" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第五行: 死种清理 -->
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.stalled_timeout_minutes" 
                        label="死种超时清理"
                        hint="0 为禁用"
                        type="number"
                        :min="0" :max="43200"
                        placeholder="例如 60" 
                      >
                        <template #suffix>分钟</template>
                      </AppTextField>
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item>
                      <AppTextField 
                        v-model:value="config.stalled_monitor_interval" 
                        label="巡检频率 (分)"
                        hint="0 为禁用，建议 15-60"
                        type="number"
                        :min="0" :max="1440"
                        placeholder="例如 30" 
                      >
                        <template #suffix>分钟</template>
                      </AppTextField>
                    </n-form-item>
                  </n-gi>
                  <n-gi :span="2">
                    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px; margin-top: -8px;">
                      定时检查 qBittorrent 下载器，发现运行超过 <b>{{ config.stalled_timeout_minutes }}</b> 分钟且进度未完成的任务，将自动删除并加入黑名单，同时回滚订阅状态以便重新下载。
                    </div>
                  </n-gi>
                </n-grid>
              </n-form>
            </n-card>
          </n-space>
        </n-tab-pane>

        <!-- 下载器管理 -->
        <n-tab-pane name="clients" tab="下载器管理">
          <n-card class="app-card-config">
            <template #header>
              <div class="card-title-box">
                <span class="card-title-text">下载客户端配置</span>
              </div>
            </template>
            <template #header-extra>
              <n-button type="primary" size="small" @click="openAddClient">
                添加客户端
              </n-button>
            </template>
            
            <n-grid :x-gap="12" :y-gap="12" :cols="3">
              <n-gi v-for="client in clients" :key="client.id">
                <n-card hoverable class="client-card" :data-app-instance="'client-card'" @click="openEditClient(client)">
                  <div class="client-info">
                    <div class="client-name">
                      <n-icon v-if="client.is_default" style="color: var(--n-warning-color)" title="默认客户端">
                         <span style="font-size:12px">★</span>
                      </n-icon>
                      {{ client.name }}
                    </div>
                    <div class="client-meta">{{ client.type }} | {{ client.url }}</div>
                    <div v-if="client.version" class="client-version">
                      <n-tag size="small" type="success">{{ client.version }}</n-tag>
                      <span v-if="client.last_test_time" class="test-time">{{ client.last_test_time }}</span>
                    </div>
                  </div>
                  <template #action>
                    <n-space justify="end" @click.stop>
                      <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDeleteClientWithConfirm(client)">
                        <template #icon><n-icon><DeleteIcon/></n-icon></template>
                      </n-button>
                    </n-space>
                  </template>
                </n-card>
              </n-gi>
              <n-gi v-if="clients.length === 0">
                 <div class="empty-clients">暂无下载器，请点击右上角添加</div>
              </n-gi>
            </n-grid>
          </n-card>
        </n-tab-pane>

        <!-- 规则管理 -->
        <n-tab-pane name="rules" tab="识别与订阅规则">
          <n-space vertical size="large">
            <div class="rules-toolbar">
              <n-button type="primary" size="small" :loading="syncLoading" @click="refreshRemoteRules">
                同步远程规则
              </n-button>
            </div>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自定义识别词</span>
                </div>
              </template>
              <n-grid :cols="2" :x-gap="24" :y-gap="12">
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">本地规则</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">可编辑</n-tag>
                    </div>
                    <n-input
                      v-model:value="noiseLocalText"
                      type="textarea"
                      placeholder="例如: 10月新番&#10;或者: 藤本树 17-26 => 藤本树 17_26"
                      :rows="8"
                    />
                  </div>
                </n-gi>
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">远程订阅</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">仅同步</n-tag>
                    </div>
                    <n-input
                      v-model:value="noiseRemoteText"
                      type="textarea"
                      placeholder="http://example.com/rules.txt"
                      :rows="8"
                    />
                  </div>
                </n-gi>
              </n-grid>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自定义制作组</span>
                </div>
              </template>
              <n-grid :cols="2" :x-gap="24" :y-gap="12">
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">本地规则</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">可编辑</n-tag>
                    </div>
                    <n-input
                      v-model:value="groupLocalText"
                      type="textarea"
                      placeholder="例如: SweetSub&#10;Mikanani"
                      :rows="8"
                    />
                  </div>
                </n-gi>
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">远程订阅</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">仅同步</n-tag>
                    </div>
                    <n-input
                      v-model:value="groupRemoteText"
                      type="textarea"
                      placeholder="http://example.com/rules.txt"
                      :rows="8"
                    />
                  </div>
                </n-gi>
              </n-grid>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自定义渲染词</span>
                </div>
              </template>
              <n-grid :cols="2" :x-gap="24" :y-gap="12">
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">本地规则</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">可编辑</n-tag>
                    </div>
                    <n-input
                      v-model:value="renderLocalText"
                      type="textarea"
                      placeholder="例如: 剧场版 => {[type=movie]}&#10;S2 => {[s=2]}"
                      :rows="8"
                    />
                  </div>
                </n-gi>
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">远程订阅</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">仅同步</n-tag>
                    </div>
                    <n-input
                      v-model:value="renderRemoteText"
                      type="textarea"
                      placeholder="http://example.com/rules.txt"
                      :rows="8"
                    />
                  </div>
                </n-gi>
              </n-grid>
            </n-card>

            <n-card class="app-card-config">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自定义特权规则</span>
                </div>
              </template>
              <n-grid :cols="2" :x-gap="24" :y-gap="12">
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">本地规则</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#2e7d32', borderColor: 'transparent' }">可编辑</n-tag>
                    </div>
                    <n-input
                      v-model:value="privilegedLocalText"
                      type="textarea"
                      placeholder="格式: 正则表达式 => {[字段=值;字段=值]}&#10;例如: ^\[([^\]]+)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3]}&#10;例如: Yami.Shibai.+?(\d+).+?(\d+).+?^[A-Za-z]+$ => {[tmdbid=56559;type=tv;s=\1;e=\2]}"
                      :rows="8"
                    />
                  </div>
                </n-gi>
                <n-gi>
                  <div class="rule-col">
                    <div class="rule-col-header">
                      <span class="switch-label">远程订阅</span>
                      <n-tag size="tiny" round :bordered="false" :style="{ color: '#fff', backgroundColor: '#0288d1', borderColor: 'transparent' }">仅同步</n-tag>
                    </div>
                    <n-input
                      v-model:value="privilegedRemoteText"
                      type="textarea"
                      placeholder="http://example.com/rules.txt"
                      :rows="8"
                    />
                  </div>
                </n-gi>
              </n-grid>
            </n-card>
          </n-space>
        </n-tab-pane>

        <!-- AI 实验室 -->
        <n-tab-pane name="ai_lab" tab="AI 实验室">
          <AiLabView :external-config="config" />
        </n-tab-pane>

        <!-- 账号与安全 -->
        <n-tab-pane name="account" tab="账号与安全">
          <AccountTab />
        </n-tab-pane>

        <!-- 服务状态 -->
        <n-tab-pane name="services" tab="服务状态">
          <ServiceStatusTab />
        </n-tab-pane>

        <!-- 掉盘检测 -->
        <n-tab-pane name="health" tab="掉盘与失效检测">
          <HealthCheckManager />
        </n-tab-pane>
      </n-tabs>
    </n-spin>

    <ClientEditModal 
      v-model:show="showClientModal" 
      :client-data="currentClient" 
      :is-new="isNewClient"
      :all-clients="clients"
      @save="handleClientSave" 
    />
  </div>
</template>

<style scoped>
.settings-view { width: 100%; }

.card-title-box { display: flex; align-items: center; gap: 8px; }
.card-title-text { font-size: 15px; font-weight: 600; color: var(--text-secondary); }

.rules-toolbar { display: flex; justify-content: flex-end; }

.rule-col { display: flex; flex-direction: column; gap: 6px; }
.rule-col-header { display: flex; align-items: center; gap: 8px; }

/* 规则输入框：移除 Naive UI 默认灰色底色，跟随卡片背景；边框使用项目统一变量 */
.rule-col :deep(.n-input) {
  --n-color: transparent !important;
  --n-color-focus: transparent !important;
}
.rule-col :deep(.n-input .n-input-wrapper) {
  background: transparent !important;
}
.rule-col :deep(.n-input .n-input__border),
.rule-col :deep(.n-input .n-input__border-hover),
.rule-col :deep(.n-input .n-input__border-focus) {
  border: var(--input-border) !important;
}

.client-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 140px;
}
.client-card :deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.client-card .client-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.client-card .client-name { font-weight: bold; font-size: 16px; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.client-card .client-meta { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.client-card .client-version { margin-top: auto; padding-top: 8px; display: flex; align-items: center; gap: 8px; }
.client-card .test-time { font-size: 11px; color: var(--text-tertiary); }
.empty-clients { padding: 40px; text-align: center; color: var(--text-muted); border: 1px dashed var(--border-medium); border-radius: 8px; }

.switch-label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-desc { font-size: 12px; color: var(--text-tertiary); }

.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }

.form-item-desc { font-size: 12px; color: var(--text-tertiary); margin-top: -8px; margin-bottom: 8px; line-height: 1.4; }

/* Tabs 样式已移至 global.css 统一管理 */
/* 统一为所有 Tab 面板添加顶部间距，避免内容紧贴 Tabs 导航栏 */
.custom-tabs {
  --tabs-pane-padding: 16px 0 0 0;
}
</style>