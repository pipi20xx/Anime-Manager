<script setup lang="ts">
import { 
  NCard, NSpace, NButton, NIcon, NInput, NForm, NFormItem, 
  NDivider, NGrid, NGi, NSwitch, NTabs, NTabPane,
  NSpin, NCheckbox, NInputNumber, NPopconfirm
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  SyncOutlined as SyncIcon,
  DeleteOutlineOutlined as DeleteIcon
} from '@vicons/material'
import ConfigSection from '../../components/ConfigSection.vue'
import ClientEditModal from '../../components/ClientEditModal.vue'
import HealthCheckManager from '../../components/HealthCheckManager.vue'
import EmbyConfig from '../../components/EmbyConfig.vue'
import AiLabView from '../../views/AiLabView.vue'
import AccountTab from '../../views/settings/AccountTab.vue'
import ServiceStatusTab from '../../views/settings/ServiceStatusTab.vue'
import { useSettings } from '../../composables/views/useSettings'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
      <n-tabs type="segment" animated class="custom-tabs">
        <!-- 基础配置 -->
        <n-tab-pane name="basic" tab="基础配置">
          <n-space vertical size="large">
            <n-card bordered style="background: var(--app-surface-card)">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">TMDB 设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="100">
                <n-form-item label="TMDB API">
                  <n-space vertical :size="2" style="width: 100%">
                    <n-input v-model:value="config.tmdb_api_key" type="password" show-password-on="click" placeholder="输入 TMDB API Key" />
                    <a href="https://www.themoviedb.org/settings/api" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">这是 TMDB API KEY https://www.themoviedb.org/settings/api 申请。</a>
                  </n-space>
                </n-form-item>
                <n-form-item label="BGM Token">
                  <n-space vertical :size="2" style="width: 100%">
                    <n-input v-model:value="config.bangumi_token" type="password" show-password-on="click" placeholder="可选: 输入 Bangumi Access Token" />
                    <a href="https://next.bgm.tv/demo/access-token" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">从 https://next.bgm.tv/demo/access-token 获取。</a>
                  </n-space>
                </n-form-item>
                <n-form-item label="搜索策略">
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
                </n-form-item>
              </n-form>
            </n-card>

            <!-- Jackett 设置 -->
            <n-card bordered style="background: var(--app-surface-card)">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">Jackett 设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="100">
                <n-form-item label="Jackett URL">
                  <n-space vertical :size="2" style="width: 100%">
                    <n-input v-model:value="config.jackett_url" placeholder="http://192.168.1.10:9117" />
                    <span style="font-size: 12px; color: var(--text-muted);">示例: http://192.168.50.12:9117/ (请确保包含端口号)</span>
                  </n-space>
                </n-form-item>
                <n-form-item label="API Key">
                  <n-input v-model:value="config.jackett_api_key" type="password" show-password-on="click" placeholder="Jackett API Key" />
                </n-form-item>
                <n-form-item label="管理密码">
                  <n-space vertical :size="2" style="width: 100%">
                    <n-input v-model:value="config.jackett_password" type="password" show-password-on="click" placeholder="Jackett 管理密码 (可选)" />
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
            <n-card bordered style="background: var(--app-surface-card)">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">通知设置 (Telegram)</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="100">
                <n-form-item label="Bot Token">
                  <n-space vertical :size="2" style="width: 100%">
                     <n-input v-model:value="config.telegram.bot_token" type="password" show-password-on="click" placeholder="123456789:ABCdefGHIjklMNOpqrs..." />
                     <a href="https://t.me/BotFather" target="_blank" style="font-size: 12px; color: var(--n-primary-color); text-decoration: none;">从 @BotFather 获取的 Bot Token，用于发送消息。</a>
                  </n-space>
                </n-form-item>
                <n-form-item label="Chat ID">
                  <n-space vertical :size="2" style="width: 100%">
                    <n-input v-model:value="config.telegram.chat_id" type="password" show-password-on="click" placeholder="用户或群组 ID (如 12345678)" />
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
            <n-card bordered style="background: var(--app-surface-card)">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">网络代理设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="100">
                <n-form-item label="HTTP 代理" feedback="支持 http://ip:port 或 http://user:pass@ip:port">
                  <n-input v-model:value="config.http_proxy" placeholder="例如: http://192.168.50.66:7893" />
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

            <n-card bordered style="background: var(--app-surface-card)">
              <template #header>
                <div class="card-title-box">
                  <span class="card-title-text">自动化设置</span>
                </div>
              </template>
              <n-form label-placement="left" label-width="120">
                <n-grid :cols="2" :x-gap="24" :y-gap="16">
                  <!-- 第一行: RSS 刷新 -->
                  <n-gi>
                    <n-form-item label="RSS 自动刷新">
                      <n-switch v-model:value="config.rss_auto_refresh" />
                    </n-form-item>
                    <div class="form-item-desc">定时拉取 RSS 源，检测新发布的资源</div>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="刷新间隔 (分)">
                      <n-input-number 
                        v-model:value="config.rss_refresh_interval" 
                        :min="1" :max="1440" 
                        :disabled="!config.rss_auto_refresh"
                        placeholder="请输入分钟数" 
                        style="width: 100%" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第二行: 规则同步 -->
                  <n-gi>
                    <n-form-item label="规则自动同步">
                      <n-switch v-model:value="config.rule_auto_update" />
                    </n-form-item>
                    <div class="form-item-desc">定时从远程地址同步社区识别规则</div>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="同步周期 (时)">
                      <n-input-number 
                        v-model:value="config.rule_update_interval" 
                        :min="1" 
                        :disabled="!config.rule_auto_update"
                        placeholder="请输入小时数" 
                        style="width: 100%" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第三行: 自动补全 -->
                  <n-gi>
                    <n-form-item label="自动搜寻补全">
                      <n-switch v-model:value="config.sub_auto_fill" />
                    </n-form-item>
                    <div class="form-item-desc">自动搜寻补全缺失的订阅集数</div>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="补全周期 (时)">
                      <n-input-number 
                        v-model:value="config.sub_fill_interval" 
                        :min="1" 
                        :disabled="!config.sub_auto_fill"
                        placeholder="请输入小时数" 
                        style="width: 100%" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第四行: 定时清理 -->
                  <n-gi>
                    <n-form-item label="定时清理缓存">
                      <n-switch v-model:value="config.auto_clear_recognition" />
                    </n-form-item>
                    <div class="form-item-desc">定时清空 RSS 订阅项缓存</div>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="清理周期 (时)">
                      <n-input-number 
                        v-model:value="config.auto_clear_interval" 
                        :min="1" 
                        :disabled="!config.auto_clear_recognition"
                        placeholder="请输入小时数" 
                        style="width: 100%" 
                      />
                    </n-form-item>
                  </n-gi>

                  <!-- 第五行: 下载超时熔断 -->
                  <n-gi>
                    <n-form-item label="死种超时删除" feedback="0 为禁用">
                      <n-input-number 
                        v-model:value="config.stalled_timeout_minutes" 
                        :min="0" :max="43200"
                        placeholder="例如 60" 
                        style="width: 100%" 
                      >
                        <template #suffix>分钟</template>
                      </n-input-number>
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="巡检频率 (分)" feedback="0 为禁用，建议 15-60">
                      <n-input-number 
                        v-model:value="config.stalled_monitor_interval" 
                        :min="0" :max="1440"
                        placeholder="例如 30" 
                        style="width: 100%" 
                      >
                        <template #suffix>分钟</template>
                      </n-input-number>
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
          <n-card bordered style="background: var(--app-surface-card)">
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
                <n-card hoverable class="client-card" @click="openEditClient(client)">
                  <div class="client-info">
                    <div class="client-name">
                      <n-icon v-if="client.is_default" style="color: var(--n-warning-color)" title="默认客户端">
                         <span style="font-size:12px">★</span>
                      </n-icon>
                      {{ client.name }}
                    </div>
                    <div class="client-meta">{{ client.type }} | {{ client.url }}</div>
                  </div>
                  <template #action>
                    <n-space justify="end" @click.stop>
                      <n-popconfirm
                        positive-text="确定"
                        negative-text="取消"
                        @positive-click="handleDeleteClient(client.id)"
                      >
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                            <template #icon><n-icon><DeleteIcon/></n-icon></template>
                          </n-button>
                        </template>
                        确定要删除该下载客户端配置吗？
                      </n-popconfirm>
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
            <ConfigSection 
              title="自定义识别词" 
              description="这些词会被从文件名中剔除，防止干扰解析。支持正则替换 (A => B) 或直接删除 (A)。"
              placeholder="例如: 10月新番&#10;或者: 藤本树 17-26 => 藤本树 17_26"
              v-model:local="config.custom_noise_words" 
              v-model:remote="config.remote_noise_urls" 
            />

            <ConfigSection 
              title="自定义制作组" 
              description="强制将这些词识别为制作组，不受内置库限制。"
              placeholder="例如: SweetSub&#10;Mikanani"
              v-model:local="config.custom_release_groups" 
              v-model:remote="config.remote_group_urls" 
            />

            <ConfigSection 
              title="自定义渲染词" 
              description="在识别完成后执行，用于修改标题、修正季集或强制重定向 TMDB ID。"
              placeholder="例如: 剧场版 => {[type=movie]}&#10;S2 => {[s=2]}"
              v-model:local="config.custom_render_words" 
              v-model:remote="config.remote_render_urls" 
            />

            <ConfigSection 
              title="自定义特权规则" 
              description="优先级极高的提取规则，命中后集数直接锁定，标题作为优先搜索候选。"
              placeholder="格式: 正则表达式 => {[字段=值;字段=值]}&#10;例如: ^\[([^\]]+)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3]}&#10;例如: Yami.Shibai.+?(\d+).+?(\d+).+?^[A-Za-z]+$ => {[tmdbid=56559;type=tv;s=\1;e=\2]}"
              v-model:local="config.custom_privileged_rules" 
              v-model:remote="config.remote_privileged_urls" 
            />

            <n-card bordered style="background: var(--app-surface-card)">
              <n-space justify="center">
                <n-button v-bind="getButtonStyle('secondary')" :loading="syncLoading" @click="refreshRemoteRules">
                  立即从所有远程 URL 同步规则
                </n-button>
              </n-space>
            </n-card>
          </n-space>
        </n-tab-pane>

        <!-- AI 实验室 -->
        <n-tab-pane name="ai_lab" tab="AI 实验室">
          <AiLabView />
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

.client-card .client-name { font-weight: bold; font-size: 16px; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.client-card .client-meta { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.empty-clients { padding: 40px; text-align: center; color: var(--text-muted); border: 1px dashed var(--border-medium); border-radius: 8px; }

.switch-label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-desc { font-size: 12px; color: var(--text-tertiary); }

.form-item-desc { font-size: 12px; color: var(--text-tertiary); margin-top: -8px; margin-bottom: 8px; line-height: 1.4; }

/* Tabs 样式已移至 global.css 统一管理 */
</style>