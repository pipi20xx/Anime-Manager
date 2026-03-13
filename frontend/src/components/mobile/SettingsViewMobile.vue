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
  <div class="m-page m-page-safe-bottom">
    <!-- 页面头部 -->
    <div class="m-header m-header-plain">
      <h1 class="m-header-title">系统设置</h1>
      <n-button v-bind="getButtonStyle('primary')" :loading="loading" @click="saveAll">
        <template #icon><n-icon><SaveIcon /></n-icon></template>
        保存
      </n-button>
    </div>

    <n-spin :show="loading" class="m-tabs-wrapper">
      <n-tabs type="line" animated class="m-tabs">
        <!-- 基础配置 -->
        <n-tab-pane name="basic" tab="基础">
          <div class="m-tab-content">
            <n-space vertical size="large">
              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">TMDB 设置</h3>
                </div>
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
              </div>

              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">Jackett 设置</h3>
                </div>
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
              </div>

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

              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">通知设置 (Telegram)</h3>
                </div>
                <n-form label-placement="top">
                  <n-form-item label="Bot Token">
                     <n-input v-model:value="config.telegram.bot_token" type="password" show-password-on="click" placeholder="Bot Token" />
                  </n-form-item>
                  <n-form-item label="Chat ID">
                    <n-input v-model:value="config.telegram.chat_id" type="password" show-password-on="click" placeholder="Chat ID" />
                  </n-form-item>
                  <n-form-item label="通知类型">
                    <n-grid :cols="2" y-gap="8">
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
                    <n-space justify="space-between" style="width: 100%">
                      <n-switch v-model:value="config.telegram.enabled" />
                      <n-button v-bind="getButtonStyle('secondary')" size="tiny" @click="testTelegram" :disabled="!config.telegram.bot_token" :loading="testTgLoading">测试</n-button>
                    </n-space>
                  </n-form-item>
                </n-form>
              </div>

              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">代理设置</h3>
                </div>
                <n-form label-placement="top">
                  <n-form-item label="HTTP 代理">
                    <n-input v-model:value="config.http_proxy" placeholder="http://ip:port" />
                  </n-form-item>
                  <n-form-item label="应用范围">
                    <n-grid :cols="2" y-gap="8">
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
              </div>

              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">自动化</h3>
                </div>
                <n-form label-placement="top">
                  <n-grid :cols="2" x-gap="12" y-gap="16">
                    <n-gi :span="2">
                      <n-form-item label="RSS 自动刷新">
                        <n-space align="center">
                          <n-switch v-model:value="config.rss_auto_refresh" />
                          <n-input-number v-if="config.rss_auto_refresh" v-model:value="config.rss_refresh_interval" :min="1" size="small" style="width: 100px"><template #suffix>分</template></n-input-number>
                        </n-space>
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="2">
                      <n-form-item label="规则自动同步">
                        <n-space align="center">
                          <n-switch v-model:value="config.rule_auto_update" />
                          <n-input-number v-if="config.rule_auto_update" v-model:value="config.rule_update_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                        </n-space>
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="2">
                      <n-form-item label="自动搜寻补全">
                        <n-space align="center">
                          <n-switch v-model:value="config.sub_auto_fill" />
                          <n-input-number v-if="config.sub_auto_fill" v-model:value="config.sub_fill_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                        </n-space>
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="2">
                      <n-form-item label="定时清理缓存">
                        <n-space align="center">
                          <n-switch v-model:value="config.auto_clear_recognition" />
                          <n-input-number v-if="config.auto_clear_recognition" v-model:value="config.auto_clear_interval" :min="1" size="small" style="width: 100px"><template #suffix>时</template></n-input-number>
                        </n-space>
                      </n-form-item>
                    </n-gi>
                    
                    <n-gi :span="2"><n-divider dashed /></n-gi>

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
              </div>
            </n-space>
          </div>
        </n-tab-pane>

        <!-- 下载器 -->
        <n-tab-pane name="clients" tab="下载器">
          <div class="m-tab-content">
            <n-button v-bind="getButtonStyle('primary')" block dashed class="m-mb-lg" @click="openAddClient">
              添加客户端
            </n-button>
            
            <div class="m-card-list">
              <div v-for="client in clients" :key="client.id" class="m-card-item">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">{{ client.name }}</div>
                  <div class="m-list-item-desc">{{ client.type }} | {{ client.url }}</div>
                </div>
                <div class="m-flex m-items-center m-gap-sm">
                  <n-tag v-if="client.is_default" type="warning" size="small">默认</n-tag>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openEditClient(client)">
                    <template #icon><n-icon><EditIcon/></n-icon></template>
                  </n-button>
                  <n-popconfirm @positive-click="handleDeleteClient(client.id)">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                        <template #icon><n-icon><DeleteIcon/></n-icon></template>
                      </n-button>
                    </template>
                    确定删除?
                  </n-popconfirm>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 规则 -->
        <n-tab-pane name="rules" tab="规则">
          <div class="m-tab-content">
            <n-space vertical size="large">
              <ConfigSection title="识别干扰词" v-model:local="config.custom_noise_words" v-model:remote="config.remote_noise_urls" />
              <ConfigSection title="自定义制作组" v-model:local="config.custom_release_groups" v-model:remote="config.remote_group_urls" />
              <ConfigSection title="渲染替换" v-model:local="config.custom_render_words" v-model:remote="config.remote_render_urls" />
              <ConfigSection title="特权规则" v-model:local="config.custom_privileged_rules" v-model:remote="config.remote_privileged_urls" />
              <n-button v-bind="getButtonStyle('secondary')" block :loading="syncLoading" @click="refreshRemoteRules">
                <template #icon><n-icon><SyncIcon /></n-icon></template>
                同步远程规则
              </n-button>
            </n-space>
          </div>
        </n-tab-pane>

        <!-- AI -->
        <n-tab-pane name="ai" tab="AI">
          <div class="m-tab-content">
            <AiLabView />
          </div>
        </n-tab-pane>

        <!-- 账号 -->
        <n-tab-pane name="account" tab="账号">
          <div class="m-tab-content">
            <AccountTab />
          </div>
        </n-tab-pane>

        <!-- 服务状态 -->
        <n-tab-pane name="services" tab="服务">
          <div class="m-tab-content">
            <ServiceStatusTabMobile />
          </div>
        </n-tab-pane>

        <!-- 掉盘 -->
        <n-tab-pane name="health" tab="掉盘">
          <div class="m-tab-content">
            <HealthCheckManager />
          </div>
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
.m-tabs-wrapper {
  flex: 1;
  overflow: hidden;
}

.m-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.m-tabs :deep(.n-tabs-nav) {
  padding: var(--m-spacing-sm) var(--m-spacing-lg);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.m-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

.m-tabs :deep(.n-tab-pane) {
  height: 100%;
  overflow-y: auto;
  padding: 0;
}

.m-tab-content {
  padding: var(--m-spacing-lg);
}

/* 下载器列表项特殊样式 */
.m-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
