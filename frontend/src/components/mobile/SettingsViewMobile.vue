<script setup lang="ts">
import {
  NSpace, NButton, NIcon, NInput, NForm, NFormItem,
  NDivider, NSwitch, NTabs, NTabPane,
  NSpin, NCheckbox, NInputNumber, NPopconfirm, NTag
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  SyncOutlined as SyncIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  AddOutlined as AddIcon
} from '@vicons/material'
import ConfigSectionMobile from './ConfigSectionMobile.vue'
import ClientEditModal from '../../components/ClientEditModal.vue'
import HealthCheckManager from '../../components/HealthCheckManager.vue'
import EmbyConfigMobile from './EmbyConfigMobile.vue'
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
      <n-button type="primary" size="small" :loading="loading" @click="saveAll">
        <template #icon><n-icon><SaveIcon /></n-icon></template>
        保存
      </n-button>
    </div>

    <n-spin :show="loading" class="m-tabs-wrapper">
      <n-tabs type="line" class="m-tabs" size="small" :tabs-padding="16">
        <!-- 基础配置 -->
        <n-tab-pane name="basic" tab="基础">
          <div class="m-tab-content">
            <n-space vertical size="large">
              <!-- TMDB 设置 -->
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
                  <div class="switch-list">
                    <div class="switch-item">
                      <span class="switch-label">动漫识别优化</span>
                      <n-switch v-model:value="config.anime_priority" size="small" />
                    </div>
                    <div class="switch-item">
                      <span class="switch-label">本地数据优先</span>
                      <n-switch v-model:value="config.offline_priority" size="small" />
                    </div>
                    <div class="switch-item">
                      <span class="switch-label">合集增强</span>
                      <n-switch v-model:value="config.batch_enhancement" size="small" />
                    </div>
                    <div class="switch-item">
                      <span class="switch-label">Bangumi 源优先</span>
                      <n-switch v-model:value="config.bangumi_priority" size="small" />
                    </div>
                    <div class="switch-item">
                      <span class="switch-label">Bangumi 故障转移</span>
                      <n-switch v-model:value="config.bangumi_failover" :disabled="config.bangumi_priority" size="small" />
                    </div>
                    <div class="switch-item">
                      <span class="switch-label">智能记忆</span>
                      <n-switch v-model:value="config.series_fingerprint" size="small" />
                    </div>
                  </div>
                </n-form>
              </div>

              <!-- Jackett 设置 -->
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

              <!-- Emby 设置 -->
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

              <!-- 通知设置 -->
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

                  <n-divider dashed>通知类型</n-divider>
                  <div class="checkbox-grid">
                    <n-checkbox v-model:checked="config.telegram.notify_on_startup" size="small">系统启动</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_add" size="small">新增订阅</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_del" size="small">删除订阅</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_complete" size="small">订阅完结</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_sub_push" size="small">订阅推送</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_rule_push" size="small">规则下载</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_organize" size="small">整理完成</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_strm_finish" size="small">STRM完成</n-checkbox>
                    <n-checkbox v-model:checked="config.telegram.notify_on_strm_link" size="small">STRM联动</n-checkbox>
                  </div>

                  <n-form-item label="开关">
                    <n-space justify="space-between" style="width: 100%">
                      <n-switch v-model:value="config.telegram.enabled" size="small" />
                      <n-button type="primary" size="tiny" secondary @click="testTelegram" :disabled="!config.telegram.bot_token" :loading="testTgLoading">测试</n-button>
                    </n-space>
                  </n-form-item>
                </n-form>
              </div>

              <!-- 代理设置 -->
              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">代理设置</h3>
                </div>
                <n-form label-placement="top">
                  <n-form-item label="HTTP 代理">
                    <n-input v-model:value="config.http_proxy" placeholder="http://ip:port" />
                  </n-form-item>

                  <n-divider dashed>应用范围</n-divider>
                  <div class="checkbox-grid">
                    <n-checkbox v-model:checked="config.proxy_services.tmdb" size="small">TMDB</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.bangumi" size="small">Bangumi</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.telegram" size="small">Telegram</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.rss" size="small">RSS</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.jackett" size="small">Jackett</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.remote_rules" size="small">远程规则</n-checkbox>
                    <n-checkbox v-model:checked="config.proxy_services.docker_hub" size="small">Docker Hub</n-checkbox>
                  </div>
                </n-form>
              </div>

              <!-- 自动化 -->
              <div class="m-card">
                <div class="m-card-header">
                  <h3 class="m-card-title">自动化</h3>
                </div>
                <n-form label-placement="top">
                  <div class="auto-item">
                    <div class="auto-header">
                      <span class="auto-label">RSS 自动刷新</span>
                      <n-switch v-model:value="config.rss_auto_refresh" size="small" />
                    </div>
                    <n-input-number v-if="config.rss_auto_refresh" v-model:value="config.rss_refresh_interval" :min="1" size="small" style="width: 120px">
                      <template #suffix>分钟</template>
                    </n-input-number>
                  </div>

                  <div class="auto-item">
                    <div class="auto-header">
                      <span class="auto-label">规则自动同步</span>
                      <n-switch v-model:value="config.rule_auto_update" size="small" />
                    </div>
                    <n-input-number v-if="config.rule_auto_update" v-model:value="config.rule_update_interval" :min="1" size="small" style="width: 120px">
                      <template #suffix>小时</template>
                    </n-input-number>
                  </div>

                  <div class="auto-item">
                    <div class="auto-header">
                      <span class="auto-label">自动搜寻补全</span>
                      <n-switch v-model:value="config.sub_auto_fill" size="small" />
                    </div>
                    <n-input-number v-if="config.sub_auto_fill" v-model:value="config.sub_fill_interval" :min="1" size="small" style="width: 120px">
                      <template #suffix>小时</template>
                    </n-input-number>
                  </div>

                  <div class="auto-item">
                    <div class="auto-header">
                      <span class="auto-label">定时清理缓存</span>
                      <n-switch v-model:value="config.auto_clear_recognition" size="small" />
                    </div>
                    <n-input-number v-if="config.auto_clear_recognition" v-model:value="config.auto_clear_interval" :min="1" size="small" style="width: 120px">
                      <template #suffix>小时</template>
                    </n-input-number>
                  </div>

                  <n-divider dashed />

                  <div class="number-row">
                    <n-form-item label="死种超时" style="flex: 1">
                      <n-input-number v-model:value="config.stalled_timeout_minutes" :min="0" size="small" style="width: 100%">
                        <template #suffix>分钟</template>
                      </n-input-number>
                    </n-form-item>
                    <n-form-item label="巡检频率" style="flex: 1">
                      <n-input-number v-model:value="config.stalled_monitor_interval" :min="0" size="small" style="width: 100%">
                        <template #suffix>分钟</template>
                      </n-input-number>
                    </n-form-item>
                  </div>
                </n-form>
              </div>
            </n-space>
          </div>
        </n-tab-pane>

        <!-- 下载器 -->
        <n-tab-pane name="clients" tab="下载器">
          <div class="m-tab-content">
            <n-button type="primary" dashed size="small" block class="m-mb-lg" @click="openAddClient">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              添加客户端
            </n-button>

            <div class="m-card-list">
              <div v-for="client in clients" :key="client.id" class="m-card-item">
                <div class="m-list-item-content">
                  <div class="m-list-item-title">{{ client.name }}</div>
                  <div class="m-list-item-desc">{{ client.type }} | {{ client.url }}</div>
                </div>
                <div class="m-flex m-items-center m-gap-sm">
                  <n-tag v-if="client.is_default" type="warning" size="tiny">默认</n-tag>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openEditClient(client)">
                    <template #icon><n-icon><EditIcon/></n-icon></template>
                  </n-button>
                  <n-popconfirm
                    @positive-click="handleDeleteClient(client.id)"
                    positive-text="确定"
                    negative-text="取消"
                  >
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
              <ConfigSectionMobile title="识别干扰词" v-model:local="config.custom_noise_words" v-model:remote="config.remote_noise_urls" />
              <ConfigSectionMobile title="自定义制作组" v-model:local="config.custom_release_groups" v-model:remote="config.remote_group_urls" />
              <ConfigSectionMobile title="渲染替换" v-model:local="config.custom_render_words" v-model:remote="config.remote_render_urls" />
              <ConfigSectionMobile title="特权规则" v-model:local="config.custom_privileged_rules" v-model:remote="config.remote_privileged_urls" />
              <n-button type="primary" secondary size="small" block :loading="syncLoading" @click="refreshRemoteRules">
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

