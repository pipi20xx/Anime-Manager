<script setup lang="ts">
import { 
  NCard, NSpace, NButton, NIcon, NInput, NForm, NFormItem, 
  NDivider, NGrid, NGi, NSwitch, NTabs, NTabPane,
  NSpin, NCheckbox, NInputNumber, NPopconfirm, NList, NListItem, NThing
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  SyncOutlined as SyncIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon
} from '@vicons/material'
import ConfigSection from '../../components/ConfigSection.vue'
import ClientEditModal from '../../components/ClientEditModal.vue'
import HealthCheckManager from '../../components/HealthCheckManager.vue'
import EmbyConfigMobile from '../../components/mobile/EmbyConfigMobile.vue'
import AiLabView from '../../views/AiLabView.vue'
import AccountTab from '../../views/settings/AccountTab.vue'
import ServiceStatusTabMobile from '../../views/settings/ServiceStatusTabMobile.vue'
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
  <div class="settings-view-mobile">
    <div class="mobile-header">
      <div class="header-title">系统设置</div>
      <n-button v-bind="getButtonStyle('primary')" size="small" :loading="loading" @click="saveAll">
        保存
      </n-button>
    </div>

    <n-spin :show="loading">
      <n-tabs type="line" animated>
        <!-- 基础配置 -->
        <n-tab-pane name="basic" tab="基础">
          <n-space vertical>
            <n-card :bordered="false" title="TMDB 设置" size="small">
              <n-form label-placement="top">
                <n-form-item label="TMDB API Key">
                  <n-input v-model:value="config.tmdb_api_key" type="password" show-password-on="click" placeholder="输入 Key" />
                </n-form-item>
                <n-form-item label="Bangumi Token">
                  <n-input v-model:value="config.bangumi_token" type="password" show-password-on="click" placeholder="可选 Token" />
                </n-form-item>
                
                <n-divider dashed>策略开关</n-divider>
                <n-space vertical>
                  <n-switch v-model:value="config.anime_priority"><template #checked>动漫识别优化开启</template><template #unchecked>动漫识别优化关闭</template></n-switch>
                  <n-switch v-model:value="config.offline_priority"><template #checked>本地数据优先</template><template #unchecked>本地数据优先关闭</template></n-switch>
                  <n-switch v-model:value="config.batch_enhancement"><template #checked>合集增强开启</template><template #unchecked>合集增强关闭</template></n-switch>
                  <n-switch v-model:value="config.bangumi_priority"><template #checked>Bangumi 源优先</template><template #unchecked>TMDB 源优先</template></n-switch>
                  <n-switch v-model:value="config.bangumi_failover" :disabled="config.bangumi_priority"><template #checked>Bangumi 故障转移开启</template><template #unchecked>Bangumi 故障转移关闭</template></n-switch>
                  <n-switch v-model:value="config.series_fingerprint"><template #checked>智能记忆开启</template><template #unchecked>智能记忆关闭</template></n-switch>
                </n-space>
              </n-form>
            </n-card>

            <n-card :bordered="false" title="Jackett 设置" size="small">
              <n-form label-placement="top">
                <n-form-item label="URL">
                  <n-input v-model:value="config.jackett_url" placeholder="http://ip:port" />
                </n-form-item>
                <n-form-item label="API Key">
                  <n-input v-model:value="config.jackett_api_key" type="password" show-password-on="click" placeholder="API Key" />
                </n-form-item>
                <n-form-item label="管理密码">
                  <n-input v-model:value="config.jackett_password" type="password" show-password-on="click" placeholder="可选" />
                </n-form-item>
              </n-form>
            </n-card>

            <EmbyConfigMobile
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

            <n-card :bordered="false" title="通知设置 (Telegram)" size="small">
              <n-form label-placement="top">
                <n-form-item label="Bot Token">
                   <n-input v-model:value="config.telegram.bot_token" type="password" show-password-on="click" placeholder="Bot Token" />
                </n-form-item>
                <n-form-item label="Chat ID">
                  <n-input v-model:value="config.telegram.chat_id" type="password" show-password-on="click" placeholder="Chat ID" />
                </n-form-item>
                <n-form-item label="通知类型">
                  <n-grid :cols="2" :y-gap="8">
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_startup">系统启动</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_sub_add">新增订阅</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_sub_del">删除订阅</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_sub_complete">订阅完结</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_sub_push">订阅推送</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_rule_push">规则下载</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_organize">整理完成</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_strm_finish">STRM完成</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.telegram.notify_on_strm_link">STRM联动</n-checkbox></n-gi>
                  </n-grid>
                </n-form-item>
                <n-form-item label="开关">
                  <n-space justify="space-between">
                    <n-switch v-model:value="config.telegram.enabled" />
                    <n-button size="tiny" secondary @click="testTelegram" :disabled="!config.telegram.bot_token" :loading="testTgLoading">测试</n-button>
                  </n-space>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card :bordered="false" title="代理设置" size="small">
              <n-form label-placement="top">
                <n-form-item label="HTTP 代理">
                  <n-input v-model:value="config.http_proxy" placeholder="http://ip:port" />
                </n-form-item>
                <n-form-item label="应用范围">
                  <n-grid :cols="2" :y-gap="8">
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.tmdb">TMDB</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.bangumi">Bangumi</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.telegram">Telegram</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.rss">RSS</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.jackett">Jackett</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.remote_rules">远程规则</n-checkbox></n-gi>
                    <n-gi><n-checkbox v-model:checked="config.proxy_services.docker_hub">Docker Hub</n-checkbox></n-gi>
                  </n-grid>
                </n-form-item>
              </n-form>
            </n-card>

            <n-card :bordered="false" title="自动化" size="small">
              <n-form label-placement="top">
                <n-grid :cols="2" :x-gap="12" :y-gap="16">
                  <!-- RSS -->
                  <n-gi :span="2">
                    <n-form-item label="RSS 自动刷新">
                      <n-space align="center">
                        <n-switch v-model:value="config.rss_auto_refresh" />
                        <n-input-number v-if="config.rss_auto_refresh" v-model:value="config.rss_refresh_interval" :min="1" size="small" style="width: 100px"><template #suffix>分</template></n-input-number>
                      </n-space>
                    </n-form-item>
                  </n-gi>
                  <!-- 规则 -->
                  <n-gi :span="2">
                    <n-form-item label="规则自动同步">
                      <n-space align="center">
                        <n-switch v-model:value="config.rule_auto_update" />
                        <n-input-number v-if="config.rule_auto_update" v-model:value="config.rule_update_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                      </n-space>
                    </n-form-item>
                  </n-gi>
                  <!-- 补全 -->
                  <n-gi :span="2">
                    <n-form-item label="自动搜寻补全">
                      <n-space align="center">
                        <n-switch v-model:value="config.sub_auto_fill" />
                        <n-input-number v-if="config.sub_auto_fill" v-model:value="config.sub_fill_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                      </n-space>
                    </n-form-item>
                  </n-gi>
                  <!-- 清理 -->
                  <n-gi :span="2">
                    <n-form-item label="定时清理缓存">
                      <n-space align="center">
                        <n-switch v-model:value="config.auto_clear_recognition" />
                        <n-input-number v-if="config.auto_clear_recognition" v-model:value="config.auto_clear_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                      </n-space>
                    </n-form-item>
                  </n-gi>
                  
                  <n-gi :span="2"><n-divider dashed /></n-gi>

                  <!-- 死种 -->
                  <n-gi>
                    <n-form-item label="死种超时(分)">
                      <n-input-number v-model:value="config.stalled_timeout_minutes" :min="0" style="width: 100%" />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="巡检频率(分)">
                      <n-input-number v-model:value="config.stalled_monitor_interval" :min="0" style="width: 100%" />
                    </n-form-item>
                  </n-gi>
                </n-grid>
              </n-form>
            </n-card>
          </n-space>
        </n-tab-pane>

        <!-- 下载器 -->
        <n-tab-pane name="clients" tab="下载器">
          <n-button block dashed type="primary" @click="openAddClient" style="margin-bottom: 12px">
            添加客户端
          </n-button>
          
          <n-list hoverable>
            <n-list-item v-for="client in clients" :key="client.id">
              <n-thing :title="client.name">
                <template #description>{{ client.type }} | {{ client.url }}</template>
                <template #header-extra>
                   <n-tag v-if="client.is_default" type="warning" size="small">默认</n-tag>
                </template>
              </n-thing>
              <template #suffix>
                <n-space vertical>
                  <n-button circle size="small" @click="openEditClient(client)"><template #icon><n-icon><EditIcon/></n-icon></template></n-button>
                  <n-popconfirm @positive-click="handleDeleteClient(client.id)">
                    <template #trigger>
                      <n-button circle size="small" type="error" ghost><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
                    </template>
                    确定删除?
                  </n-popconfirm>
                </n-space>
              </template>
            </n-list-item>
          </n-list>
        </n-tab-pane>

        <!-- 规则 -->
        <n-tab-pane name="rules" tab="规则">
          <n-space vertical>
            <ConfigSection title="识别干扰词" v-model:local="config.custom_noise_words" v-model:remote="config.remote_noise_urls" />
            <ConfigSection title="自定义制作组" v-model:local="config.custom_release_groups" v-model:remote="config.remote_group_urls" />
            <ConfigSection title="渲染替换" v-model:local="config.custom_render_words" v-model:remote="config.remote_render_urls" />
            <ConfigSection title="特权规则" v-model:local="config.custom_privileged_rules" v-model:remote="config.remote_privileged_urls" />
            <n-button block secondary type="info" :loading="syncLoading" @click="refreshRemoteRules">同步远程规则</n-button>
          </n-space>
        </n-tab-pane>

        <!-- AI -->
        <n-tab-pane name="ai" tab="AI">
          <AiLabView />
        </n-tab-pane>

        <!-- 账号 -->
        <n-tab-pane name="account" tab="账号">
          <AccountTab />
        </n-tab-pane>

        <!-- 服务状态 -->
        <n-tab-pane name="services" tab="服务">
          <ServiceStatusTabMobile />
        </n-tab-pane>

        <!-- 掉盘 -->
        <n-tab-pane name="health" tab="掉盘">
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
.settings-view-mobile { padding-bottom: 20px; }
.mobile-header { display: flex; justify-content: space-between; align-items: center; padding: 0 4px 12px 4px; }
.header-title { font-size: 18px; font-weight: bold; }
</style>