.m-tabs-wrapper :deep(.n-spin-content) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.m-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.m-tabs :deep(.n-tabs-nav) {
  padding: var(--m-spacing-sm) 0;
  flex-shrink: 0;
}

.m-tabs :deep(.n-tabs-nav-scroll-wrapper) {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.m-tabs :deep(.n-tabs-nav-scroll-wrapper::-webkit-scrollbar) {
  display: none;
}

.m-tabs :deep(.n-tabs-nav-scroll-content) {
  display: flex;
  gap: var(--m-spacing-xs);
}

.m-tabs :deep(.n-tab) {
  padding: var(--m-spacing-xs) var(--m-spacing-md);
  white-space: nowrap;
}

.m-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.m-tabs :deep(.n-tab-pane) {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0;
}

.m-tab-content {
  padding: var(--m-spacing-md);
  padding-bottom: calc(var(--m-spacing-md) + var(--m-safe-bottom));
}

/* 卡片样式 */
.m-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-md);
}

.m-card-header {
  margin-bottom: var(--m-spacing-md);
}

.m-card-title {
  font-size: var(--m-text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Switch 列表 */
.switch-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.switch-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-xs) 0;
}

.switch-label {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}

/* Checkbox 网格 */
.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--m-spacing-sm);
}

/* 自动化项 */
.auto-item {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
  padding: var(--m-spacing-sm) 0;
  border-bottom: 1px solid var(--app-border-light);
}

.auto-item:last-of-type {
  border-bottom: none;
}

.auto-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.auto-label {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}

/* 数字输入行 */
.number-row {
  display: flex;
  gap: var(--m-spacing-md);
}

/* 下载器列表 */
.m-card-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}

.m-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--m-spacing-md);
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-md);
}

.m-list-item-content {
  flex: 1;
  min-width: 0;
}

.m-list-item-title {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.m-list-item-desc {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 间距工具类 */
.m-mb-lg {
  margin-bottom: var(--m-spacing-lg);
}

.m-flex {
  display: flex;
}

.m-items-center {
  align-items: center;
}

.m-gap-sm {
  gap: var(--m-spacing-sm);
}
</style>
